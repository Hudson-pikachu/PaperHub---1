"""Independent script: chấm điểm bài nghiên cứu dựa trên title & abstract gốc tiếng Anh.

Sử dụng Gemini API với temperature thấp (0.1) để đảm bảo tính ổn định.
Script này hoạt động ĐỘC LẬP, không gọi cùng với AI summary/dịch thuật.

Cách dùng:
    cd source
    python -m scripts.score_papers          # Chấm tất cả bài chưa có điểm
    python -m scripts.score_papers --limit 10   # Chỉ chấm 10 bài đầu chưa có điểm
    python -m scripts.score_papers --all    # Chấm lại TẤT CẢ bài (kể cả đã có điểm)

Tiêu chí chấm điểm (tổng 10 điểm):
    1. Sự đột phá về phương pháp (4 điểm):
       3-4đ: Đề xuất kiến trúc mới, thuật toán mới hoặc cách tiếp cận chưa từng thấy.
       1-2đ: Cải tiến dựa trên mô hình cũ (ví dụ: thay đổi nhẹ layer, thêm attention vào model cũ).

    2. Hiệu suất định lượng (4 điểm):
       3-4đ: Có con số cải thiện rõ rệt (ví dụ: +5% accuracy, giảm 2x latency) so với SOTA.
       1-2đ: Kết quả tốt nhưng con số không ấn tượng hoặc không so sánh trực diện với SOTA.

    3. Tính kiểm chứng & Tài nguyên (2 điểm):
       2đ: Nhắc đến bộ dataset lớn, chuẩn hóa hoặc đề cập đến mã nguồn/link GitHub.
       0đ: Kết quả trên dataset tự chế hoặc không rõ ràng về môi trường thực nghiệm.
"""

import argparse
import json
import re
import sys
import time
import io

# Fix UnicodeEncodeError on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
except Exception:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

from google import genai
from google.genai import types

from app import create_app
from app.database.models import Paper, db

# API key (cùng key với ai_service.py)
GOOGLE_API_KEY = "AIzaSyCy3K9OGxa7wQgPKz--Mo5esO-S1xDti_M"

# Temperature thấp để điểm ổn định qua các lần chấm
SCORING_TEMPERATURE = 0.1

# Model dùng để chấm điểm
SCORING_MODEL = "gemini-2.5-flash-lite"

# Delay giữa các request để tránh rate limit
DELAY_BETWEEN_REQUESTS = 1.5

# Số bài gửi trong 1 batch (mỗi lần gọi API)
BATCH_SIZE = 5


def _get_client():
    """Khởi tạo Gemini client."""
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        raise RuntimeError("GOOGLE_API_KEY must be configured in score_papers.py")
    return genai.Client(api_key=GOOGLE_API_KEY)


def _parse_score_response(text: str, expected_count: int) -> list[dict]:
    """Parse JSON array từ response của Gemini.

    Args:
        text: Raw response text từ Gemini.
        expected_count: Số lượng kết quả mong đợi.

    Returns:
        List[dict]: Mỗi dict có keys: index, method_score, performance_score,
                    verifiability_score, total_score, reasoning.
    """
    json_text = text.strip()
    # Xóa markdown code fences nếu có
    json_text = re.sub(r"^```(?:json)?\s*", "", json_text)
    json_text = re.sub(r"\s*```$", "", json_text)

    # Tìm JSON array trong response
    match = re.search(r"\[.*\]", json_text, re.DOTALL)
    if not match:
        match = re.search(r"\{.*\}", json_text, re.DOTALL)
    if match:
        json_text = match.group(0)

    # Escape invalid JSON backslashes (LaTeX artifacts)
    json_text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", json_text)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        raise ValueError(f"Không parse được JSON từ response:\n{text[:500]}")

    # Hỗ trợ cả object bọc ngoài và array trực tiếp
    if isinstance(data, dict):
        items = data.get("results") or data.get("scores") or data.get("papers") or []
        if not items:
            for v in data.values():
                if isinstance(v, list):
                    items = v
                    break
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(f"Response không phải array/object: {type(data)}")

    if len(items) != expected_count:
        raise ValueError(
            f"Số kết quả ({len(items)}) không khớp với số bài gửi ({expected_count})"
        )

    return items


def build_scoring_prompt(papers: list[Paper]) -> str:
    """Xây dựng prompt chấm điểm cho một batch papers.

    Args:
        papers: Danh sách các Paper cần chấm điểm.

    Returns:
        Prompt string gửi cho Gemini.
    """
    papers_json_blocks = []
    for i, paper in enumerate(papers):
        # Dùng title_en và abstract_en (gốc tiếng Anh) để chấm
        title = paper.title_en or paper.title or ""
        abstract = paper.abstract_en or paper.abstract or ""

        block = f"""
  {{
    "index": {i},
    "title": {json.dumps(title, ensure_ascii=False)},
    "abstract": {json.dumps(abstract[:2000], ensure_ascii=False)}
  }}"""
        papers_json_blocks.append(block.strip())

    papers_json = "[\n" + ",\n".join(papers_json_blocks) + "\n]"

    prompt = f"""Bạn là chuyên gia đánh giá bài nghiên cứu khoa học trong lĩnh vực AI/ML/CS.
Nhiệm vụ: Chấm điểm {len(papers)} bài nghiên cứu dưới đây dựa trên 3 tiêu chí.

=== TIÊU CHÍ CHẤM ĐIỂM (TỔNG 10 ĐIỂM) ===

1. SỰ ĐỘT PHÁ VỀ PHƯƠNG PHÁP (0-4 điểm):
   - 3-4 điểm: Đề xuất kiến trúc mới, thuật toán mới hoặc cách tiếp cận CHƯA TỪNG THẤY trước đây. Có tính sáng tạo cao, mở ra hướng nghiên cứu mới.
   - 1-2 điểm: Cải tiến dựa trên mô hình cũ (ví dụ: thay đổi nhẹ layer, thêm attention vào model cũ, điều chỉnh loss function). Có đóng góp nhưng không đột phá.
   - 0 điểm: Không có đóng góp mới về phương pháp, chỉ là survey hoặc áp dụng lại phương pháp cũ.

2. HIỆU SUẤT ĐỊNH LƯỢNG (0-4 điểm):
   - 3-4 điểm: Có con số cải thiện RÕ RỆT (ví dụ: +5% accuracy, giảm 2x latency, +10% F1-score) so với SOTA (State-of-the-art). Có bảng so sánh trực tiếp với các đối thủ mạnh nhất.
   - 1-2 điểm: Kết quả tốt nhưng con số KHÔNG ấn tượng hoặc không so sánh trực diện với SOTA. Chỉ so sánh với baseline yếu.
   - 0 điểm: Không có kết quả định lượng hoặc không đề cập đến hiệu suất.

3. TÍNH KIỂM CHỨNG & TÀI NGUYÊN (0-2 điểm):
   - 2 điểm: Nhắc đến bộ dataset LỚN, CHUẨN HÓA (ví dụ: ImageNet, CIFAR, GLUE, SQuAD, COCO) hoặc đề cập đến mã nguồn mở/link GitHub công khai.
   - 1 điểm: Có dataset nhưng nhỏ hoặc không phổ biến; có nhắc đến code nhưng không rõ ràng.
   - 0 điểm: Kết quả trên dataset tự chế, không rõ ràng về môi trường thực nghiệm, hoặc không đề cập gì về khả năng tái tạo.

=== DỮ LIỆU CẦN CHẤM ===
{papers_json}

=== YÊU CẦU ĐẦU RA ===
Trả về MỘT JSON array (KHÔNG có markdown code fence) với đúng {len(papers)} phần tử.
Mỗi phần tử là một object có định dạng:
{{
  "index": <số thứ tự khớp với input>,
  "method_score": <điểm tiêu chí 1, số nguyên 0-4>,
  "performance_score": <điểm tiêu chí 2, số nguyên 0-4>,
  "verifiability_score": <điểm tiêu chí 3, số nguyên 0-2>,
  "total_score": <tổng 3 điểm trên, số nguyên 0-10>,
  "reasoning": "<giải thích ngắn gọn 1-2 câu TIẾNG VIỆT cho điểm số>"
}}

QUAN TRỌNG:
- total_score PHẢI bằng method_score + performance_score + verifiability_score.
- Chỉ chấm dựa trên title và abstract được cung cấp, không suy đoán thêm.
- Giữ nguyên thứ tự index.
- Trả về ĐÚNG {len(papers)} phần tử."""
    return prompt


def score_batch(papers: list[Paper], client) -> list[dict]:
    """Gọi Gemini API để chấm điểm một batch papers.

    Args:
        papers: Danh sách Paper (tối đa BATCH_SIZE).
        client: Gemini client instance.

    Returns:
        List[dict]: Kết quả chấm điểm đã parse.
    """
    prompt = build_scoring_prompt(papers)

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        ),
    ]

    generate_config = types.GenerateContentConfig(
        temperature=SCORING_TEMPERATURE,
        max_output_tokens=2048,
    )

    response = client.models.generate_content(
        model=f"models/{SCORING_MODEL}",
        contents=contents,
        config=generate_config,
    )

    result_text = response.text if (hasattr(response, 'text') and response.text) else str(response)
    if not result_text:
        raise ValueError("Empty response from Gemini API")

    return _parse_score_response(result_text, len(papers))


def apply_scores(papers: list[Paper], score_results: list[dict]) -> int:
    """Ghi điểm vào database cho các paper đã chấm.

    Args:
        papers: Danh sách Paper tương ứng với score_results.
        score_results: Kết quả chấm điểm từ Gemini.

    Returns:
        Số bài đã cập nhật thành công.
    """
    saved = 0
    for item in score_results:
        idx = item.get("index", -1)
        if idx < 0 or idx >= len(papers):
            continue

        paper = papers[idx]
        total = item.get("total_score")

        if total is not None:
            paper.score = float(total)
            db.session.add(paper)
            saved += 1
            print(f"  [✓] Paper #{paper.id}: {total}/10 | "
                  f"M={item.get('method_score')} "
                  f"P={item.get('performance_score')} "
                  f"V={item.get('verifiability_score')} | "
                  f"{item.get('reasoning', '')[:80]}")

    db.session.commit()
    return saved


def run_scoring(limit: int | None = None, rescore_all: bool = False) -> dict:
    """Chạy quy trình chấm điểm toàn bộ papers chưa có điểm.

    Args:
        limit: Số lượng paper tối đa cần chấm (None = tất cả).
        rescore_all: Nếu True, chấm lại cả những bài đã có điểm.

    Returns:
        dict: Tổng kết {"total": int, "scored": int, "errors": int, "error_list": list}.
    """
    app = create_app()
    client = _get_client()

    total_scored = 0
    total_errors = 0
    error_list = []

    with app.app_context():
        # Query papers
        query = Paper.query
        if not rescore_all:
            query = query.filter(Paper.score.is_(None))
        query = query.order_by(Paper.id.desc())

        if limit and limit > 0:
            query = query.limit(limit)

        papers = query.all()
        total = len(papers)

        if total == 0:
            print("[Score] Không có bài nào cần chấm điểm.")
            return {"total": 0, "scored": 0, "errors": 0, "error_list": []}

        print(f"[Score] Tìm thấy {total} bài cần chấm điểm.")
        print(f"[Score] Model: {SCORING_MODEL}, Temperature: {SCORING_TEMPERATURE}")
        print(f"[Score] Batch size: {BATCH_SIZE}, Delay: {DELAY_BETWEEN_REQUESTS}s")
        print("-" * 60)

        # Xử lý theo batch
        for i in range(0, total, BATCH_SIZE):
            batch = papers[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"\n[Batch {batch_num}/{total_batches}] {len(batch)} papers: "
                  f"IDs {[p.id for p in batch]}")

            try:
                score_results = score_batch(batch, client)
                saved = apply_scores(batch, score_results)
                total_scored += saved
            except Exception as e:
                error_msg = f"Batch {batch_num}: {str(e)[:200]}"
                print(f"  [✗] ERROR: {error_msg}")
                total_errors += 1
                error_list.append(error_msg)

                # Fallback: thử từng bài một trong batch bị lỗi
                print(f"  [↻] Fallback: chấm từng bài trong batch {batch_num}...")
                for paper in batch:
                    try:
                        time.sleep(DELAY_BETWEEN_REQUESTS)
                        score_results = score_batch([paper], client)
                        saved = apply_scores([paper], score_results)
                        total_scored += saved
                    except Exception as e2:
                        error_msg2 = f"Paper #{paper.id}: {str(e2)[:150]}"
                        print(f"    [✗] Paper #{paper.id} ERROR: {str(e2)[:100]}")
                        total_errors += 1
                        error_list.append(error_msg2)

            # Delay giữa các batch để tránh rate limit
            if i + BATCH_SIZE < total:
                time.sleep(DELAY_BETWEEN_REQUESTS)

    result = {
        "total": total,
        "scored": total_scored,
        "errors": total_errors,
        "error_list": error_list,
    }
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Chấm điểm bài nghiên cứu bằng Gemini API (độc lập với AI summary)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Số lượng paper tối đa cần chấm (mặc định: tất cả bài chưa có điểm)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        dest="rescore_all",
        help="Chấm lại TẤT CẢ bài, kể cả những bài đã có điểm"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  PAPER SCORING - Đánh giá chất lượng bài nghiên cứu")
    print("=" * 60)

    result = run_scoring(limit=args.limit, rescore_all=args.rescore_all)

    print("\n" + "=" * 60)
    print("  KẾT QUẢ CHẤM ĐIỂM")
    print("=" * 60)
    print(f"  Tổng số bài cần chấm: {result['total']}")
    print(f"  Đã chấm thành công:   {result['scored']}")
    print(f"  Lỗi:                 {result['errors']}")

    if result["error_list"]:
        print("\n  Chi tiết lỗi:")
        for err in result["error_list"]:
            print(f"    - {err[:150]}")

    print("=" * 60)


if __name__ == "__main__":
    main()