"""AI service module for Google AI translation and summarization."""

import json
from google import genai
from google.genai import types
from ..database.models import Paper, db
from ..utils import parse_ai_json_response

# Thay thế giá trị bên dưới bằng API key của bạn.
GOOGLE_API_KEY = "AIzaSyCy3K9OGxa7wQgPKz--Mo5esO-S1xDti_M"

# Global client instance
_client = None


def _get_client():
    global _client
    if _client is None:
        if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
            raise RuntimeError("GOOGLE_API_KEY must be configured directly in source/app/services/ai_service.py for this private project.")
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


def batch_translate_and_summarize(paper_ids: list, model: str = "gemini-2.5-flash-lite") -> int:
    """Dịch & tóm tắt nhiều bài trong MỘT lần gọi Google AI để tiết kiệm quota.

    Args:
        paper_ids: Danh sách ID các Paper cần xử lý (status="pending").
        model: Tên model Gemini.

    Returns:
        Số bài đã xử lý thành công (status → "posted").

    Logic:
        1. Load tất cả Paper từ DB, lọc bỏ bài đã posted hoặc không tồn tại.
        2. Gộp title + abstract của tất cả bài vào MỘT prompt duy nhất.
        3. Gọi Google AI 1 lần, yêu cầu trả về JSON array.
        4. Parse JSON array, phân phối kết quả về từng Paper tương ứng.
        5. Commit tất cả một lần.
    """
    if not paper_ids:
        return 0

    client = _get_client()

    # ── Bước 1: Load papers ──
    papers: list[Paper] = []
    for pid in paper_ids:
        paper = Paper.query.get(pid)
        if paper and paper.status != "posted":
            papers.append(paper)

    if not papers:
        return 0

    # ── Bước 2: Xây dựng prompt batch ──
    papers_json_blocks = []
    for i, paper in enumerate(papers):
        block = f"""
  {{
    "index": {i},
    "title_gốc": {json.dumps(paper.title, ensure_ascii=False)},
    "abstract_gốc": {json.dumps(paper.abstract or '', ensure_ascii=False)}
  }}"""
        papers_json_blocks.append(block.strip())

    papers_json_array = "[\n" + ",\n".join(papers_json_blocks) + "\n]"

    prompt = f"""Bạn là trợ lý dịch thuật kỹ thuật cho nội dung khoa học và AI.

QUY TẮC BẮT BUỘC:
- KHÔNG sử dụng bất kỳ ký hiệu toán học LaTeX nào (tuyệt đối không dùng $, $$, \\(...\\), \\[...\\], \\frac, \\sum, v.v.)
- Thay thế mọi công thức, ký hiệu toán học bằng LỜI VĂN tiếng Việt tự nhiên, dễ hiểu.
  Ví dụ: "$O(n \\log n)$" → "độ phức tạp O(n log n)" hoặc "thời gian chạy tỉ lệ với n nhân log n"
  Ví dụ: "$k$-MSR" → "bài toán k-MSR" hoặc viết rõ tên đầy đủ
- Giữ tên riêng, tên phương pháp, tên mô hình bằng tiếng Anh (ví dụ: GPT, BERT, Transformer)

Dưới đây là danh sách {len(papers)} bài nghiên cứu. Với MỖI bài, bạn cần:
1. Dịch tiêu đề sang tiếng Việt chuẩn thuật ngữ, tự nhiên, hấp dẫn.
2. Dịch abstract sang tiếng Việt tự nhiên, hấp dẫn, dễ đọc, giữ đúng nội dung khoa học.
3. Tóm tắt kết quả và đóng góp chính của nghiên cứu bằng ĐÚNG 2-3 CÂU tiếng Việt ngắn gọn, súc tích. KHÔNG dài hơn 3 câu. Chỉ nêu kết quả đạt được và ý nghĩa của nghiên cứu, không mô tả phương pháp.
4. Cung cấp phiên bản tiếng Anh: title_en giữ nguyên gốc (chỉ làm sạch LaTeX), abstract_en giữ nguyên gốc (chỉ làm sạch LaTeX), summary_en là bản tóm tắt ngắn gọn bằng tiếng Anh (2-3 câu).

Danh sách bài viết (JSON array):
{papers_json_array}

Trả về MỘT JSON array (KHÔNG có markdown code fence) với đúng {len(papers)} phần tử, mỗi phần tử là một object có định dạng:
{{
  "index": <số thứ tự khớp với input>,
  "title": "<tiêu đề tiếng Việt>",
  "abstract": "<abstract tiếng Việt>",
  "summary": "<tóm tắt tiếng Việt>",
  "title_en": "<tiêu đề tiếng Anh đã làm sạch>",
  "abstract_en": "<abstract tiếng Anh đã làm sạch>",
  "summary_en": "<tóm tắt tiếng Anh>"
}}

QUAN TRỌNG: Trả về ĐÚNG {len(papers)} phần tử, không thiếu, không thừa. Giữ nguyên thứ tự index."""

    # ── Bước 3: Gọi Google AI (1 lần duy nhất) ──
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        ),
    ]

    response = client.models.generate_content(
        model=f"models/{model}",
        contents=contents,
    )

    result_text = response.text if (hasattr(response, 'text') and response.text) else str(response)
    if not result_text:
        raise ValueError("Empty response from Google AI")

    # ── Bước 4: Parse JSON array ──
    try:
        raw_output = parse_ai_json_response(result_text)
    except json.JSONDecodeError:
        raise ValueError(f"Không parse được JSON từ Google AI response: {result_text}")

    # Hỗ trợ cả object bọc ngoài lẫn array trực tiếp
    if isinstance(raw_output, dict):
        # Có thể Gemini bọc trong {{ "results": [...] }}
        items = raw_output.get("results") or raw_output.get("papers") or []
        if not items:
            # Thử tìm key đầu tiên có value là list
            for v in raw_output.values():
                if isinstance(v, list):
                    items = v
                    break
    elif isinstance(raw_output, list):
        items = raw_output
    else:
        raise ValueError(f"JSON response không phải array hoặc object: {type(raw_output)}")

    if len(items) != len(papers):
        raise ValueError(
            f"Số lượng kết quả ({len(items)}) không khớp với số bài gửi đi ({len(papers)}). "
            f"Response: {result_text[:500]}"
        )

    # ── Bước 5: Phân phối kết quả về từng Paper ──
    saved = 0
    for item in items:
        idx = item.get("index", -1)
        if idx < 0 or idx >= len(papers):
            continue

        paper = papers[idx]

        title = (item.get("title") or "").strip()
        abstract = (item.get("abstract") or "").strip()
        summary = (item.get("summary") or "").strip()
        title_en = (item.get("title_en") or "").strip()
        abstract_en = (item.get("abstract_en") or "").strip()
        summary_en = (item.get("summary_en") or "").strip()

        if title:
            paper.title = title
        if abstract:
            paper.abstract = abstract
        if summary:
            paper.ai_summary = summary
        if title_en:
            paper.title_en = title_en
        if abstract_en:
            paper.abstract_en = abstract_en
        if summary_en:
            paper.ai_summary_en = summary_en
        paper.status = "posted"

        db.session.add(paper)
        saved += 1

    db.session.commit()
    return saved


def check_ai_status() -> dict:
    """Kiểm tra trạng thái Google AI API key (không gọi API, không tốn token).
    
    Thực tế: khi Fetch hoặc Process Pending chạy mới test thật.
    Returns:
        dict: {"ok": bool, "message": str}
    """
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        return {"ok": False, "message": "API key chưa được cấu hình."}
    try:
        _get_client()  # Kiểm tra xem có lỗi tạo client không
        return {"ok": True, "message": "API key đã được cấu hình. Test thật: bấm \"Xử lý bằng AI\"."}
    except Exception as e:
        return {"ok": False, "message": f"Lỗi khởi tạo client: {str(e)}"}


def process_pending_papers(limit: int = 12, model: str = "gemini-2.5-flash-lite", chunk_size: int = 6) -> int:
    """Xử lý tối đa limit bài pending, chia thành các batch nhỏ (chunk_size).

    Mỗi lần gọi Google AI xử lý tối đa chunk_size bài để tránh timeout.
    Ví dụ: 12 bài pending → chia 2 lần, mỗi lần 6 bài.
    """
    _get_client()
    pending_papers = Paper.query.filter_by(status="pending").limit(limit).all()
    if not pending_papers:
        return 0
    print(f"[AI] Found {len(pending_papers)} pending papers, chunk_size={chunk_size}")

    total_saved = 0
    for i in range(0, len(pending_papers), chunk_size):
        chunk = pending_papers[i:i + chunk_size]
        chunk_ids = [p.id for p in chunk]
        chunk_num = i // chunk_size + 1
        total_chunks = (len(pending_papers) + chunk_size - 1) // chunk_size
        print(f"[AI] Chunk {chunk_num}/{total_chunks}: {len(chunk)} papers")

        try:
            result = batch_translate_and_summarize(chunk_ids, model=model)
            total_saved += result
            print(f"[AI] Chunk {chunk_num}/{total_chunks} done: {result}/{len(chunk)}")
        except Exception as e:
            print(f"[AI] Chunk {chunk_num}/{total_chunks} batch error: {e}")
            # Fallback: xử lý từng bài trong chunk
            for paper in chunk:
                try:
                    result = batch_translate_and_summarize([paper.id], model=model)
                    if result > 0:
                        total_saved += result
                except Exception as e2:
                    print(f"[AI] Paper {paper.id} error: {e2}")
                    continue

    print(f"[AI] Total processed: {total_saved}/{len(pending_papers)}")
    return total_saved
