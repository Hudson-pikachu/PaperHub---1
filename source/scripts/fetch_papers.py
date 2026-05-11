"""
Script CLI — Fetch arXiv papers thủ công.

Cách dùng:
    python scripts/fetch_papers.py                          # Mỗi category 2 bài
    python scripts/fetch_papers.py --per-category 5         # Mỗi category 5 bài
    python scripts/fetch_papers.py --category cs.LG         # Chỉ 1 category arXiv
    python scripts/fetch_papers.py --dry-run                # Chạy thử, không DB

Dùng cho:
  - Dev local: chạy tay khi cần lấy bài mới
  - Host shared (qua SSH): đặt cron job gọi script này định kỳ
    Ví dụ crontab: 0 */6 * * * cd /path/to/paperhub && python scripts/fetch_papers.py >> logs/cron.log 2>&1

Yêu cầu: chạy từ thư mục gốc PaperHub (nơi có source/).
"""

import sys
import os
import argparse
from datetime import datetime

# Thêm thư mục source/ vào sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, PROJECT_ROOT)

# Import app context
from app import create_app
from app.database.models import db, SchedulerState
from app.services.arxiv_service import fetch_arxiv_for_all_categories, fetch_arxiv_papers


def _set_last_run(run_time: datetime):
    """Ghi lại thời gian fetch cuối cùng."""
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
        help='Số bài tối đa mỗi category (mặc định: 2)'
    )
    parser.add_argument(
        '--category', type=str, default=None,
        help='Chỉ fetch 1 category arXiv (vd: cs.LG, cs.CL). Mặc định: fetch tất cả category đã cấu hình.'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Chạy thử: hiển thị số bài sẽ lấy, không ghi DB'
    )
    args = parser.parse_args()

    print(f"[{datetime.utcnow().isoformat()}] Bắt đầu fetch arXiv...")
    print(f"  per_category={args.per_category}, category={args.category or 'ALL'}, dry_run={args.dry_run}")

    app = create_app()

    with app.app_context():
        started_at = datetime.utcnow()
        try:
            if args.dry_run:
                print("[DRY RUN] Bỏ qua, không ghi DB.")
                print("[DRY RUN] Kết thúc.")
                return

            if args.category:
                saved, new_ids = fetch_arxiv_papers(query=args.category, max_results=args.per_category)
                if new_ids:
                    from app.services.ai_service import batch_translate_and_summarize
                    batch_translate_and_summarize(new_ids)
                total = saved
            else:
                total = fetch_arxiv_for_all_categories(per_category=args.per_category)

            _set_last_run(datetime.utcnow())
            elapsed = (datetime.utcnow() - started_at).seconds
            print(f"[{datetime.utcnow().isoformat()}] Hoàn tất. Đã lưu {total} bài mới. ({elapsed}s)")
        except Exception as e:
            print(f"[{datetime.utcnow().isoformat()}] LỖI: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()