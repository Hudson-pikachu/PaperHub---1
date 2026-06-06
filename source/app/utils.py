"""
Shared utility functions dùng chung cho toàn bộ PaperHub app.

Bao gồm:
- Unicode fix cho Windows stdout
- Helper ghi lịch sử fetch (dùng chung giữa admin.py & fetch_papers.py)
- Helper parse JSON response từ Gemini AI
"""

import sys
import io
import json
import re
from datetime import datetime


# ── Unicode fix cho Windows ──────────────────────────────────────────────────

def fix_windows_unicode():
    """Sửa lỗi UnicodeEncodeError trên Windows khi in tiếng Việt ra console."""
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        except Exception:
            pass


# ── Parse JSON từ Google AI / Gemini ────────────────────────────────────────

def parse_ai_json_response(text: str) -> list | dict:
    """Parse JSON từ response text của Google AI / Gemini.

    Hỗ trợ cả JSON object { ... } và JSON array [ ... ].
    Tự động xử lý markdown code fence, escape invalid backslashes,
    và fallback object bọc ngoài (vd: {{"results": [...]}}).

    Returns:
        list hoặc dict đã parse.
    """
    json_text = text.strip()

    # Remove markdown code fences
    json_text = re.sub(r"^```(?:json)?\s*", "", json_text)
    json_text = re.sub(r"\s*```$", "", json_text)

    # Match JSON array first, then JSON object
    match = re.search(r"\[.*\]", json_text, re.S)
    if not match:
        match = re.search(r"\{.*\}", json_text, re.S)
    if match:
        json_text = match.group(0)

    # Escape invalid JSON backslashes from LaTeX-like strings
    json_text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", json_text)

    return json.loads(json_text)


# ── Fetch history helpers ────────────────────────────────────────────────────

def safe_rollback(db):
    """Rollback DB session an toàn (chịu lỗi nếu session đã clean)."""
    try:
        db.session.rollback()
    except Exception:
        pass


def set_last_run(db, SchedulerState, run_time: datetime):
    """Ghi nhận thời điểm chạy fetch cuối cùng vào SchedulerState."""
    safe_rollback(db)
    state = SchedulerState.query.get(1)
    if not state:
        state = SchedulerState()
        state.id = 1
    state.last_run = run_time
    db.session.add(state)
    db.session.commit()


def log_fetch_history(db, FetchHistory, saved_count: int, per_category: int,
                      duration_seconds: int = 0, ai_processed: int = 0,
                      ai_error: str | None = None, error_message: str | None = None):
    """Ghi lịch sử fetch vào FetchHistory với session riêng, chịu lỗi."""
    safe_rollback(db)
    try:
        entry = FetchHistory()
        entry.saved_count = saved_count
        entry.per_category = per_category
        entry.duration_seconds = duration_seconds
        entry.ai_processed = ai_processed
        entry.ai_error = ai_error
        entry.error_message = error_message
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        print(f"[Utils] Failed to save fetch history: {e}")
        safe_rollback(db)