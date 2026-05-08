from flask import Flask
from flask_apscheduler import APScheduler
from sqlalchemy import inspect, text
from datetime import datetime, timedelta
from .database.models import db, SchedulerState
from .services.arxiv_service import fetch_arxiv_for_all_categories

def _ensure_db_schema(app):
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        if 'paper' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('paper')]
            if 'status' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE paper ADD COLUMN status VARCHAR(20) DEFAULT 'pending' NOT NULL"))


def _get_last_run():
    state = SchedulerState.query.get(1)
    return state.last_run if state else None


def _set_last_run(run_time: datetime):
    state = SchedulerState.query.get(1)
    if not state:
        state = SchedulerState()
        state.id = 1
    state.last_run = run_time
    db.session.add(state)
    db.session.commit()


def create_app():
    app = Flask(__name__)
    
    # Cấu hình DB (Tạm thời viết cứng ở đây, sau này đưa ra config.py)
    import os
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database', 'data.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SCHEDULER_API_ENABLED'] = False
    app.config['SCHEDULER_TIMEZONE'] = 'Asia/Ho_Chi_Minh'

    db.init_app(app)
    _ensure_db_schema(app)

    # Đăng ký các Route
    from .routes import main_bp
    app.register_blueprint(main_bp)

    # Cấu hình định kỳ fetch arXiv mỗi 6 tiếng
    scheduler = APScheduler()
    scheduler.init_app(app)

    def scheduled_fetch():
        with app.app_context():
            count = fetch_arxiv_for_all_categories(per_category=2)
            _set_last_run(datetime.utcnow())
            print(f"[Scheduler] Fetch arXiv 6x2 completed, saved {count} papers")

    next_run = None
    last_run = None
    with app.app_context():
        last_run = _get_last_run()
    if last_run:
        next_run = last_run + timedelta(hours=6)
        if next_run < datetime.utcnow():
            next_run = datetime.utcnow()
    else:
        next_run = datetime.utcnow()

    scheduler.add_job(
        id='fetch_arxiv_every_6h',
        func=scheduled_fetch,
        trigger='interval',
        hours=6,
        next_run_time=next_run,
    )
    scheduler.start()

    return app