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


def _parse_json_response_text(text: str) -> dict:
    json_text = text.strip()
    # Remove markdown code fences around JSON
    json_text = re.sub(r"^```(?:json)?\s*", "", json_text)
    json_text = re.sub(r"\s*```$", "", json_text)
    match = re.search(r"\{.*\}", json_text, re.S)
    if match:
        json_text = match.group(0)
    # Escape invalid JSON backslashes coming from LaTeX-like strings
    json_text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", json_text)
    return json.loads(json_text)


def translate_and_summarize_paper(paper_id: int, model: str = "gemini-2.5-flash-lite") -> Optional[Paper]:
    """Dịch tiêu đề và abstracts, tạo AI summary, đánh dấu status thành posted."""
    client = _get_client()

    paper = Paper.query.get(paper_id)
    if not paper:
        return None
    if paper.status == "posted":
        return paper

    prompt = f"""
Bạn là trợ lý dịch thuật kỹ thuật cho nội dung khoa học và AI.
Hãy dịch và viết lại tiêu đề sau sang tiếng Việt chuẩn thuật ngữ, tự nhiên, hấp dẫn, giữ nguyên ý chính của bài nghiên cứu.
Tiêu đề gốc:
{paper.title}

Tiếp theo, dịch abstract sau sang tiếng Việt tự nhiên, hấp dẫn, dễ đọc, nhưng vẫn giữ đúng nội dung khoa học.
Abstract gốc:
{paper.abstract}

Cuối cùng, tóm tắt ý quan trọng nhất của abstract bằng một đoạn văn ngắn gọn, rõ ràng, thiên về kết quả và đóng góp.
Trả về định dạng JSON sau:
{{
  "title": "...",
  "abstract": "...",
  "summary": "..."
}}
"""

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
        raise ValueError(f"Empty response from Google AI")
    
    try:
        output = _parse_json_response_text(result_text)
    except json.JSONDecodeError:
        raise ValueError(f"Không parse được JSON từ Google AI response: {result_text}")

    title = output.get("title", paper.title).strip()
    abstract = output.get("abstract", paper.abstract).strip()
    summary = output.get("summary", "").strip()

    paper.title = title
    paper.abstract = abstract
    paper.ai_summary = summary
    paper.status = "posted"

    db.session.add(paper)
    db.session.commit()
    return paper


def process_pending_papers(limit: int = 10, model: str = "gemini-2.5-flash-lite") -> int:
    """Process up to limit pending papers and mark them posted."""
    _get_client()  # Ensure client is initialized
    pending_papers = Paper.query.filter_by(status="pending").limit(limit).all()
    saved = 0
    for paper in pending_papers:
        translate_and_summarize_paper(paper.id, model=model)
        saved += 1
    return saved