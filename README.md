# PaperHub
PaperHub là một nền tảng tổng hợp và quản lý tài liệu nghiên cứu khoa học (Research Papers) từ nhiều nguồn uy tín về một giao diện duy nhất. Thay vì phải tìm kiếm rời rạc trên arXiv, PubMed hay IEEE, PaperHub giúp bạn tối ưu hóa quy trình nghiên cứu bằng cách tập trung mọi dữ liệu vào một "trạm trung chuyển" thông minh.

---

# Cấu Trúc Mã Nguồn

PaperHub được tổ chức theo mô hình **Flask Application** để tách biệt giữa cấu hình, dữ liệu và logic xử lý.

## Thư mục gốc (`/`)

| File / Folder | Công dụng |
|---|---|
| `README.md` | Tài liệu hướng dẫn và mô tả cấu trúc dự án |
| `.gitignore` | Danh sách file/folder bị Git bỏ qua (logs, cache, venv, data.db...) |
| `docs/` | Thư mục chứa tài liệu dự án (kế hoạch, biên bản, yêu cầu, sơ đồ) |
| `docs/brief_plan.md` | Kế hoạch tổng quan dự án |
| `docs/minutes_log.md` | Nhật ký biên bản các cuộc họp / quyết định |
| `docs/project_requirements.md` | Yêu cầu chức năng và phi chức năng của dự án |
| `docs/diagrams/` | Sơ đồ (Flowchart, ERD, Use Case...) |
| `source/` | Toàn bộ mã nguồn chính của ứng dụng |

---

## `source/` — Mã nguồn ứng dụng

### Entry Point & Cấu Hình

| File | Công dụng |
|---|---|
| `main.py` | **Điểm khởi chạy ứng dụng** (Entry Point). Gọi `create_app()` từ `app/__init__.py` và chạy Flask dev server với Host `0.0.0.0` để hỗ trợ truy cập đa thiết bị trong mạng LAN. |
| `config.py` | **Quản lý cấu hình hệ thống**. Chứa `SQLALCHEMY_DATABASE_URI`, `SECRET_KEY` và các biến môi trường. Có cơ chế **Auto-fallback**: tự động chuyển sang dùng SQLite (`data.db`) nếu kết nối MySQL server thất bại, giúp app luôn chạy được ngay cả khi không có MySQL. |
| `requirements.txt` | Danh sách toàn bộ thư viện Python cần thiết: `Flask`, `Flask-SQLAlchemy`, `Flask-Login`, `Flask-APScheduler`, `google-genai`, `arxiv`, `pymysql`, `cryptography`, `python-dotenv`... |

### `app/` — Core Application Package

#### Khởi tạo & Cấu hình App

| File | Công dụng |
|---|---|
| `__init__.py` | **Hàm factory `create_app()`**: khởi tạo Flask app, cấu hình database, Flask-Login, đăng ký Blueprints, thiết lập scheduler tự động fetch arXiv mỗi 6 tiếng, gắn error handlers. Đây là "bộ não" kết nối tất cả thành phần của app. |

#### Điều hướng & API (Routes)

| File | Công dụng |
|---|---|
| `routes.py` | **Điều hướng chính của PaperHub**. Chứa tất cả route: trang chủ `/`, `/profile`, `/load-more` (load thêm bài infinite scroll), `/scheduler-status` (trạng thái scheduler), `/save-paper` (bookmark toggle), `/saved-papers` (danh sách đã lưu), `/toggle-follow` (theo dõi chủ đề), `/following-papers` (bài viết theo chủ đề đã follow), `/followed-categories` (danh sách ID chủ đề đã follow). |
| `auth.py` | **Xử lý xác thực người dùng**: Đăng ký (`/auth/register`), Đăng nhập (`/auth/login`), Đăng xuất (`/auth/logout`). Sử dụng `Flask-Login` để quản lý session. |
| `admin.py` | **Trang quản trị**: dành cho quản trị viên (đang phát triển). |

#### Dịch vụ (Services)

| File | Công dụng |
|---|---|
| `services/arxiv_service.py` | **Fetch bài viết từ arXiv API**: gọi arXiv API theo danh mục (category), parse XML response, lưu bài mới vào database với status `pending`. Hỗ trợ fetch theo danh mục (`fetch_arxiv_for_all_categories`). |
| `services/ai_service.py` | **Dịch vụ AI (Google Gemini)**: dùng Google Generative AI API để tạo tóm tắt tiếng Việt (`ai_summary`) cho abstract của bài nghiên cứu. |

#### Cơ sở dữ liệu (Database)

| File / Folder | Công dụng |
|---|---|
| `database/models.py` | **Định nghĩa tất cả Model (bảng) của hệ thống**: `Category` (danh mục), `Paper` (bài viết), `User` (người dùng), `SchedulerState` (trạng thái scheduler), `SavedPaper` (bài đã bookmark), `UserCategory` (chủ đề đã follow). |
| `database/data.db` | **Cơ sở dữ liệu SQLite**: file database vật lý, dùng khi fallback hoặc dev local. |

#### Giao diện người dùng (Templates)

| File / Folder | Công dụng |
|---|---|
| `templates/base.html` | **Layout gốc (Base Template)**: chứa `<head>` (Tailwind CSS CDN, favicon, CSS tùy chỉnh), header (guest/user), footer, nút "Back to Top", load toàn bộ file JS dùng chung. Định nghĩa block `content` và `extra_js` để các trang con override. |
| `templates/pages/index.html` | **Trang chủ (Home)**: hiển thị feed bài viết với 3 tab filter (Newest, Saved, Following), infinite scroll "Xem thêm bài nghiên cứu", bookmark toggle, auth-gating cho các tính năng yêu cầu đăng nhập. |
| `templates/pages/profile.html` | **Trang cá nhân (Profile)**: hiển thị avatar, username, email, ngày tham gia; danh sách nút toggle chủ đề yêu thích (bấm để follow/unfollow). |
| `templates/components/` | **Thư viện component tái sử dụng**: các phần UI dùng chung được `{% include %}` vào nhiều trang. |
| `templates/components/paper_card.html` | **Component Card bài viết**: hiển thị tiêu đề, tác giả, ngày, abstract (có expand/collapse), AI tóm tắt, nút bookmark, nút "Đọc bài". |
| `templates/components/header/` | **Header components**: `guest_header_q.html` (header cho khách chưa đăng nhập với nút "Đăng nhập" + search bar), `user_header.html` (header cho user đã đăng nhập với avatar + dropdown menu). |
| `templates/components/auth/` | **Auth modals**: `login_modal.html` (modal đăng nhập), `register_modal.html` (modal đăng ký). |
| `templates/components/footer.html` | **Footer chung**: hiển thị thông tin bản quyền, liên kết. |

#### Static Assets

| Folder | Công dụng |
|---|---|
| `static/css/main.css` | **CSS tùy chỉnh**: style cho paper card, auth modal, animation, typography... |
| `static/js/modal.js` | **JS quản lý modal**: mở/đóng login modal, register modal; chuyển đổi giữa login ↔ register. |
| `static/js/auth.js` | **JS xử lý form đăng nhập/đăng ký**: gửi AJAX request đến `/auth/login` và `/auth/register`, xử lý response, hiển thị lỗi. |
| `static/js/dropdown.js` | **JS quản lý dropdown menu** (user menu khi đã đăng nhập). |
| `static/js/back-to-top.js` | **JS nút "Back to Top"**: hiển thị/ẩn khi scroll, cuộn mượt lên đầu trang. |
| `static/js/paper-expand.js` | **JS xử lý expand/collapse abstract**: bấm "Xem thêm" để mở rộng abstract, "Thu gọn" để rút lại. |
| `static/js/main.js` | **JS khởi tạo chung**: các script khởi tạo chạy trên mọi trang. |
| `static/images/` | Hình ảnh tĩnh của ứng dụng. |
| `static/logo/` | Logo PaperHub (`logo.png`). |
| `static/favicon/` | Favicon (`favicon.ico`). |

#### Tiện ích (Utilities)

| File | Công dụng |
|---|---|
| `logger.py` | **Cấu hình logging**: ghi log ứng dụng ra file `logs/app.log`, hỗ trợ debug và monitoring. |
| `logs/app.log` | **File log ứng dụng**: ghi lại các sự kiện, lỗi, hoạt động scheduler. |

---

## Luồng Hoạt Động Chính

1. **Khởi động**: `main.py` → `create_app()` → khởi tạo Flask, DB, Login Manager, Scheduler, Blueprints
2. **Fetch arXiv tự động**: Scheduler chạy mỗi 6 tiếng → gọi arXiv API → lưu bài mới → gọi AI tạo tóm tắt tiếng Việt
3. **Người dùng truy cập**: Trang chủ hiển thị 5 bài mới nhất → bấm "Xem thêm bài nghiên cứu" để load thêm (infinite scroll)
4. **Xác thực**: Guest bấm "Đăng nhập" → modal login/register → `auth.py` xử lý → `Flask-Login` quản lý session
5. **Bookmark**: User bấm icon bookmark → `POST /save-paper` → toggle lưu/bỏ lưu → UI cập nhật ngay
6. **Filter Saved/Following**: Chọn tab → gọi API tương ứng → render danh sách phù hợp
7. **Profile & Follow**: Vào Profile → bấm nút chủ đề để follow/unfollow → `POST /toggle-follow`