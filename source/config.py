"""
Database configuration for PaperHub - Auto-detects MySQL with SQLite fallback.

If MySQL is unavailable, automatically falls back to SQLite (data.db)
and sets a flag for the UI to show the warning banner.
"""

import os
from urllib.parse import quote_plus

# --- Global state ---
_FALLBACK_ACTIVE = False

# --- MySQL config ---
DB_HOST = "paperhub.site"
DB_PORT = 3306
DB_USER = "ardvtlxg_paperhub"
DB_PASSWORD = "PaperHub@2026"
DB_NAME = "ardvtlxg_paperhub"

# --- SQLite fallback path (relative to this file's directory) ---
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'database', 'data.db')


def _get_mysql_uri():
    """Build MySQL connection URI with URL-encoded password and charset."""
    encoded_pw = quote_plus(DB_PASSWORD)
    return f"mysql+pymysql://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"


def _get_sqlite_uri():
    """Build SQLite fallback connection URI."""
    return f"sqlite:///{SQLITE_PATH}"


def _test_mysql_connection():
    """Test if MySQL is reachable. Returns True if OK."""
    import pymysql
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
            connect_timeout=5
        )
        conn.close()
        return True
    except Exception:
        return False


def get_db_uri():
    """Get the appropriate database URI. Falls back to SQLite if MySQL is down."""
    global _FALLBACK_ACTIVE

    if _test_mysql_connection():
        _FALLBACK_ACTIVE = False
        return _get_mysql_uri()
    else:
        _FALLBACK_ACTIVE = True
        print("[DB] MySQL unavailable, falling back to SQLite demo data.")
        return _get_sqlite_uri()


def is_fallback():
    """Returns True if using SQLite fallback (MySQL was unavailable at startup)."""
    return _FALLBACK_ACTIVE


# --- Flask session secret key (bắt buộc cho Flask-Login) ---
SECRET_KEY = 'paperhub-secret-key-2026-change-in-production'

# --- SQLAlchemy settings (evaluated once at import time) ---
SQLALCHEMY_DATABASE_URI = get_db_uri()
SQLALCHEMY_TRACK_MODIFICATIONS = False

# --- Connection pool settings (tránh lỗi "MySQL server has gone away") ---
SQLALCHEMY_ENGINE_OPTIONS = {
    # Tái tạo connection sau 280 giây (trước khi MySQL server đóng sau 300s idle)
    'pool_recycle': 280,
    # Kiểm tra connection còn sống không trước mỗi lần dùng (SELECT 1)
    'pool_pre_ping': True,
    # Timeout khi chờ lấy connection từ pool
    'pool_timeout': 20,
    # Số connection tối đa trong pool
    'pool_size': 5,
    'max_overflow': 10,
}
