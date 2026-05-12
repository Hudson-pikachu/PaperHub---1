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
import argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.database.models import db, SchedulerState, FetchHistory
from app.services.arxiv_service import fetch_arxiv_for_all_categories, fetch_arxiv_papers


def _safe_rollback():
    """Rollback DB session an toàn (chịu lỗi nếu session đã clean)."""
    try:
        db.session.rollback()
    except Exception:
        pass


def _log_fetch_history(saved_count: int, per_category: int, duration_seconds: int = 0,
                        ai_processed: int = 0, ai_error: str | None = None,
                        error_message: str | None = None):
    """Ghi lịch sử vào FetchHistory với session riêng, chịu lỗi."""
    _safe_rollback()
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
    except Exception as log_err:
        print(f"[{datetime.utcnow().isoformat()}] WARNING: Failed to log history: {log_err}")
        _safe_rollback()


def _set_last_run(run_time: datetime):
    _safe_rollback()
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
        total = 0
        ai_processed = 0
        ai_error = None

        try:
            if args.dry_run:
                print("[DRY RUN] Bo qua, khong ghi DB.")
                print("[DRY RUN] Ket thuc.")
                return

            if args.category:
                saved, new_ids = fetch_arxiv_papers(query=args.category, max_results=args.per_category)
                total = saved
                if new_ids:
                    from app.services.ai_service import batch_translate_and_summarize
                    try:
                        ai_processed = batch_translate_and_summarize(new_ids)
                        print(f"  AI processed: {ai_processed}/{saved} papers")
                    except Exception as e:
                        ai_error = str(e)[:200]
                        print(f"  AI error: {e}")
            else:
                total, ai_processed, ai_error = fetch_arxiv_for_all_categories(per_category=args.per_category)
                print(f"  AI processed: {ai_processed}/{total} papers")
                if ai_error:
                    print(f"  AI error: {ai_error[:200]}")

            _set_last_run(datetime.utcnow())
            elapsed = (datetime.utcnow() - started_at).seconds

            # Ghi lich su vao FetchHistory
            _log_fetch_history(
                saved_count=total,
                per_category=args.per_category if not args.category else args.per_category,
                duration_seconds=elapsed,
                ai_processed=ai_processed,
                ai_error=ai_error,
            )

            print(f"[{datetime.utcnow().isoformat()}] Hoan tat. Da luu {total} bai moi. ({elapsed}s)")
        except Exception as e:
            elapsed = (datetime.utcnow() - started_at).seconds
            error_msg = str(e)
            print(f"[{datetime.utcnow().isoformat()}] LOI: {error_msg}", file=sys.stderr)
            # Rollback DB transaction trước khi log lỗi
            _safe_rollback()
            _log_fetch_history(
                saved_count=total,
                per_category=args.per_category if not args.category else args.per_category,
                duration_seconds=elapsed,
                ai_processed=ai_processed,
                ai_error=ai_error,
                error_message=error_msg,
            )
            sys.exit(1)


if __name__ == '__main__':
    main()