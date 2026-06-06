import logging
from flask import Flask, jsonify
from flask_login import LoginManager
from .database.models import db, User
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


def create_app():
    app = Flask(__name__)

    # ── Cấu hình DB từ config.py (MySQL with SQLite fallback) ──
    app.config.from_object('config')
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

    # ── Context processor: inject unread_count vào tất cả templates ──
    from .database.models import Paper, UserPaperRead

    @app.context_processor
    def inject_unread_count():
        from flask_login import current_user
        if current_user.is_authenticated:
            since = current_user.created_at
            read_ids = [
                rp.paper_id for rp in
                UserPaperRead.query.filter_by(user_id=current_user.id).all()
            ]
            query = Paper.query.filter(
                Paper.status == 'posted',
                Paper.date_added > since
            )
            if read_ids:
                query = query.filter(~Paper.id.in_(read_ids))
            unread_count = query.count()
        else:
            unread_count = 0
        return {'unread_count': unread_count}

    # ── Đăng ký Blueprints ──
    from .routes import main_bp
    app.register_blueprint(main_bp)

    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .admin import admin_bp, public_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)

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

    return app