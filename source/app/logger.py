"""
Logging module cho PaperHub.

- Ghi tất cả WARNING / ERROR / CRITICAL ra file source/logs/app.log
- RotatingFileHandler: tối đa 5 MB/file, giữ 5 bản backup
- Format: [2026-05-10 07:38:25] ERROR in module: message
- Dev xem log qua route bí mật: GET /dev/logs?secret=<ADMIN_SECRET>
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# Thư mục logs nằm ở source/logs/ (cùng cấp với source/app/)
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
LOG_FILE = os.path.join(_LOG_DIR, 'app.log')

_FORMATTER = logging.Formatter(
    fmt='[%(asctime)s] %(levelname)-8s in %(module)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


def setup_logging(app) -> str:
    """
    Thiết lập ghi log ra file cho Flask app.
    Gắn handler vào app.logger và root logger (để bắt cả APScheduler, SQLAlchemy...).
    Trả về đường dẫn tuyệt đối tới file log.
    """
    os.makedirs(_LOG_DIR, exist_ok=True)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(_FORMATTER)

    # Flask app logger
    app.logger.setLevel(logging.WARNING)
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        app.logger.addHandler(file_handler)

    # Root logger — bắt lỗi từ thư viện ngoài (APScheduler, SQLAlchemy, arxiv, ...)
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(file_handler)

    app.logger.info(f"[Logger] Log file: {LOG_FILE}")
    return LOG_FILE


def get_last_lines(n: int = 100) -> list[str]:
    """Đọc n dòng cuối của file log. Trả về [] nếu chưa có log."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    return [line.rstrip() for line in lines[-n:]]


def get_log_stats() -> dict:
    """Trả về thông tin cơ bản về file log."""
    if not os.path.exists(LOG_FILE):
        return {'exists': False, 'size_kb': 0, 'total_lines': 0, 'path': LOG_FILE}
    size = os.path.getsize(LOG_FILE)
    with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
        total = sum(1 for _ in f)
    return {
        'exists': True,
        'size_kb': round(size / 1024, 2),
        'total_lines': total,
        'path': LOG_FILE,
    }
