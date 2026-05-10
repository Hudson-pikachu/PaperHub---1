from flask import Blueprint, request, jsonify, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from .database.models import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Đăng ký tài khoản mới. Trả về JSON."""
    if current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Bạn đã đăng nhập rồi.'}), 400

    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    confirm = data.get('confirm_password', '')

    # --- Validation ---
    if not username or not email or not password or not confirm:
        return jsonify({'success': False, 'message': 'Vui lòng điền đầy đủ thông tin.'}), 400
    if len(username) < 3:
        return jsonify({'success': False, 'message': 'Username phải có ít nhất 3 ký tự.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Mật khẩu phải có ít nhất 6 ký tự.'}), 400
    if password != confirm:
        return jsonify({'success': False, 'message': 'Mật khẩu xác nhận không khớp.'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username đã tồn tại, hãy chọn tên khác.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email này đã được sử dụng.'}), 400

    # --- Tạo user ---
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)
    return jsonify({'success': True, 'message': f'Chào mừng {username}! Đăng ký thành công.', 'redirect': '/'})


@auth_bp.route('/login', methods=['POST'])
def login():
    """Đăng nhập. Trả về JSON."""
    if current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Bạn đã đăng nhập rồi.'}), 400

    data = request.get_json(silent=True) or {}
    identifier = data.get('identifier', '').strip()  # email hoặc username
    password = data.get('password', '')
    remember = data.get('remember', False)

    if not identifier or not password:
        return jsonify({'success': False, 'message': 'Vui lòng điền đầy đủ thông tin.'}), 400

    # Tìm user theo email hoặc username
    user = User.query.filter_by(email=identifier.lower()).first()
    if not user:
        user = User.query.filter_by(username=identifier).first()

    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Email/Username hoặc mật khẩu không đúng.'}), 401

    login_user(user, remember=remember)
    return jsonify({'success': True, 'message': f'Chào mừng trở lại, {user.username}!', 'redirect': '/'})


@auth_bp.route('/logout')
@login_required
def logout():
    """Đăng xuất và quay về trang chủ."""
    logout_user()
    return redirect(url_for('main.home'))
