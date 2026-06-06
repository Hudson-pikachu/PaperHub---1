"""
Admin Blueprint — Route bí mật dành cho dev & admin.
Bảo vệ bằng ADMIN_SECRET token.

Routes:
   GET  /dev?secret=<SECRET>                                 — Admin dashboard HTML
   GET  /dev/run-fetch?secret=<ADMIN_SECRET>                 — Fetch thủ công
   POST /dev/run-fetch  (Header: X-Admin-Secret)             — Fetch (dùng cho cron HTTP)
   GET  /dev/process-pending?secret=<ADMIN_SECRET>           — Xử lý bài pending bằng AI
   GET  /dev/fetch-history?secret=<ADMIN_SECRET>             — Lịch sử fetch
   GET  /dev/status?secret=<ADMIN_SECRET>                    — Trạng thái fetch + AI
   POST /dev/settings?secret=<ADMIN_SECRET>                  — Cập nhật cấu hình trang
   GET  /dev/logs?secret=<ADMIN_SECRET>                      — Xem N dòng log cuối

   GET  /site-settings                                       — Public API: cấu hình trang
"""

import os
import sys
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime, timedelta, timezone
from .database.models import db, SchedulerState, FetchHistory, SiteSettings, Paper
from .services.arxiv_service import fetch_arxiv_for_all_categories
from .services.ai_service import check_ai_status, process_pending_papers
from .logger import get_last_lines, get_log_stats, read_log_file, read_log_file_stats
from .utils import set_last_run, log_fetch_history, safe_rollback

# Thêm thư mục scripts vào path để import được score_papers
_scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

admin_bp = Blueprint('admin', __name__, url_prefix='/dev')

_FALLBACK_SECRET = 'ph-dev-t0ken-2026!'
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', _FALLBACK_SECRET)

VN_TZ = timezone(timedelta(hours=7))


def _now_vn():
    return datetime.now(VN_TZ)


def _format_vn(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(VN_TZ).isoformat()


public_bp = Blueprint('public_settings', __name__)


@public_bp.route('/site-settings')
def site_settings():
    settings = SiteSettings.query.get(1)
    return jsonify({
        'guest_load_more': settings.guest_load_more if settings else True,
        'worthy_threshold': settings.worthy_threshold if settings else 7.0,
    })


@admin_bp.route('')
@admin_bp.route('/dashboard')
def admin_dashboard():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401
    return render_template('pages/admin.html')


def _check_secret() -> bool:
    token = (
        request.args.get('secret')
        or request.headers.get('X-Admin-Secret')
        or (request.get_json(silent=True) or {}).get('secret')
    )
    return token == ADMIN_SECRET




def _get_or_create_settings() -> SiteSettings:
    cfg = SiteSettings.query.get(1)
    if not cfg:
        cfg = SiteSettings()
        cfg.id = 1
        cfg.guest_load_more = True
        db.session.add(cfg)
        db.session.commit()
    return cfg


@admin_bp.route('/ai-status', methods=['GET'])
def ai_status():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401
    return jsonify(check_ai_status())


@admin_bp.route('/process-pending', methods=['GET', 'POST'])
def process_pending():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    count = request.args.get('count', 12, type=int) or 12
    pending_count = Paper.query.filter_by(status='pending').count()
    if pending_count == 0:
        return jsonify({'success': True, 'message': 'Không có bài pending.', 'processed': 0})

    started_at = _now_vn()
    print(f"[Admin] process-pending triggered at {started_at.isoformat()}, limit={count}, pending={pending_count}")

    try:
        saved = process_pending_papers(limit=count)
        set_last_run(db, SchedulerState, _now_vn())
        elapsed = (_now_vn() - started_at).seconds

        # Ghi lịch sử: rollback transaction AI cũ trước
        try:
            db.session.rollback()
        except Exception:
            pass
        ai_error_msg = None if saved >= pending_count else f'Only processed {saved}/{pending_count} papers'
        log_fetch_history(db, FetchHistory,
            saved_count=0, per_category=0, duration_seconds=elapsed,
            ai_processed=saved, ai_error=ai_error_msg,
        )
        print(f"[Admin] process-pending done: AI processed {saved}/{pending_count}, {elapsed}s")
        return jsonify({
            'success': True,
            'message': f'Đã xử lý {saved}/{pending_count} bài pending.',
            'processed': saved,
            'elapsed_seconds': elapsed,
        })
    except Exception as e:
        error_msg = str(e)
        print(f"[Admin] process-pending error: {error_msg}")
        log_fetch_history(db, FetchHistory, saved_count=0, per_category=0, ai_processed=0, ai_error=error_msg)
        return jsonify({'success': False, 'message': error_msg}), 500


@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    if request.method == 'GET':
        cfg = _get_or_create_settings()
        return jsonify({
            'success': True,
            'settings': {
                'guest_load_more': cfg.guest_load_more,
                'worthy_threshold': cfg.worthy_threshold,
            },
        })

    data = request.get_json(silent=True) or {}
    cfg = _get_or_create_settings()

    if 'guest_load_more' in data:
        cfg.guest_load_more = bool(data['guest_load_more'])
    if 'worthy_threshold' in data:
        val = data['worthy_threshold']
        if val is not None:
            cfg.worthy_threshold = max(0.0, min(10.0, float(val)))

    db.session.commit()
    return jsonify({'success': True, 'message': 'Đã lưu cấu hình.'})


@admin_bp.route('/run-fetch', methods=['GET', 'POST'])
def run_fetch():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    per_category = (
        request.args.get('per_category', type=int)
        or data.get('per_category')
        or 2
    )
    if per_category < 1:
        return jsonify({'success': False, 'message': 'Số bài mỗi category phải >= 1.'}), 400

    started_at = _now_vn()
    print(f"[Admin] run-fetch triggered at {started_at.isoformat()}, per_category={per_category}")

    try:
        count, ai_processed, ai_error = fetch_arxiv_for_all_categories(per_category=per_category)
        set_last_run(db, SchedulerState, _now_vn())
        elapsed = (_now_vn() - started_at).seconds
        log_fetch_history(db, FetchHistory,
            saved_count=count, per_category=per_category, duration_seconds=elapsed,
            ai_processed=ai_processed, ai_error=ai_error,
        )
        print(f"[Admin] run-fetch done: {count} papers, AI: {ai_processed}, {elapsed}s")
        msg = f'Fetch hoàn tất. Đã lưu {count} bài mới.'
        if ai_error:
            msg += f' AI lỗi: {ai_error[:100]}'
        return jsonify({
            'success': True,
            'message': msg,
            'saved': count,
            'per_category': per_category,
            'started_at': started_at.isoformat(),
            'elapsed_seconds': elapsed,
            'ai_processed': ai_processed,
            'ai_error': ai_error,
        })
    except Exception as e:
        error_msg = str(e)
        print(f"[Admin] run-fetch error: {error_msg}")
        log_fetch_history(db, FetchHistory, saved_count=0, per_category=per_category, error_message=error_msg)
        return jsonify({'success': False, 'message': error_msg}), 500


@admin_bp.route('/fetch-history', methods=['GET'])
def fetch_history():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    limit = min(request.args.get('limit', 20, type=int), 100)
    records = (
        FetchHistory.query
        .order_by(FetchHistory.started_at.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        'success': True,
        'records': [
            {
                'id': r.id,
                'started_at': _format_vn(r.started_at),
                'finished_at': _format_vn(r.finished_at),
                'duration_seconds': r.duration_seconds,
                'saved_count': r.saved_count,
                'per_category': r.per_category,
                'ai_processed': r.ai_processed,
                'ai_error': r.ai_error,
                'error_message': r.error_message,
                'status': 'error' if r.error_message else 'success',
            }
            for r in records
        ],
    })


@admin_bp.route('/status', methods=['GET'])
def status():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    state = SchedulerState.query.get(1)
    last_run = state.last_run if state else None
    pending_count = Paper.query.filter_by(status='pending').count()

    return jsonify({
        'last_run': _format_vn(last_run) if last_run else None,
        'pending_count': pending_count,
    })


@admin_bp.route('/cron-log', methods=['GET'])
def view_cron_log():
    """Đọc N dòng cuối của file cron.log (cron job output)."""
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    lines_count = min(request.args.get('lines', 50, type=int), 500)
    cron_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs', 'cron.log')
    cron_log_path = os.path.normpath(cron_log_path)

    stats = read_log_file_stats(cron_log_path)
    if not stats['exists']:
        return jsonify({
            'success': True,
            'message': 'Chưa có file cron.log nào.',
            'stats': stats,
            'lines': [],
        })

    raw_lines = read_log_file(cron_log_path, lines_count)
    return jsonify({
        'success': True,
        'stats': stats,
        'showing': len(raw_lines),
        'lines': raw_lines,
    })


@admin_bp.route('/logs', methods=['GET'])
def view_logs():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    lines_count = min(request.args.get('lines', 100, type=int), 1000)
    level_filter = request.args.get('level', '').upper()

    stats = get_log_stats()
    if not stats['exists']:
        return jsonify({
            'success': True,
            'message': 'Chưa có file log nào.',
            'stats': stats,
            'lines': [],
        })

    raw_lines = get_last_lines(lines_count)

    if level_filter:
        raw_lines = [l for l in raw_lines if level_filter in l]

    return jsonify({
        'success': True,
        'stats': stats,
        'filter': level_filter or 'ALL',
        'showing': len(raw_lines),
        'lines': raw_lines,
    })


@admin_bp.route('/score-papers', methods=['GET', 'POST'])
def score_papers():
    """Gọi Gemini API chấm điểm các bài chưa có score."""
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    # Count unscored
    unscored_count = Paper.query.filter(Paper.score.is_(None)).count()
    if unscored_count == 0:
        return jsonify({'success': True, 'message': 'Tất cả bài đã có điểm.', 'scored': 0, 'total': 0})

    started_at = _now_vn()
    print(f"[Admin] score-papers triggered at {started_at.isoformat()}, unscored={unscored_count}")

    try:
        from score_papers import run_scoring  # type: ignore[import-not-found]
        result = run_scoring(limit=None, rescore_all=False)
        elapsed = (_now_vn() - started_at).seconds

        time_suffix = " ({elapsed}s)".format(elapsed=elapsed) if elapsed else ""
        msg = "Đã chấm {scored}/{total} bài{time_suffix}.".format(
            scored=result["scored"], total=result["total"], time_suffix=time_suffix
        )
        if result.get("errors"):
            msg += " Lỗi: {errors} bài.".format(errors=result["errors"])
        print(f"[Admin] score-papers done: {result}")

        return jsonify({
            'success': True,
            'message': msg,
            'scored': result['scored'],
            'total': result['total'],
            'errors': result.get('errors', 0),
            'elapsed_seconds': elapsed,
        })
    except Exception as e:
        error_msg = str(e)
        print(f"[Admin] score-papers error: {error_msg}")
        return jsonify({'success': False, 'message': error_msg}), 500
