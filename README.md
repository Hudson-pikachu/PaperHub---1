# PaperHub
PaperHub là một nền tảng tổng hợp và quản lý tài liệu nghiên cứu khoa học (Research Papers) từ nhiều nguồn uy tín về một giao diện duy nhất. Thay vì phải tìm kiếm rời rạc trên arXiv, PubMed hay IEEE, PaperHub giúp bạn tối ưu hóa quy trình nghiên cứu bằng cách tập trung mọi dữ liệu vào một "trạm trung chuyển" thông minh.
*/---------------/*
# Cấu Trúc Mã Nguồn
PaperHub được tổ chức theo mô hình **Flask Application** để tách biệt giữa cấu hình, dữ liệu và logic xử lý
Folder source sẽ có đầy đủ phần core code của PaperHub:
* `main.py`: Điểm khởi chạy ứng dụng (Entry Point). Thiết lập Host 0.0.0.0 hỗ trợ truy cập đa thiết bị.
* `config.py`: Quản lý cấu hình hệ thống. Đặc biệt có cơ chế Auto-fallback: tự động chuyển sang dùng SQLite (data.db) nếu kết nối MySQL server thất bại.
* `requirements.txt`: Danh sách toàn bộ thư viện cần thiết (Flask, SQLAlchemy, Google-GenAI, Arxiv API...).
* folder `app`
*   `routes.py`: Điều hướng trang giao diện của PaperHub (Home, Profile, Tab..)
*   `auth.py`: Xử lý Đăng ký / Đăng nhập
*   `admin.py`: Phần dành cho quản trị viên
*   `database`
*   `models.py`: Cấu trúc dữ liệu của các bài báo cáo của người dùng
*   `data.db`: Cơ sở dữ liệu của web (sử dụng SQLite)  
