"""
Admin Blueprint — Route bí mật chỉ dành cho dev & admin.
Không được expose công khai. Bảo vệ bằng ADMIN_SECRET token.

Routes quản lý fetch:
   GET  /dev/run-fetch?secret=<ADMIN_SECRET>              — Chạy fetch arXiv thủ công
   POST /dev/run-fetch  (Header: X-Admin-Secret)          — Chạy fetch (dùng cho cron job HTTP)
   GET  /dev/fetch-history?secret=<ADMIN_SECRET>          — Xem lịch sử fetch
   GET  /dev/settings?secret=<ADMIN_SECRET>                — Xem cấu hình fetch
   POST /dev/settings?secret=<ADMIN_SECRET>                — Cập nhật cấu hình fetch
   GET  /dev/status?secret=<ADMIN_SECRET>                 — Xem trạng thái scheduler
   GET  /dev/logs?secret=<ADMIN_SECRET>                   — Xem N dòng log cuối

Dùng cron job gọi HTTP endpoint /dev/run-fetch nếu host shared hỗ trợ.
Dùng script CLI `python scripts/fetch_papers.py` cho SSH cron job.

ADMIN_SECRET mặc định lấy từ env var ADMIN_SECRET.
Nếu không set env var, dùng giá trị fallback trong code (chỉ cho dev local).
"""

import os
from flask import Blueprint, request, jsonify, render_template_string
from datetime import datetime, timedelta
from .database.models import db, SchedulerState, FetchHistory, FetchConfig
from .services.arxiv_service import fetch_arxiv_for_all_categories
from .logger import get_last_lines, get_log_stats

# URL prefix không rõ ràng để tránh bị đoán
admin_bp = Blueprint('admin', __name__, url_prefix='/dev')

# Secret token — đặt env var ADMIN_SECRET trên host để override
_FALLBACK_SECRET = 'ph-dev-t0ken-2026!'
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', _FALLBACK_SECRET)

# ── HTML admin dashboard (inline, không cần file template riêng) ──
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
<h1 class="text-2xl font-bold mb-6">🔧 PaperHub - Quản lý Fetch</h1>

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
  <div class="bg-white p-4 rounded-lg shadow">
    <h2 class="font-semibold mb-2">Trạng thái</h2>
    <div id="status"><p class="text-gray-500">Đang tải...</p></div>
  </div>
  <div class="bg-white p-4 rounded-lg shadow">
    <h2 class="font-semibold mb-2">Cấu hình</h2>
    <div id="config-form">
      <label class="block text-sm mb-1">interval_hours</label>
      <input id="cfg-interval" type="number" class="border p-1 w-full mb-2 rounded" min="1" max="168">
      <label class="block text-sm mb-1">per_category</label>
      <input id="cfg-per-cat" type="number" class="border p-1 w-full mb-2 rounded" min="1" max="50">
      <label class="flex items-center gap-2 text-sm mb-3">
        <input id="cfg-enabled" type="checkbox"> Bật scheduler
      </label>
      <button onclick="saveConfig()" class="bg-blue-600 text-white px-4 py-1 rounded text-sm hover:bg-blue-700">Lưu</button>
      <span id="cfg-msg" class="text-sm ml-2"></span>
    </div>
  </div>
</div>

<div class="bg-white p-4 rounded-lg shadow mb-6">
  <div class="flex justify-between items-center mb-3">
    <h2 class="font-semibold">🚀 Fetch thủ công</h2>
    <div class="flex gap-2 items-center">
      <span class="text-sm">Mỗi category:</span>
      <input id="fetch-count" type="number" value="2" class="border p-1 w-16 rounded text-sm">
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

<div class="text-xs text-gray-400 space-y-1">
  <p>💡 Host shared: dùng cron job gọi <code class="bg-gray-200 px-1 rounded">curl "https://domain.com/dev/run-fetch?secret=..."</code></p>
  <p>💡 SSH cron job: dùng <code class="bg-gray-200 px-1 rounded">python scripts/fetch_papers.py</code></p>
  <p>💡 Cron mẫu (6h/lần): <code class="bg-gray-200 px-1 rounded">0 */6 * * * cd /path && python scripts/fetch_papers.py >> logs/cron.log 2>&1</code></p>
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
  el.innerHTML = `<p>🕐 Lần cuối: <b>${new Date(d.last_run).toLocaleString('vi-VN')}</b></p>` +
    (d.next_run ? `<p>⏭ Lần tới: <b>${new Date(d.next_run).toLocaleString('vi-VN')}</b></p>` : '') +
    (d.last_fetch ? `<p>📊 Gần nhất: ${d.last_fetch.saved_count} bài — <span class="${d.last_fetch.status === 'error' ? 'text-red-500' : 'text-green-500'}">${d.last_fetch.status}</span></p>` : '');
  if (d.config) {
    document.getElementById('cfg-interval').value = d.config.interval_hours;
    document.getElementById('cfg-per-cat').value = d.config.per_category;
    document.getElementById('cfg-enabled').checked = d.config.enabled;
  }
}

async function loadHistory() {
  const d = await api('/fetch-history?limit=20');
  const tbody = document.getElementById('history-body');
  if (!d.records || d.records.length === 0) { tbody.innerHTML = '<tr><td class="p-2 text-gray-500" colspan="5">Chưa có lịch sử.</td></tr>'; return; }
  tbody.innerHTML = d.records.map(r => `<tr class="border-t ${r.status === 'error' ? 'bg-red-50' : ''}">
    <td class="p-2">${r.id}</td>
    <td class="p-2">${r.started_at ? new Date(r.started_at).toLocaleString('vi-VN') : '-'}</td>
    <td class="p-2">${r.saved_count}</td>
    <td class="p-2">${r.duration_seconds}</td>
    <td class="p-2">${r.error_message ? `<span class="text-red-500" title="${r.error_message}">❌</span>` : '✅'}</td>
  </tr>`).join('');
}

async function runFetch() {
  const perCat = document.getElementById('fetch-count').value || 2;
  const el = document.getElementById('fetch-result');
  el.innerHTML = '<span class="text-blue-500">⏳ Đang fetch...</span>';
  const d = await api(`/run-fetch?per_category=${perCat}`);
  if (d.success) {
    el.innerHTML = `<span class="text-green-500">✅ ${d.message} (${d.elapsed_seconds}s)</span>`;
  } else {
    el.innerHTML = `<span class="text-red-500">❌ Lỗi: ${d.message}</span>`;
  }
  loadStatus();
  loadHistory();
}

async function saveConfig() {
  const body = JSON.stringify({
    interval_hours: parseInt(document.getElementById('cfg-interval').value) || 6,
    per_category: parseInt(document.getElementById('cfg-per-cat').value) || 2,
    enabled: document.getElementById('cfg-enabled').checked,
  });
  const d = await api('/settings', { method: 'POST', body });
  document.getElementById('cfg-msg').textContent = d.success ? '✅ Đã lưu' : '❌ ' + d.message;
  document.getElementById('cfg-msg').className = d.success ? 'text-sm ml-2 text-green-500' : 'text-sm ml-2 text-red-500';
  setTimeout(() => document.getElementById('cfg-msg').textContent = '', 3000);
}

loadStatus();
loadHistory();
</script>
</body>
</html>
'''


@admin_bp.route('')
@admin_bp.route('/dashboard')
def admin_dashboard():
    """Admin dashboard HTML."""
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401
    return render_template_string(_ADMIN_HTML)


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


def _log_fetch_history(saved_count: int, per_category: int, duration_seconds: int = 0, error_message: str | None = None):
    """Ghi lại một lần fetch vào lịch sử."""
    entry = FetchHistory()
    entry.saved_count = saved_count
    entry.per_category = per_category
    entry.duration_seconds = duration_seconds
    entry.error_message = error_message
    db.session.add(entry)
    db.session.commit()


def _get_or_create_config() -> FetchConfig:
    """Lấy hoặc tạo FetchConfig mặc định."""
    cfg = FetchConfig.query.get(1)
    if not cfg:
        cfg = FetchConfig()
        cfg.id = 1
        cfg.interval_hours = 6
        cfg.per_category = 2
        cfg.enabled = True
        db.session.add(cfg)
        db.session.commit()
    return cfg


@admin_bp.route('/run-fetch', methods=['GET', 'POST'])
def run_fetch():
    """
    Kích hoạt thủ công job fetch arXiv + dịch AI.
    - Cron job HTTP trên host shared: GET /dev/run-fetch?secret=<SECRET>
    - SSH cron job: dùng `python scripts/fetch_papers.py`
    """
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

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
        _log_fetch_history(saved_count=count, per_category=per_category, duration_seconds=elapsed)
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
        error_msg = str(e)
        print(f"[Admin] run-fetch lỗi: {error_msg}")
        _log_fetch_history(saved_count=0, per_category=per_category, error_message=error_msg)
        return jsonify({'success': False, 'message': error_msg}), 500


@admin_bp.route('/fetch-history', methods=['GET'])
def fetch_history():
    """Xem lịch sử các lần fetch gần nhất (mặc định 20 bản ghi)."""
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


@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """
    Xem / cập nhật cấu hình fetch.
    GET  — trả về cấu hình hiện tại
    POST — cập nhật cấu hình (body JSON)
    """
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    from flask import current_app

    if request.method == 'GET':
        cfg = _get_or_create_config()
        return jsonify({
            'success': True,
            'config': {
                'interval_hours': cfg.interval_hours,
                'per_category': cfg.per_category,
                'enabled': cfg.enabled,
            },
            'note': 'Cấu hình này chỉ dùng cho scheduler nội bộ (APScheduler). '
                    'Cron job HTTP / CLI dùng param riêng.',
        })

    # POST — cập nhật
    data = request.get_json(silent=True) or {}
    cfg = _get_or_create_config()

    if 'interval_hours' in data:
        val = int(data['interval_hours'])
        if val < 1 or val > 168:
            return jsonify({'success': False, 'message': 'interval_hours phải từ 1 đến 168.'}), 400
        cfg.interval_hours = val

    if 'per_category' in data:
        val = int(data['per_category'])
        if val < 1 or val > 50:
            return jsonify({'success': False, 'message': 'per_category phải từ 1 đến 50.'}), 400
        cfg.per_category = val

    if 'enabled' in data:
        cfg.enabled = bool(data['enabled'])

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Cấu hình đã được lưu.',
        'config': {
            'interval_hours': cfg.interval_hours,
            'per_category': cfg.per_category,
            'enabled': cfg.enabled,
        },
    })


@admin_bp.route('/status', methods=['GET'])
def status():
    """Xem trạng thái hệ thống: last_run, cấu hình, lịch sử gần nhất."""
    if not _check_secret():
        return jsonify({'success': False, 'message': '401 Unauthorized'}), 401

    state = SchedulerState.query.get(1)
    last_run = state.last_run if state else None
    next_run = (last_run + timedelta(hours=6)) if last_run else None

    # Lấy lịch sử gần nhất
    last_record = (
        FetchHistory.query
        .order_by(FetchHistory.started_at.desc())
        .first()
    )

    cfg = _get_or_create_config()

    return jsonify({
        'last_run': last_run.isoformat() if last_run else None,
        'next_run': next_run.isoformat() if next_run else None,
        'config': {
            'interval_hours': cfg.interval_hours,
            'per_category': cfg.per_category,
            'enabled': cfg.enabled,
        },
        'last_fetch': {
            'started_at': last_record.started_at.isoformat() if last_record and last_record.started_at else None,
            'finished_at': last_record.finished_at.isoformat() if last_record and last_record.finished_at else None,
            'saved_count': last_record.saved_count if last_record else 0,
            'status': 'error' if (last_record and last_record.error_message) else ('success' if last_record else 'never'),
            'error_message': last_record.error_message if last_record else None,
        } if last_record else None,
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

    if level_filter:
        raw_lines = [l for l in raw_lines if level_filter in l]

    return jsonify({
        'success': True,
        'stats': stats,
        'filter': level_filter or 'ALL',
        'showing': len(raw_lines),
        'lines': raw_lines,
    })