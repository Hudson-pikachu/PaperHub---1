"""
Cấu hình Database cho PaperHub - Tự động phát hiện MySQL với cơ chế dự phòng SQLite.
Nếu MySQL không khả dụng, hệ thống tự động chuyển sang SQLite (data.db)
và bật cờ thông báo để UI hiển thị banner cảnh báo.
"""

import os
from urllib.parse import quote_plus

# // --- Trạng thái toàn cục ---
# // Biến này lưu trữ việc hệ thống có đang phải dùng SQLite hay không
_FALLBACK_ACTIVE = False

# // --- Cấu hình MySQL ---
# // Thông tin kết nối đến server MySQL (thường là shared hosting)
DB_HOST = "paperhub.site"
DB_PORT = 3306
DB_USER = "ardvtlxg_paperhub"
DB_PASSWORD = "PaperHub@2026"
DB_NAME = "ardvtlxg_paperhub"

# // --- Đường dẫn file SQLite dự phòng ---
# // Tạo đường dẫn tuyệt đối đến file data.db nằm trong thư mục app/database
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'database', 'data.db')


def _get_mysql_uri():
    # // Hàm xây dựng chuỗi Connection URI cho MySQL
    # // quote_plus dùng để mã hóa các ký tự đặc biệt trong mật khẩu (như @, #, $)
    encoded_pw = quote_plus(DB_PASSWORD)
    return f"mysql+pymysql://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"


def _get_sqlite_uri():
    # // Hàm xây dựng chuỗi Connection URI cho SQLite
    return f"sqlite:///{SQLITE_PATH}"


def _test_mysql_connection():
    # // Hàm kiểm tra thực tế xem có kết nối được tới MySQL server không
    # // Thử mở một kết nối nhanh (timeout 5s), nếu lỗi thì coi như server sập
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
    # // Hàm quyết định sử dụng DB nào khi khởi chạy ứng dụng
    global _FALLBACK_ACTIVE

    if _test_mysql_connection():
        # // Nếu MySQL chạy tốt: Tắt cờ dự phòng và trả về URI MySQL
        _FALLBACK_ACTIVE = False
        return _get_mysql_uri()
    else:
        # // Nếu MySQL lỗi: Bật cờ dự phòng và dùng SQLite để app không bị crash
        _FALLBACK_ACTIVE = True
        print("[DB] MySQL unavailable, falling back to SQLite demo data.")
        return _get_sqlite_uri()


def is_fallback():
    # // Hàm helper để các phần khác (như UI) kiểm tra trạng thái database
    return _FALLBACK_ACTIVE


# // --- Flask session secret key ---
# // Chìa khóa bảo mật để mã hóa session (cần thiết cho đăng nhập)
SECRET_KEY = 'paperhub-secret-key-2026-change-in-production'

# // --- Cấu hình SQLAlchemy (Được thực thi ngay khi import file này) ---
# // 1. Xác định URI database (MySQL hoặc SQLite)
SQLALCHEMY_DATABASE_URI = get_db_uri()
# // 2. Tắt tính năng theo dõi thay đổi để tiết kiệm tài nguyên
SQLALCHEMY_TRACK_MODIFICATIONS = False

# // --- Cấu hình Connection Pool (Tối ưu cho Shared Hosting) ---
# // Shared hosting thường giới hạn số lượng kết nối đồng thời (~25-50)
SQLALCHEMY_ENGINE_OPTIONS = {
    # // Tự động làm mới kết nối sau 600 giây để tránh lỗi "MySQL server has gone away"
    # // Đặc biệt hữu ích khi xử lý các tác vụ AI tốn thời gian
    'pool_recycle': 600,
    
    # // Kiểm tra kết nối còn sống không trước khi thực hiện truy vấn (tránh lỗi ngắt quãng)
    'pool_pre_ping': True,
    
    # // Thời gian tối đa (10 giây) để chờ một kết nối trống từ hàng đợi
    'pool_timeout': 10,
    
    # // pool_size=2: Mỗi worker (tiến trình) giữ tối đa 2 kết nối cố định
    # // max_overflow=2: Cho phép tạo thêm tối đa 2 kết nối tạm thời khi quá tải
    # // Công thức: (pool_size + max_overflow) * số workers < giới hạn hosting
    'pool_size': 2,
    'max_overflow': 2,
}