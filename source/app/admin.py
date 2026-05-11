"""
Admin Blueprint — Route bí mật dành cho dev & admin.
Bảo vệ bằng ADMIN_SECRET token.

Routes:
   GET  /dev?secret=<SECRET>                                 — Admin dashboard HTML
   GET  /dev/run-fetch?secret=<ADMIN_SECRET>                 — Fetch thủ công
   POST /dev/run-fetch  (Header: X-Admin-Secret)             — Fetch (dùng cho cron HTTP)
   GET  /dev/fetch-history?secret=<ADMIN_SECRET>             — Lịch sử fetch
   GET  /dev/status?secret=<ADMIN_SECRET>                    — Trạng thái fetch
   POST /dev/settings?secret=<ADMIN_SECRET>                  — Cập nhật cấu hình trang
   GET  /dev/logs?secret=<ADMIN_SECRET>                      — Xem N dòng log cuối

   GET  /site-settings                                       — Public API: cấu hình trang (không cần secret)

ADMIN_SECRET lấy từ env var ADMIN_SECRET.
Nếu không set, dùng fallback (chỉ cho dev local).
"""

import os
from flask import Blueprint, request, jsonify, render_template_string
from datetime import datetime, timedelta
from .database.models import db, SchedulerState, FetchHistory, SiteSettings
from .services.arxiv_service import fetch_arxiv_for_all_categories
from .logger import get_last_lines, get_log_stats

admin_bp = Blueprint('admin', __name__, url_prefix='/dev')

_FALLBACK_SECRET = 'ph-dev-t0ken-2026!'
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', _FALLBACK_SECRET)

# ── HTML admin dashboard ──
_ADMIN_HTML = r'''
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>PaperHub - Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 p-6">
<div class="max-w-4xl mx-auto">
<h1 class="text-2xl font-bold mb-6">🔧 PaperHub - Quản lý</h1>

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
  <div class="bg-white p-4 rounded-lg shadow">
    <h2 class="font-semibold mb-2">Trạng thái</h2>
    <div id="status"><p class="text-gray-500">Đang tải...</p></div>
  </div>
  <div class="bg-white p-4 rounded-lg shadow">
    <h2 class="font-semibold mb-2">Cấu hình trang</h2>
    <label class="flex items-center gap-2 text-sm">
      <input id="cfg-guest-load-more" type="checkbox" class="rounded">
      Cho phép "Xem thêm" khi chưa đăng nhập
    </label>
    <button onclick="saveSettings()" class="mt-3 bg-blue-600 text-white px-4 py-1 rounded text-sm hover:bg-blue-700">Lưu</button>
    <span id="cfg-msg" class="text-sm ml-2"></span>
  </div>
</div>

<div class="bg-white p-4 rounded-lg shadow mb-6">
  <div class="flex justify-between items-center mb-3">
    <h2 class="font-semibold">🚀 Fetch thủ công</h2>
    <div class="flex gap-2 items-center">
      <span class="text-sm">Mỗi category:</span>
      <input id="fetch-count" type="number" value="2" min="1" class="border p-1 w-16 rounded text-sm">
      <button onclick="runFetch()" class="bg-green-600 text-white px-4 py-1 rounded text-sm hover:bg-green-700">Chạy</button>
    </div>
  </div>
  <div id="fetch-result" class="text-sm"></div>
</div>

<div class="bg-white p-4 rounded-lg shadow mb-6">
  <h2 class="font-semibold mb-3">📋 Lịch sử fetch (20 gần nhất)</h2>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead><tr class="bg-gray-100"><th class="p-2 text-left">#</th><th class="p-2 text-left">Thời gian</th><th class="p-2 text-left">Bài lưu</th><th class="p-2 text-left">Thời gian (s)</th><th class="p-2 text-left">Trạng thái</th></tr></thead>
      <tbody id="history-body"><tr><td class="p-2 text-gray-500" colspan="5">Đang tải...</td></tr></tbody>
    </table>
  </div>
</div>
</div>

<script>
const SECRET = new URLSearchParams(location.search).get('secret') || '';
const BASE = '/dev';
function headers() { return { 'X-Admin-Secret': SECRET, 'Content-Type': 'application/json' }; }

async function api(url, opts={}) {
  const r = await fetch(BASE + url, { headers: headers(), ...opts });
  return r.json();
}

async function loadStatus() {
  const d = await api('/status');
  const el = document.getElementById('status');
  if (!d.last_run) { el.innerHTML = '<p class="text-gray-500">Chưa fetch lần nào.</p>'; return; }
  el.innerHTML = '<p>🕐 Lần cuối: <b>' + new Date(d.last_run).toLocaleString('vi-VN') + '</b></p>';
}

async function loadSettings() {
  const d = await api('/settings');
  if (d.settings) {
    document.getElementById('cfg-guest-load-more').checked = d.settings.guest_load_more;
  }
}

async function saveSettings() {
  const body = JSON.stringify({
    guest_load_more: document.getElementById('cfg-guest-load-more').checked,
  });
  const d = await api('/settings', { method: 'POST', body });
  const el = document.getElementById('cfg-msg');
  if (d.success) {
    el.textContent = '✅ Đã lưu';
    el.className = 'text-sm ml-2 text-green-500';
  } else {
    el.textContent = '❌ ' + d.message;
    el.className = 'text-sm ml-2 text-red-500';
  }
  setTimeout(function() { el.textContent = ''; }, 3000);
}

async function loadHistory() {
  const d = await api('/fetch-history?limit=20');
  const tbody = document.getElementById('history-body');
  if (!d.records || d.records.length === 0) { tbody.innerHTML = '<tr><td class="p-2 text-gray-500" colspan="5">Chưa có lịch sử.</td></tr>'; return; }
  tbody.innerHTML = d.records.map(function(r) {
    return '<tr class="border-t ' + (r.status === 'error' ? 'bg-red-50' : '') + '">' +
      '<td class="p-2">' + r.id + '</td>' +
      '<td class="p-2">' + (r.started_at ? new Date(r.started_at).toLocaleString('vi-VN') : '-') + '</td>' +
      '<td class="p-2">' + r.saved_count + '</td>' +
      '<td class="p-2">' + r.duration_seconds + '</td>' +
      '<td class="p-2">' + (r.error_message ? '<span class="text-red-500" title="' + r.error_message + '">❌</span>' : '✅') + '</td>' +
    '</tr>';
  }).join('');
}

async function runFetch() {
  const perCat = document.getElementById('fetch-count').value || 2;
  if (perCat < 1) {
    document.getElementById('fetch-result').innerHTML = '<span class="text-red-500">Số bài phải >= 1.</span>';
    return;
  }
  const el = document.getElementById('fetch-result');
  el.innerHTML = '<span class="text-blue-500">⏳ Đang fetch...</span>';
  const d = await api('/run-fetch?per_category=' + perCat);
  if (d.success) {
    el.innerHTML = '<span class="text-green-500">✅ ' + d.message + ' (' + d.elapsed_seconds + 's)</span>';
  } else {
    el.innerHTML = '<span class="text-red-500">❌ Lỗi: ' + d.message + '</span>';
  }
  loadStatus();
  loadHistory();
}

loadStatus();
loadSettings();
loadHistory();
</script>
</body>
</html>
'''


# ── Public API: trả cấu hình trang cho frontend (không cần secret) ──
public_bp = Blueprint('public_settings', __name__)


@public_bp.route('/site-settings')
def site_settings():
    settings = SiteSettings.query.get(1)
    return jsonify({
        'guest_load_more': settings.guest_load_more if settings else True,
    })


@admin_bp.route('')
@admin_bp.route('/dashboard')
def admin_dashboard():
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401
    return render_template_string(_ADMIN_HTML)


def _check_secret() -> bool:
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


def _log_fetch_history(saved_count: int, per_category: int, duration_seconds: int = 0, error_message: str | None = None):
    entry = FetchHistory()
    entry.saved_count = saved_count
    entry.per_category = per_category
    entry.duration_seconds = duration_seconds
    entry.error_message = error_message
    db.session.add(entry)
    db.session.commit()


def _get_or_create_settings() -> SiteSettings:
    cfg = SiteSettings.query.get(1)
    if not cfg:
        cfg = SiteSettings()
        cfg.id = 1
        cfg.guest_load_more = True
        db.session.add(cfg)
        db.session.commit()
    return cfg


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
            },
        })

    data = request.get_json(silent=True) or {}
    cfg = _get_or_create_settings()

    if 'guest_load_more' in data:
        cfg.guest_load_more = bool(data['guest_load_more'])

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

    started_at = datetime.utcnow()
    print(f"[Admin] run-fetch triggered at {started_at.isoformat()}, per_category={per_category}")

    try:
        count = fetch_arxiv_for_all_categories(per_category=per_category)
        _set_last_run(datetime.utcnow())
        elapsed = (datetime.utcnow() - started_at).seconds
        _log_fetch_history(saved_count=count, per_category=per_category, duration_seconds=elapsed)
        print(f"[Admin] run-fetch done: {count} papers, {elapsed}s")
        return jsonify({
            'success': True,
            'message': f'Fetch hoàn tất. Đã lưu {count} bài mới.',
            'saved': count,
            'per_category': per_category,
            'started_at': started_at.isoformat(),
            'elapsed_seconds': elapsed,
        })
    except Exception as e:
        error_msg = str(e)
        print(f"[Admin] run-fetch error: {error_msg}")
        _log_fetch_history(saved_count=0, per_category=per_category, error_message=error_msg)
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
                'started_at': r.started_at.isoformat() if r.started_at else None,
                'finished_at': r.finished_at.isoformat() if r.finished_at else None,
                'duration_seconds': r.duration_seconds,
                'saved_count': r.saved_count,
                'per_category': r.per_category,
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

    return jsonify({
        'last_run': last_run.isoformat() if last_run else None,
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