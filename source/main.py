import subprocess
import sys
import os
from app import create_app


# def ensure_dependencies():
#     """Kiểm tra và cài đặt các dependencies từ requirements.txt nếu chưa có."""
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     try:
#         result = subprocess.run(
#             [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
#             cwd=script_dir,
#             capture_output=True,
#             text=True,
#             timeout=300
#         )
#         if result.returncode != 0:
#             print(f"Warning: Cài đặt dependencies gặp lỗi: {result.stderr}")
#         else:
#             print("✓ Tất cả dependencies đã được cài đặt thành công")
#     except Exception as e:
#         print(f"Error: Không thể cài đặt dependencies: {e}")


app = create_app()

if __name__ == '__main__':
    # Kiểm tra và cài đặt dependencies trước khi chạy app
    # ensure_dependencies()
    # host='0.0.0.0' giúp bạn có thể truy cập từ thiết bị khác trong mạng LAN
    app.run(host='0.0.0.0', port=8080, debug=True)
