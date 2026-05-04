# Chương trình được code trên Python 3.11
# Sử dụng framework web app Flask 2.2.5
# Sử dụng thư viện flask_sqlalchemy 3.1.1 để điều khiển SQLite
# Sau khi build thì truy cập bằng trình duyệt web bằng đường dẫn: http://127.0.0.1:8080

import os
from flask import Flask
from flask import jsonify, request, render_template # Thêm hàm này để load file html
from database.models import db, Paper # Import từ file models.py

app = Flask(__name__)

# 1. Cấu hình đường dẫn file Database
basedir = os.path.abspath(os.path.dirname(__file__)) # Sử dụng os.path để tự động tương thích với mọi máy tính
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database', 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Tắt tính năng thông báo để đỡ tốn tài nguyên

# 2. Kết nối vào cơ sở dữ liệu
db.init_app(app)

@app.route('/')
def home():
    # Lấy 5 bài nghiên cứu mới nhất dựa trên ngày thêm vào (date_added)
    latest_papers = Paper.query.order_by(Paper.date_added.desc()).limit(5).all()
    return render_template('index.html', papers=latest_papers)

@app.route('/load-more')
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

if __name__ == '__main__':
    # host='0.0.0.0' giúp bạn có thể truy cập từ thiết bị khác trong cùng mạng LAN
    app.run(host='0.0.0.0', port=8080, debug=True)