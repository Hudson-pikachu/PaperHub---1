"""
Script CLI — Fetch arXiv papers thu cong.

Cach dung:
    python scripts/fetch_papers.py                          # Moi category 2 bai
    python scripts/fetch_papers.py --per-category 5         # Moi category 5 bai
    python scripts/fetch_papers.py --category cs.LG         # Chi 1 category arXiv
    python scripts/fetch_papers.py --dry-run                # Chay thu, khong DB

Dung cho:
  - Dev local: chay tay khi can lay bai moi
  - Host shared (qua SSH): dat cron job goi script nay dinh ky
    Vi du crontab: 0 */6 * * * cd /path/to/paperhub && python scripts/fetch_papers.py >> logs/cron.log 2>&1

Yeu cau: chay tu thu muc goc PaperHub (noi co source/).
"""

import sys
import os
import io
import argparse
from datetime import datetime

# Fix UnicodeEncodeError trên Windows: 'ascii' codec can't encode Vietnamese chars
# Python mặc định dùng cp1252/ascii cho stdout → không encode được tiếng Việt (vd: "Học Máy")
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.database.models import db, SchedulerState, FetchHistory
from app.services.arxiv_service import fetch_arxiv_for_all_categories, fetch_arxiv_papers


def _set_last_run(run_time: datetime):
    state = SchedulerState.query.get(1)
    if not state:
        state = SchedulerState()
        state.id = 1
    state.last_run = run_time
    db.session.add(state)
    db.session.commit()


def main():
    parser = argparse.ArgumentParser(description='Fetch papers from arXiv')
    parser.add_argument(
        '--per-category', type=int, default=2,
        help='So bai toi da moi category (mac dinh: 2)'
    )
    parser.add_argument(
        '--category', type=str, default=None,
        help='Chi fetch 1 category arXiv (vd: cs.LG, cs.CL). Mac dinh: fetch tat ca category da cau hinh.'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Chay thu: hien thi so bai se lay, khong ghi DB'
    )
    args = parser.parse_args()

    print(f"[{datetime.utcnow().isoformat()}] Bat dau fetch arXiv...")
    print(f"  per_category={args.per_category}, category={args.category or 'ALL'}, dry_run={args.dry_run}")

    app = create_app()

    with app.app_context():
        started_at = datetime.utcnow()
        try:
            if args.dry_run:
                print("[DRY RUN] Bo qua, khong ghi DB.")
                print("[DRY RUN] Ket thuc.")
                return

            if args.category:
                saved, new_ids = fetch_arxiv_papers(query=args.category, max_results=args.per_category)
                if new_ids:
                    from app.services.ai_service import batch_translate_and_summarize
                    try:
                        ai_processed = batch_translate_and_summarize(new_ids)
                        print(f"  AI processed: {ai_processed}/{saved} papers")
                    except Exception as e:
                        print(f"  AI error: {e}")
                total = saved
            else:
                total, ai_processed, ai_error = fetch_arxiv_for_all_categories(per_category=args.per_category)
                print(f"  AI processed: {ai_processed}/{total} papers")
                if ai_error:
                    print(f"  AI error: {ai_error[:100]}")

            _set_last_run(datetime.utcnow())
            elapsed = (datetime.utcnow() - started_at).seconds

            # Ghi lich su vao FetchHistory (de xem tren admin dashboard)
            ai_processed_val = ai_processed if 'ai_processed' in dir() else 0
            ai_error_val = ai_error if 'ai_error' in dir() else None
            try:
                entry = FetchHistory()
                entry.saved_count = total
                entry.per_category = args.per_category if not args.category else args.per_category
                entry.duration_seconds = elapsed
                entry.ai_processed = ai_processed_val
                entry.ai_error = ai_error_val
                db.session.add(entry)
                db.session.commit()
            except Exception as log_err:
                print(f"[{datetime.utcnow().isoformat()}] WARNING: Failed to log history: {log_err}")

            print(f"[{datetime.utcnow().isoformat()}] Hoan tat. Da luu {total} bai moi. ({elapsed}s)")
        except Exception as e:
            print(f"[{datetime.utcnow().isoformat()}] LOI: {e}", file=sys.stderr)
            # Log error to FetchHistory too
            try:
                entry = FetchHistory()
                entry.saved_count = 0
                entry.per_category = args.per_category if not args.category else args.per_category
                entry.duration_seconds = 0
                entry.error_message = str(e)
                db.session.add(entry)
                db.session.commit()
            except Exception:
                pass
            sys.exit(1)


if __name__ == '__main__':
    main()