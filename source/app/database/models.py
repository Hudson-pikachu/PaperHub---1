from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Khởi tạo đối tượng Database
db = SQLAlchemy()

class Paper(db.Model):
    # 1. ID tự tăng (Khóa chính)
    id = db.Column(db.Integer, primary_key=True)
    # 2. Tiêu đề bài viết
    title = db.Column(db.String(500), nullable=False)
    # 3. Ngày xuất bản (Lưu dạng chuỗi hoặc ngày tháng)
    published_date = db.Column(db.String(100))
    # 4. Tác giả (Lưu dạng chuỗi, có thể phân cách bằng dấu phẩy)
    authors = db.Column(db.String(500))
    # 5. Nhà xuất bản
    publisher = db.Column(db.String(200))
    # 6. Tóm tắt gốc (Abstracts) - Dùng Text vì nội dung thường rất dài
    abstract = db.Column(db.Text)
    # 7. Link trực tiếp
    link = db.Column(db.String(500))
    # 8. Số lượt trích dẫn (Cited by)
    cited_count = db.Column(db.Integer, default=0)
    # 9. Nội dung tóm tắt bằng AI (Sau này bạn sẽ dùng Faster-Whisper hoặc GPT để điền vào đây)
    ai_summary = db.Column(db.Text)
    # 10. Thể loại (Category)
    category = db.Column(db.String(100))
    # 11. Ngày thêm vào cơ sở dữ liệu (Tự động lấy thời gian hiện tại)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self):
        return f'<Paper {self.title[:30]}...>'