from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Khởi tạo đối tượng Database
db = SQLAlchemy()

class Category(db.Model):
    # Bảng danh mục bài viết
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    name_en = db.Column(db.String(100))
    description = db.Column(db.String(500))
    
    @property
    def display_name(self):
        from flask import session
        lang = session.get('lang', 'vi') if session else 'vi'
        if lang == 'en' and self.name_en:
            return self.name_en
        return self.name
    
    def __repr__(self):
        return f'<Category {self.name}>'

class SchedulerState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    last_run = db.Column(db.DateTime)

    def __repr__(self):
        return f'<SchedulerState last_run={self.last_run}>'


class FetchHistory(db.Model):
    """Lịch sử các lần fetch arXiv."""
    __tablename__ = 'fetch_history'

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    finished_at = db.Column(db.DateTime, default=datetime.utcnow)
    duration_seconds = db.Column(db.Integer, default=0)
    saved_count = db.Column(db.Integer, default=0)
    per_category = db.Column(db.Integer, default=2)
    ai_processed = db.Column(db.Integer, default=0)
    ai_error = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<FetchHistory id={self.id} saved={self.saved_count}>'


class FetchConfig(db.Model):
    """Cấu hình fetch arXiv (dùng cho scheduler nội bộ)."""
    __tablename__ = 'fetch_config'

    id = db.Column(db.Integer, primary_key=True)
    interval_hours = db.Column(db.Integer, default=6, nullable=False)
    per_category = db.Column(db.Integer, default=2, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<FetchConfig interval={self.interval_hours}h per_cat={self.per_category}>'


class SiteSettings(db.Model):
    """Cấu hình toàn trang."""
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)
    guest_load_more = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<SiteSettings guest_load_more={self.guest_load_more}>'

class Paper(db.Model):
    # 1. ID tự tăng (Khóa chính)
    id = db.Column(db.Integer, primary_key=True)
    # 2. Tiêu đề bài viết
    title = db.Column(db.String(500), nullable=False)
    # 2b. Tiêu đề tiếng Anh
    title_en = db.Column(db.String(500))
    # 3. Ngày xuất bản (Lưu dạng chuỗi hoặc ngày tháng)
    published_date = db.Column(db.String(100))
    # 4. Tác giả (Lưu dạng chuỗi, có thể phân cách bằng dấu phẩy)
    authors = db.Column(db.String(500))
    # 5. Nhà xuất bản
    publisher = db.Column(db.String(200))
    # 6. Tóm tắt gốc (Abstracts) - Dùng Text vì nội dung thường rất dài
    abstract = db.Column(db.Text)
    # 6b. Abstract tiếng Anh
    abstract_en = db.Column(db.Text)
    # 7. Link trực tiếp
    link = db.Column(db.String(500), unique=True)
    # 8. Số lượt trích dẫn (Cited by)
    cited_count = db.Column(db.Integer, default=0)
    # 9. Nội dung tóm tắt bằng AI
    ai_summary = db.Column(db.Text)
    # 9b. AI summary (English)
    ai_summary_en = db.Column(db.Text)
    # 10. Hiện trạng nội dung
    status = db.Column(db.String(20), default='pending', nullable=False)
    # 11. Thể loại - khóa ngoại tới bảng Category
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category = db.relationship('Category', backref='papers')
    
    # 12. Ngày thêm vào cơ sở dữ liệu (Tự động lấy thời gian hiện tại)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def category_name(self):
        if not self.category:
            return "Chờ phân loại"
        return self.category.display_name

    def __repr__(self):
        return f'<Paper {self.title[:30]}...>'


class User(db.Model, UserMixin):
    """Bảng người dùng — hỗ trợ đăng nhập qua Flask-Login."""
    id = db.Column(db.Integer, primary_key=True)
    # Tên đăng nhập (duy nhất)
    username = db.Column(db.String(80), nullable=False, unique=True)
    # Email (duy nhất)
    email = db.Column(db.String(200), nullable=False, unique=True)
    # Mật khẩu đã hash
    password_hash = db.Column(db.String(256), nullable=False)
    # Ngày tạo tài khoản
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Trạng thái tài khoản (UserMixin dùng is_active)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # Quyền admin (True = có quyền truy cập trang quản trị)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def __init__(self, username: str, email: str, **kwargs):
        super().__init__(**kwargs)
        self.username = username
        self.email = email

    def set_password(self, password: str):
        """Hash và lưu mật khẩu."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Kiểm tra mật khẩu với hash đã lưu."""
        return check_password_hash(self.password_hash, password)

    @property
    def initials(self) -> str:
        """Trả về 2 ký tự đầu của username (viết hoa), dùng cho avatar."""
        return self.username[:2].upper() if self.username else '??'

    def __repr__(self):
        return f'<User {self.username}>'


class SavedPaper(db.Model):
    """Bảng lưu bài viết của người dùng (bookmark)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey('paper.id', ondelete='CASCADE'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='saved_papers')
    paper = db.relationship('Paper', backref='saved_by')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'paper_id', name='uq_user_paper_save'),
    )

    def __repr__(self):
        return f'<SavedPaper user={self.user_id} paper={self.paper_id}>'


class UserCategory(db.Model):
    """Bảng theo dõi chủ đề yêu thích của người dùng."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='CASCADE'), nullable=False)

    user = db.relationship('User', backref='followed_categories')
    category = db.relationship('Category', backref='followers')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'category_id', name='uq_user_category_follow'),
    )

    def __repr__(self):
        return f'<UserCategory user={self.user_id} category={self.category_id}>'


class UserPaperRead(db.Model):
    """Bảng theo dõi bài viết người dùng đã xem qua notification bell."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey('paper.id', ondelete='CASCADE'), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='read_papers')
    paper = db.relationship('Paper')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'paper_id', name='uq_user_paper_read'),
    )

    def __repr__(self):
        return f'<UserPaperRead user={self.user_id} paper={self.paper_id}>'
