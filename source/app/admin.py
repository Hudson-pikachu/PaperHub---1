"""
Admin Blueprint — Route bí mật chỉ dành cho dev.
Không được expose công khai. Bảo vệ bằng ADMIN_SECRET token.

Routes:
  GET  /dev/run-fetch?secret=<ADMIN_SECRET>              — Chạy fetch arXiv thủ công
  GET  /dev/run-fetch?secret=<ADMIN_SECRET>&per_category=5
  POST /dev/run-fetch  (Header: X-Admin-Secret hoặc body JSON {"secret": ...})
  GET  /dev/status?secret=<ADMIN_SECRET>                 — Xem trạng thái scheduler
  GET  /dev/logs?secret=<ADMIN_SECRET>                   — Xem 100 dòng log cuối
  GET  /dev/logs?secret=<ADMIN_SECRET>&lines=200         — Xem N dòng log cuối

ADMIN_SECRET mặc định lấy từ env var ADMIN_SECRET.
Nếu không set env var, dùng giá trị fallback trong code (chỉ cho dev local).
"""

import os
from flask import Blueprint, request, jsonify
from datetime import datetime
from .database.models import db, SchedulerState
from .services.arxiv_service import fetch_arxiv_for_all_categories
from .logger import get_last_lines, get_log_stats

# URL prefix không rõ ràng để tránh bị đoán
admin_bp = Blueprint('admin', __name__, url_prefix='/dev')

# Secret token — đặt env var ADMIN_SECRET trên host để override
_FALLBACK_SECRET = 'ph-dev-t0ken-2026!'
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', _FALLBACK_SECRET)


def _check_secret() -> bool:
    """Kiểm tra secret từ query param hoặc header."""
    token = (
        request.args.get('secret')
        or request.headers.get('X-Admin-Secret')
        or (request.get_json(silent=True) or {}).get('secret')
    )
    return token == ADMIN_SECRET


def _set_last_run(run_time: datetime):
    state = SchedulerState.query.get(1)
    if not state:
        state = SchedulerState()
        state.id = 1
    state.last_run = run_time
    db.session.add(state)
    db.session.commit()


@admin_bp.route('/run-fetch', methods=['GET', 'POST'])
def run_fetch():
    """
    Kích hoạt thủ công job fetch arXiv + dịch AI.
    Trả về JSON với số bài đã lưu và thời gian chạy.
    """
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    # Số bài mỗi category — mặc định 2, có thể override qua param
    data = request.get_json(silent=True) or {}
    per_category = (
        request.args.get('per_category', type=int)
        or data.get('per_category')
        or 2
    )

    started_at = datetime.utcnow()
    print(f"[Admin] run-fetch triggered lúc {started_at.isoformat()}, per_category={per_category}")

    try:
        count = fetch_arxiv_for_all_categories(per_category=per_category)
        _set_last_run(datetime.utcnow())
        elapsed = (datetime.utcnow() - started_at).seconds
        print(f"[Admin] run-fetch hoàn tất: {count} bài mới, {elapsed}s")
        return jsonify({
            'success': True,
            'message': f'Fetch hoàn tất. Đã lưu {count} bài mới.',
            'saved': count,
            'per_category': per_category,
            'started_at': started_at.isoformat(),
            'elapsed_seconds': elapsed,
        })
    except Exception as e:
        print(f"[Admin] run-fetch lỗi: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/status', methods=['GET'])
def status():
    """Xem trạng thái scheduler: last_run, next_run dự kiến."""
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    from datetime import timedelta
    state = SchedulerState.query.get(1)
    last_run = state.last_run if state else None
    next_run = (last_run + timedelta(hours=6)) if last_run else None

    return jsonify({
        'last_run': last_run.isoformat() if last_run else None,
        'next_run': next_run.isoformat() if next_run else None,
        'scheduler_enabled': os.environ.get('ENABLE_SCHEDULER', 'false').lower() == 'true',
    })


@admin_bp.route('/logs', methods=['GET'])
def view_logs():
    """
    Xem N dòng cuối của file log.
    Query params:
      lines  — số dòng muốn xem (mặc định 100, tối đa 1000)
      level  — lọc theo từ khóa: ERROR, WARNING, CRITICAL (tuỳ chọn)
    """
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    lines_count = min(request.args.get('lines', 100, type=int), 1000)
    level_filter = request.args.get('level', '').upper()

    stats = get_log_stats()
    if not stats['exists']:
        return jsonify({
            'success': True,
            'message': 'Chưa có file log nào. App chưa ghi lỗi nào hoặc chưa được khởi động đủ lâu.',
            'stats': stats,
            'lines': [],
        })

    raw_lines = get_last_lines(lines_count)

    # Lọc theo level nếu có
    if level_filter:
        raw_lines = [l for l in raw_lines if level_filter in l]

    return jsonify({
        'success': True,
        'stats': stats,
        'filter': level_filter or 'ALL',
        'showing': len(raw_lines),
        'lines': raw_lines,
    })
