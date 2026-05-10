import os
from flask import Flask
from flask_apscheduler import APScheduler
from flask_login import LoginManager
from datetime import datetime, timedelta
from .database.models import db, SchedulerState, User
from .services.arxiv_service import fetch_arxiv_for_all_categories

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

    # ── Khởi tạo DB ──
    db.init_app(app)
    _ensure_db_schema(app)

    # ── Khởi tạo Flask-Login ──
    login_manager.init_app(app)
    login_manager.login_view = 'main.home'   # Redirect nếu chưa đăng nhập
    login_manager.login_message = 'Vui lòng đăng nhập để tiếp tục.'
    login_manager.login_message_category = 'info'

    # ── Đăng ký Blueprints ──
    from .routes import main_bp
    app.register_blueprint(main_bp)

    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .admin import admin_bp
    app.register_blueprint(admin_bp)

    # ── Cấu hình định kỳ fetch arXiv mỗi 6 tiếng ──
    scheduler = APScheduler()
    scheduler.init_app(app)

    def scheduled_fetch():
        """Job chạy mỗi 6 tiếng: lấy bài mới từ arXiv và dịch bằng AI."""
        with app.app_context():
            try:
                print(f"[Scheduler] Bắt đầu fetch arXiv lúc {datetime.utcnow().isoformat()}")
                count = fetch_arxiv_for_all_categories(per_category=2)
                _set_last_run(datetime.utcnow())
                print(f"[Scheduler] Hoàn tất. Đã lưu {count} bài mới.")
            except Exception as e:
                print(f"[Scheduler] Lỗi trong scheduled_fetch: {e}")

    with app.app_context():
        last_run = _get_last_run()

    if last_run:
        next_run = last_run + timedelta(hours=6)
        # Nếu đã quá hạn, chạy sau 60 giây (để app kịp khởi động xong)
        if next_run < datetime.utcnow():
            next_run = datetime.utcnow() + timedelta(seconds=60)
    else:
        # Lần đầu tiên: chạy sau 60 giây
        next_run = datetime.utcnow() + timedelta(seconds=60)

    scheduler.add_job(
        id='fetch_arxiv_every_6h',
        func=scheduled_fetch,
        trigger='interval',
        hours=6,
        next_run_time=next_run,
        max_instances=1,   # Không cho chạy chồng lên nhau
        coalesce=True,     # Gộp các lần bị bỏ lỡ thành 1 lần chạy duy nhất
        replace_existing=True,
    )

    # ── Bảo vệ: chỉ start scheduler khi được phép tường minh ──
    #
    # Vấn đề: nhiều instance app (host + các dev local) cùng chung 1 DB.
    # Nếu tất cả đều start scheduler → cùng 1 lúc N job chạy song song
    # → fetch arXiv + gọi Google AI N lần → ghi đè/trùng lặp vào DB.
    #
    # Giải pháp: scheduler MẶC ĐỊNH TẮT.
    # Chỉ bật khi set env var ENABLE_SCHEDULER=true — chỉ host chính mới set cái này.
    # Dev local không cần làm gì cả, scheduler tự động không chạy.
    #
    # Nếu host dùng Gunicorn multi-worker: chỉ set ENABLE_SCHEDULER=true
    # trên đúng 1 worker (dùng --workers 1, hoặc tách process riêng).
    enable_scheduler = os.environ.get('ENABLE_SCHEDULER', 'false').lower() == 'true'
    if enable_scheduler:
        if app.debug:
            # Flask debug mode: chỉ start trong process con của reloader (tránh chạy 2 lần)
            if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
                scheduler.start()
                print("[Scheduler] Đã start (debug mode).")
        else:
            scheduler.start()
            print("[Scheduler] Đã start (production mode).")
    else:
        print("[Scheduler] Đã TẮT. Set ENABLE_SCHEDULER=true trên host chính để bật.")

    return app
