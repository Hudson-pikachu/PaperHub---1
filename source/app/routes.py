from flask import Blueprint, render_template, request, jsonify
from .database.models import Paper # Import Paper để truy vấn

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    # Giữ nguyên code lấy latest_papers của bạn
    latest_papers = Paper.query.order_by(Paper.date_added.desc()).limit(5).all()
    return render_template('index.html', papers=latest_papers)

@main_bp.route('/load-more')
def load_more():
    # Lấy vị trí bắt đầu từ tham số 'offset' trên URL (mặc định là 5 vì trang đầu đã load 5 bài)
    offset = request.args.get('offset', default=5, type=int)
    limit = 5
    
    papers = Paper.query.order_by(Paper.date_added.desc()).offset(offset).limit(limit).all()
    
    # Chuyển dữ liệu thành danh sách JSON
    output = []
    for p in papers:
        output.append({
            "title": p.title,
            "authors": p.authors,
            "published_date": p.published_date,
            "abstract": p.abstract[:250] + "...",
            "ai_summary": p.ai_summary,
            "category": p.category,
            "link": p.link,
            "publisher": p.publisher,
            "cited_count": p.cited_count
        })
    
    return jsonify(output)