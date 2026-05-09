from flask import Blueprint, render_template, request, jsonify
from .database.models import Paper, Category, SchedulerState
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    latest_papers = Paper.query.filter_by(status='posted').join(Category).order_by(Paper.date_added.desc()).limit(5).all()
    return render_template('pages/index.html', papers=latest_papers)

@main_bp.route('/load-more')
def load_more():
    offset = request.args.get('offset', default=5, type=int)
    limit = 5
    
    papers = Paper.query.filter_by(status='posted').join(Category).order_by(Paper.date_added.desc()).offset(offset).limit(limit).all()
    
    output = []
    for p in papers:
        output.append({
            "title": p.title,
            "authors": p.authors,
            "published_date": p.published_date,
            "abstract": p.abstract,
            "ai_summary": p.ai_summary,
            "status": p.status,
            "category": p.category_name,
            "link": p.link,
            "publisher": p.publisher,
            "cited_count": p.cited_count
        })
    
    return jsonify(output)

@main_bp.route('/scheduler-status')
def scheduler_status():
    state = SchedulerState.query.get(1)
    if state and state.last_run:
        last_run = state.last_run.isoformat() + 'Z'
        next_run = (state.last_run + timedelta(hours=6)).isoformat() + 'Z'
    else:
        last_run = None
        next_run = None
    return jsonify({
        "last_run": last_run,
        "next_run": next_run,
        "interval_hours": 6,
        "note": "Sau khi restart, app sẽ dựa vào last_run để tính thời điểm chạy tiếp."
    })