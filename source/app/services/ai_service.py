"""AI service module for Google AI translation and summarization."""

import json
import re
from typing import Optional
from google import genai
from google.genai import types
from ..database.models import Paper, db

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


def _parse_json_response_text(text: str):
    """Parse JSON từ response text của Google AI.

    Hỗ trợ cả JSON object { ... } và JSON array [ ... ].
    Có thể bị bọc trong markdown code fence.
    """
    json_text = text.strip()
    # Remove markdown code fences around JSON
    json_text = re.sub(r"^```(?:json)?\s*", "", json_text)
    json_text = re.sub(r"\s*```$", "", json_text)
    # Thử match JSON array trước, rồi đến JSON object
    match = re.search(r"\[.*\]", json_text, re.S)
    if not match:
        match = re.search(r"\{.*\}", json_text, re.S)
    if match:
        json_text = match.group(0)
    # Escape invalid JSON backslashes coming from LaTeX-like strings
    json_text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", json_text)
    return json.loads(json_text)


def translate_and_summarize_paper(paper_id: int, model: str = "gemini-2.5-flash-lite") -> int:
    """Dịch tiêu đề và abstracts, tạo AI summary, đánh dấu status thành posted.

.. deprecated::
    Hàm này gọi Google AI cho từng bài riêng lẻ, gây lãng phí quota.
    Nên dùng :func:`batch_translate_and_summarize` để gửi nhiều bài trong 1 lần gọi API.
    """
    return batch_translate_and_summarize([paper_id], model=model)


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
3. Tóm tắt ý quan trọng nhất của abstract bằng một đoạn văn ngắn gọn, thiên về kết quả và đóng góp (tiếng Việt).
4. Cung cấp phiên bản tiếng Anh: title_en giữ nguyên gốc (chỉ làm sạch LaTeX), abstract_en giữ nguyên gốc (chỉ làm sạch LaTeX), summary_en là bản tóm tắt ngắn gọn bằng tiếng Anh.

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
        raw_output = _parse_json_response_text(result_text)
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


def process_pending_papers(limit: int = 12, model: str = "gemini-2.5-flash-lite") -> int:
    """Xử lý tối đa limit bài pending trong 1 lần gọi batch Google AI.

    Gửi toàn bộ pending papers trong 1 prompt duy nhất để tiết kiệm quota.
    """
    _get_client()  # Ensure client is initialized
    pending_papers = Paper.query.filter_by(status="pending").limit(limit).all()
    if not pending_papers:
        return 0
    paper_ids = [p.id for p in pending_papers]
    try:
        return batch_translate_and_summarize(paper_ids, model=model)
    except Exception:
        # Nếu batch lỗi, fallback về xử lý từng bài để không mất hết
        saved = 0
        for paper in pending_papers:
            try:
                translate_and_summarize_paper(paper.id, model=model)
                saved += 1
            except Exception:
                continue
        return saved
