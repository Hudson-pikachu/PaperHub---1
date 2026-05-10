from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from flask_login import login_required, current_user
from .database.models import db, Paper, Category, SchedulerState, SavedPaper, UserCategory, UserPaperRead
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    is_fallback = current_app.config.get('DB_FALLBACK', False)
    latest_papers = Paper.query.filter_by(status='posted').outerjoin(Category).order_by(Paper.date_added.desc()).limit(5).all()

    # Lấy danh sách ID bài đã lưu của user hiện tại (nếu đã đăng nhập)
    saved_paper_ids = []
    if current_user.is_authenticated:
        saved_paper_ids = [
            sp.paper_id for sp in
            SavedPaper.query.filter_by(user_id=current_user.id).all()
        ]

    return render_template('pages/index.html', papers=latest_papers, db_fallback=is_fallback, saved_paper_ids=saved_paper_ids)

@main_bp.route('/profile')
@login_required
def profile():
    categories = Category.query.order_by(Category.name).all()
    return render_template('pages/profile.html', categories=categories)

@main_bp.route('/read/<int:paper_id>')
def read_paper(paper_id):
    """Trang đọc bài nghiên cứu với PDF viewer nhúng."""
    paper = Paper.query.get_or_404(paper_id)
    # Tạo PDF URL từ arXiv link
    pdf_url = None
    if paper.link:
        # arXiv link: https://arxiv.org/abs/XXXX.XXXXX → PDF: https://arxiv.org/pdf/XXXX.XXXXX
        if 'arxiv.org/abs/' in paper.link:
            pdf_url = paper.link.replace('/abs/', '/pdf/')
        else:
            pdf_url = paper.link

    return render_template('pages/read.html', paper=paper, pdf_url=pdf_url)

@main_bp.route('/load-more')
def load_more():
    offset = request.args.get('offset', default=5, type=int)
    limit = 5
    
    papers = Paper.query.filter_by(status='posted').outerjoin(Category).order_by(Paper.date_added.desc()).offset(offset).limit(limit).all()
    
    output = []
    for p in papers:
        output.append({
            "id": p.id,
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
    
    # Kiểm tra xem còn bài nào nữa không
    total = Paper.query.filter_by(status='posted').outerjoin(Category).count()
    has_more = (offset + limit) < total
    
    return jsonify({
        "papers": output,
        "has_more": has_more
    })

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

@main_bp.route('/save-paper', methods=['POST'])
@login_required
def save_paper():
    """Toggle lưu/bỏ lưu một bài viết."""
    data = request.get_json(silent=True) or {}
    paper_id = data.get('paper_id')
    if not paper_id:
        return jsonify({'success': False, 'message': 'Thiếu paper_id.'}), 400

    paper = Paper.query.get(paper_id)
    if not paper:
        return jsonify({'success': False, 'message': 'Bài viết không tồn tại.'}), 404

    existing = SavedPaper.query.filter_by(user_id=current_user.id, paper_id=paper_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'success': True, 'saved': False, 'message': 'Đã bỏ lưu.'})
    else:
        saved = SavedPaper(user_id=current_user.id, paper_id=paper_id)
        db.session.add(saved)
        db.session.commit()
        return jsonify({'success': True, 'saved': True, 'message': 'Đã lưu.'})

@main_bp.route('/saved-papers')
@login_required
def saved_papers():
    """Trả về danh sách bài đã lưu, sắp xếp theo thời gian lưu xa dần (cũ nhất trước)."""
    saved = (
        SavedPaper.query
        .filter_by(user_id=current_user.id)
        .order_by(SavedPaper.saved_at.asc())
        .join(Paper, SavedPaper.paper_id == Paper.id)
        .all()
    )
    papers = []
    for s in saved:
        p = s.paper
        papers.append({
            "id": p.id,
            "title": p.title,
            "authors": p.authors,
            "published_date": p.published_date,
            "abstract": p.abstract,
            "ai_summary": p.ai_summary,
            "status": p.status,
            "category": p.category_name,
            "link": p.link,
            "publisher": p.publisher,
            "cited_count": p.cited_count,
        })
    return jsonify({'success': True, 'papers': papers})

@main_bp.route('/toggle-follow', methods=['POST'])
@login_required
def toggle_follow():
    """Toggle theo dõi/bỏ theo dõi một chủ đề."""
    data = request.get_json(silent=True) or {}
    category_id = data.get('category_id')
    if not category_id:
        return jsonify({'success': False, 'message': 'Thiếu category_id.'}), 400

    category = Category.query.get(category_id)
    if not category:
        return jsonify({'success': False, 'message': 'Chủ đề không tồn tại.'}), 404

    existing = UserCategory.query.filter_by(user_id=current_user.id, category_id=category_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'success': True, 'followed': False, 'message': f'Đã bỏ theo dõi "{category.name}".'})
    else:
        follow = UserCategory(user_id=current_user.id, category_id=category_id)
        db.session.add(follow)
        db.session.commit()
        return jsonify({'success': True, 'followed': True, 'message': f'Đã theo dõi "{category.name}".'})

@main_bp.route('/following-papers')
@login_required
def following_papers():
    """Trả về danh sách bài viết thuộc các chủ đề người dùng đang theo dõi."""
    followed_ids = [
        uc.category_id for uc in
        UserCategory.query.filter_by(user_id=current_user.id).all()
    ]

    if not followed_ids:
        return jsonify({'success': True, 'papers': [], 'followed_topics': []})

    papers = (
        Paper.query
        .filter(Paper.status == 'posted', Paper.category_id.in_(followed_ids))
        .outerjoin(Category)
        .order_by(Paper.date_added.desc())
        .all()
    )

    # Lấy tên các chủ đề đang theo dõi
    followed_topics = [c.name for c in Category.query.filter(Category.id.in_(followed_ids)).all()]

    output = []
    for p in papers:
        output.append({
            "id": p.id,
            "title": p.title,
            "authors": p.authors,
            "published_date": p.published_date,
            "abstract": p.abstract,
            "ai_summary": p.ai_summary,
            "status": p.status,
            "category": p.category_name,
            "link": p.link,
            "publisher": p.publisher,
            "cited_count": p.cited_count,
        })

    return jsonify({
        'success': True,
        'papers': output,
        'followed_topics': followed_topics
    })

@main_bp.route('/followed-categories')
@login_required
def followed_categories():
    """Trả về danh sách ID các chủ đề người dùng đang theo dõi."""
    followed_ids = [
        uc.category_id for uc in
        UserCategory.query.filter_by(user_id=current_user.id).all()
    ]
    return jsonify({'success': True, 'followed_ids': followed_ids})

@main_bp.route('/unread-count')
@login_required
def unread_count():
    """Trả về số bài chưa đọc trong notification bell."""
    since = current_user.created_at or datetime.utcnow()
    read_ids = [
        rp.paper_id for rp in
        UserPaperRead.query.filter_by(user_id=current_user.id).all()
    ]

    query = Paper.query.filter(
        Paper.status == 'posted',
        Paper.date_added > since
    )
    if read_ids:
        query = query.filter(~Paper.id.in_(read_ids))

    count = query.count()
    return jsonify({'success': True, 'unread_count': count})

@main_bp.route('/new-papers')
@login_required
def new_papers():
    """Trả về bài nghiên cứu mới phát sinh sau thời điểm người dùng đăng ký, trừ các bài đã xem."""
    since = current_user.created_at or datetime.utcnow()

    # Lấy danh sách ID bài đã đọc
    read_ids = [
        rp.paper_id for rp in
        UserPaperRead.query.filter_by(user_id=current_user.id).all()
    ]

    query = Paper.query.filter(
        Paper.status == 'posted',
        Paper.date_added > since
    )
    if read_ids:
        query = query.filter(~Paper.id.in_(read_ids))

    papers = (
        query
        .outerjoin(Category)
        .order_by(Paper.date_added.desc())
        .limit(20)
        .all()
    )
    count = len(papers)
    output = []
    for p in papers:
        output.append({
            "id": p.id,
            "title": p.title,
            "authors": p.authors,
            "published_date": p.published_date,
            "abstract": p.abstract[:150] + '...' if p.abstract and len(p.abstract) > 150 else (p.abstract or ''),
            "category": p.category_name,
            "link": p.link,
            "date_added": p.date_added.isoformat() + 'Z' if p.date_added else None,
        })
    return jsonify({'success': True, 'papers': output, 'count': count})

@main_bp.route('/mark-paper-read', methods=['POST'])
@login_required
def mark_paper_read():
    """Đánh dấu một bài nghiên cứu là đã xem qua notification bell."""
    data = request.get_json(silent=True) or {}
    paper_id = data.get('paper_id')
    if not paper_id:
        return jsonify({'success': False, 'message': 'Thiếu paper_id.'}), 400

    existing = UserPaperRead.query.filter_by(user_id=current_user.id, paper_id=paper_id).first()
    if not existing:
        read_entry = UserPaperRead(user_id=current_user.id, paper_id=paper_id)
        db.session.add(read_entry)
        db.session.commit()

    # Trả về số bài chưa đọc còn lại
    since = current_user.created_at or datetime.utcnow()
    read_ids = [
        rp.paper_id for rp in
        UserPaperRead.query.filter_by(user_id=current_user.id).all()
    ]
    remaining = (
        Paper.query
        .filter(
            Paper.status == 'posted',
            Paper.date_added > since
        )
    )
    if read_ids:
        remaining = remaining.filter(~Paper.id.in_(read_ids))
    unread_count = remaining.count()

    return jsonify({'success': True, 'unread_count': unread_count})
