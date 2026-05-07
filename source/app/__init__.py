from flask import Flask
from .database.models import db # Import từ models.py đã di chuyển

def create_app():
    app = Flask(__name__)
    
    # Cấu hình DB (Tạm thời viết cứng ở đây, sau này đưa ra config.py)
    import os
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database', 'data.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # Đăng ký các Route
    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app