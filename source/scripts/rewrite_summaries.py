"""
Script one-time: Rewrite AI summaries for papers ID 1-36.

- Only updates ai_summary + ai_summary_en (keeps title, abstract, status)
- Chunk 6 papers per Google AI call
- New prompt: results-focused, 2-3 sentences max

Usage:
    python scripts/rewrite_summaries.py                  # Default: papers 1-36
    python scripts/rewrite_summaries.py --dry-run        # Dry run, no DB write
"""

import sys
import os
import json
import re
import argparse
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.database.models import db, Paper
from google import genai
from google.genai import types

GOOGLE_API_KEY = "AIzaSyCy3K9OGxa7wQgPKz--Mo5esO-S1xDti_M"
CHUNK_SIZE = 6
MODEL = "models/gemini-2.5-flash-lite"


def _parse_json_response_text(text: str):
    json_text = text.strip()
    json_text = re.sub(r"^```(?:json)?\s*", "", json_text)
    json_text = re.sub(r"\s*```$", "", json_text)
    match = re.search(r"\[.*\]", json_text, re.S)
    if not match:
        match = re.search(r"\{.*\}", json_text, re.S)
    if match:
        json_text = match.group(0)
    json_text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", json_text)
    return json.loads(json_text)


def rewrite_chunk(client, papers: list[Paper]) -> int:
    """Send 1 chunk to Google AI, get 2-3 sentence summaries."""
    blocks = []
    for i, paper in enumerate(papers):
        blocks.append({
            "index": i,
            "title": paper.title_en or paper.title,
            "abstract": (paper.abstract_en or paper.abstract or '')[:1500],
        })

    prompt = f"""You are a scientific content summarizer.

Below are {len(papers)} research papers. For EACH paper, write a summary in Vietnamese of EXACTLY 2-3 sentences:
- ONLY state the achieved results and significance of the research
- DO NOT describe methods, DO NOT introduce background
- Go straight to the conclusion, concise and impactful
- Also provide summary_en (English version, also 2-3 sentences)

Input (JSON array):
{json.dumps(blocks, ensure_ascii=False, indent=2)}

Return ONE JSON array (NO markdown fence) with exactly {len(papers)} items:
[
  {{
    "index": 0,
    "summary": "<2-3 sentence summary in Vietnamese>",
    "summary_en": "<2-3 sentence summary in English>"
  }},
  ...
]"""

    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
    )
    result_text = response.text if (hasattr(response, 'text') and response.text) else ''
    if not result_text:
        raise ValueError("Empty response from Google AI")

    items = []
    raw = _parse_json_response_text(result_text)
    if isinstance(raw, dict):
        items = raw.get("results") or raw.get("papers") or []
        if not items:
            for v in raw.values():
                if isinstance(v, list):
                    items = v
                    break
    elif isinstance(raw, list):
        items = raw

    if len(items) != len(papers):
        raise ValueError(f"Mismatch: got {len(items)}, expected {len(papers)}")

    saved = 0
    for item in items:
        idx = item.get("index", -1)
        if idx < 0 or idx >= len(papers):
            continue
        paper = papers[idx]
        summary = (item.get("summary") or "").strip()
        summary_en = (item.get("summary_en") or "").strip()
        if summary:
            paper.ai_summary = summary
        if summary_en:
            paper.ai_summary_en = summary_en
        db.session.add(paper)
        saved += 1

    db.session.commit()
    return saved


def main():
    parser = argparse.ArgumentParser(description='Rewrite AI summaries to 2-3 sentences')
    parser.add_argument('--dry-run', action='store_true', help='Dry run, no DB write')
    args = parser.parse_args()

    app = create_app()
    client = genai.Client(api_key=GOOGLE_API_KEY)

    with app.app_context():
        query = Paper.query.filter(
            Paper.status == 'posted',
            Paper.id >= 1,
            Paper.id <= 36,
        )
        papers = query.all()

        if not papers:
            print("No papers to process.")
            return

        print(f"Found {len(papers)} posted papers. Chunk size = {CHUNK_SIZE}")

        if args.dry_run:
            print("[DRY RUN] Skip DB write.")
            total_chunks = (len(papers) + CHUNK_SIZE - 1) // CHUNK_SIZE
            for i in range(0, min(len(papers), 12), CHUNK_SIZE):
                chunk = papers[i:i + CHUNK_SIZE]
                print(f"  Chunk {i // CHUNK_SIZE + 1}/{total_chunks}: {len(chunk)} papers")
                for p in chunk:
                    print(f"    - {p.title_en[:60] if p.title_en else p.title[:60]}...")
            return

        total_saved = 0
        total_chunks = (len(papers) + CHUNK_SIZE - 1) // CHUNK_SIZE

        for i in range(0, len(papers), CHUNK_SIZE):
            chunk = papers[i:i + CHUNK_SIZE]
            chunk_num = i // CHUNK_SIZE + 1
            print(f"\nChunk {chunk_num}/{total_chunks}: {len(chunk)} papers")

            try:
                saved = rewrite_chunk(client, chunk)
                total_saved += saved
                print(f"  OK: {saved}/{len(chunk)}")
            except Exception as e:
                error_str = str(e)
                print(f"  ERROR: {error_str[:200]}")
                # Nếu quota exceeded (429), đợi 50s rồi retry cả chunk
                if 'RESOURCE_EXHAUSTED' in error_str or '429' in error_str:
                    print(f"  Quota exceeded. Waiting 50s before retry...")
                    time.sleep(50)
                    try:
                        saved = rewrite_chunk(client, chunk)
                        total_saved += saved
                        print(f"  Retry OK: {saved}/{len(chunk)}")
                    except Exception as e2:
                        print(f"  Retry ERROR: {e2}")
                # Nếu lỗi khác, fallback từng bài (không retry)
                else:
                    for paper in chunk:
                        try:
                            saved = rewrite_chunk(client, [paper])
                            total_saved += saved
                            print(f"  OK (single): paper {paper.id}")
                        except Exception as e2:
                            print(f"  ERROR paper {paper.id}: {e2}")

        print(f"\nDone. Updated {total_saved}/{len(papers)} papers.")


if __name__ == '__main__':
    main()