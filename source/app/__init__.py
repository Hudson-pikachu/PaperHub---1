import os
import logging
from flask import Flask, jsonify
from flask_apscheduler import APScheduler
from flask_login import LoginManager
from datetime import datetime, timedelta
from .database.models import db, SchedulerState, User
from .services.arxiv_service import fetch_arxiv_for_all_categories
from .logger import setup_logging, get_logger

# Flask-Login manager (global để có thể dùng ở nơi khác nếu cần)
login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login callback: load user từ session."""
    return User.query.get(int(user_id))


def _ensure_db_schema(app):
    with app.app_context():
        db.create_all()


def _get_last_run():
    state = SchedulerState.query.get(1)
    return state.last_run if state else None


def _set_last_run(run_time: datetime):
    state = SchedulerState.query.get(1)
    if not state:
        state = SchedulerState()
        state.id = 1
    state.last_run = run_time
    db.session.add(state)
    db.session.commit()


def create_app():
    app = Flask(__name__)

    # ── Cấu hình DB từ config.py (MySQL with SQLite fallback) ──
    app.config.from_object('config')
    app.config['SCHEDULER_API_ENABLED'] = False
    app.config['SCHEDULER_TIMEZONE'] = 'Asia/Ho_Chi_Minh'
    # Secret key cho session (Flask-Login cần session)
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'paperhub-secret-key-2026-change-in-production'

    # ── Kiểm tra trạng thái fallback (MySQL / SQLite) ──
    from config import is_fallback
    app.config['DB_FALLBACK'] = is_fallback()

    # ── Thiết lập Logging ra file ──
    setup_logging(app)

    # ── Expose ADMIN_SECRET cho template (dùng trong link admin) ──
    from .admin import ADMIN_SECRET as _admin_secret
    app.config['ADMIN_SECRET'] = _admin_secret

    # ── Khởi tạo DB ──
    db.init_app(app)
    _ensure_db_schema(app)

    # ── Khởi tạo Flask-Login ──
    app.config['LOGIN_VIEW'] = 'main.home'
    app.config['LOGIN_MESSAGE'] = 'Vui lòng đăng nhập để tiếp tục.'
    app.config['LOGIN_MESSAGE_CATEGORY'] = 'info'
    login_manager.init_app(app)

    # ── Đăng ký Blueprints ──
    from .routes import main_bp
    app.register_blueprint(main_bp)

    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .admin import admin_bp
    app.register_blueprint(admin_bp)

    # ── Flask error handlers — ghi lỗi 500 ra file log ──
    # Dùng get_logger() thay vì app.logger để tránh bị Gunicorn override
    _log = get_logger()

    @app.errorhandler(500)
    def internal_error(error):
        _log.error(f"500 Internal Server Error: {error}", exc_info=True)
        return jsonify({'success': False, 'message': 'Lỗi server nội bộ.'}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        _log.error(f"Unhandled Exception [{type(error).__name__}]: {error}", exc_info=True)
        return jsonify({'success': False, 'message': 'Đã xảy ra lỗi không xác định.'}), 500

    @app.teardown_request
    def log_teardown_error(error):
        """Lưới an toàn thứ 2: bắt lỗi thoát khỏi error handlers."""
        if error is not None:
            _log.error(f"Teardown error [{type(error).__name__}]: {error}", exc_info=True)

    # ── Cấu hình scheduler nội bộ (CHỈ dùng cho debug/dev local) ──
    # Trên host shared: dùng cron job gọi HTTP endpoint /dev/run-fetch
    # Trên local: chạy script: python scripts/fetch_papers.py
    scheduler = APScheduler()
    scheduler.init_app(app)

    def scheduled_fetch():
        """Job chạy định kỳ: lấy bài mới từ arXiv và dịch bằng AI."""
        with app.app_context():
            try:
                _log.warning(f"[Scheduler] Bắt đầu fetch arXiv lúc {datetime.utcnow().isoformat()}")
                count = fetch_arxiv_for_all_categories(per_category=2)
                _set_last_run(datetime.utcnow())
                _log.warning(f"[Scheduler] Hoàn tất. Đã lưu {count} bài mới.")
            except Exception as e:
                _log.error(f"[Scheduler] Lỗi trong scheduled_fetch: {e}", exc_info=True)

    with app.app_context():
        last_run = _get_last_run()

    if last_run:
        next_run = last_run + timedelta(hours=6)
        if next_run < datetime.utcnow():
            next_run = datetime.utcnow() + timedelta(seconds=60)
    else:
        next_run = datetime.utcnow() + timedelta(seconds=60)

    scheduler.add_job(
        id='fetch_arxiv_every_6h',
        func=scheduled_fetch,
        trigger='interval',
        hours=6,
        next_run_time=next_run,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    # Bật scheduler nội bộ CHỈ khi debug=True (dev local)
    # Production / host shared: dùng cron job HTTP hoặc script CLI
    if app.debug:
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            scheduler.start()
            print("[Scheduler] STARTED (debug mode, chỉ dùng cho dev local).")
        else:
            print("[Scheduler] Waiting for reloader child process...")
    else:
        print("[Scheduler] DISABLED (production mode). Dùng cron job HTTP hoặc 'python scripts/fetch_papers.py'")

    return app