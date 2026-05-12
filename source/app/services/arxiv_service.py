import re
import arxiv
import time
from datetime import datetime
from ..database.models import Paper, Category, db
from .ai_service import batch_translate_and_summarize

ARXIV_CATEGORY_MAP = {
    "Học Máy": "cs.LG",
    "Xử Lý Ngôn Ngữ": "cs.CL",
    "Thị Giác Máy Tính": "cs.CV",
    "Mạng Máy Tính": "cs.NI",
    "Kiến Trúc Máy Tính": "cs.AR",
    "Tối Ưu Hóa": "cs.DS",
}

# Khoảng delay tối thiểu giữa các request arXiv (giây)
# arXiv API rate limit: ~1 request / 3 giây, 429 nếu gọi nhanh quá
_ARXIV_REQUEST_DELAY = 3.5


def _clean_text(text: str) -> str:
    """Loại bỏ ký hiệu LaTeX/HTML khỏi text trước khi lưu."""
    if not text:
        return ''
    # Xóa các lệnh LaTeX: \frac{...}{...}, \sum, \mathbf{}, ...
    text = re.sub(r'\\[a-zA-Z]+\{.*?\}(\{.*?\})?', '', text)
    # Xóa math mode: $...$ và $$...$$
    text = re.sub(r'\$\$?[^$]+\$\$?', '', text)
    # Xóa các dấu { } còn sót
    text = re.sub(r'[{}\\]', ' ', text)
    # Thu gọn khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _resolve_arxiv_query(query: str) -> str:
    """Chuyển tên category nội bộ sang mã arXiv nếu cần."""
    return ARXIV_CATEGORY_MAP.get(query, query)


def _resolve_category_id(query: str) -> int | None:
    """Chuyển tên category nội bộ thành category_id trong DB."""
    if query in ARXIV_CATEGORY_MAP:
        category = Category.query.filter_by(name=query).first()
        if category:
            return category.id
    return None


def fetch_arxiv_papers(query: str = "Học Máy", max_results: int = 20) -> tuple[int, list[int]]:
    """Lấy tối đa max_results bài viết mới nhất từ arXiv và lưu vào database.

    Returns:
        (số bài đã lưu, danh sách ID các bài mới tạo - status="pending")
    """
    query_code = _resolve_arxiv_query(query)
    category_id = _resolve_category_id(query)

    # Dùng cat: prefix để search đúng category, tránh text search gây ra
    # kết quả không mong muốn và tránh lỗi 429 do query sai format
    search_query = f"cat:{query_code}" if query_code else query_code

    # Delay trước mỗi request để tránh arXiv rate limit (429)
    time.sleep(_ARXIV_REQUEST_DELAY)

    search = arxiv.Search(
        query=search_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    print(f"  [arXiv] Fetching: query='{search_query}', max_results={max_results}")
    saved = 0
    new_paper_ids = []
    for result in search.results():
        if Paper.query.filter_by(link=result.pdf_url).first():
            continue

        # Làm sạch text trước khi lưu
        clean_title = _clean_text(result.title)
        clean_abstract = _clean_text(result.summary or '')

        paper = Paper()
        paper.title = clean_title if clean_title else result.title
        paper.title_en = result.title  # Giữ nguyên bản gốc tiếng Anh
        paper.published_date = result.published.strftime("%Y-%m-%d")
        paper.authors = ", ".join(author.name for author in result.authors)
        paper.publisher = result.primary_category
        paper.abstract = clean_abstract if clean_abstract else (result.summary or '')
        paper.abstract_en = result.summary or ''
        paper.link = result.pdf_url
        paper.category_id = category_id
        paper.cited_count = 0

        db.session.add(paper)
        db.session.flush()
        new_paper_ids.append(paper.id)
        saved += 1

    db.session.commit()
    return saved, new_paper_ids


def fetch_arxiv_for_all_categories(per_category: int = 2) -> tuple[int, int, str | None]:
    """Lấy mỗi category trong ARXIV_CATEGORY_MAP per_category bài.

    Gom TẤT CẢ bài mới từ mọi category, rồi gọi batch Google AI 1 lần duy nhất.
    Mỗi category fetch độc lập — 1 category fail (vd: 429) không ảnh hưởng category khác.
    """
    total_saved = 0
    all_new_ids = []
    fetch_errors = []

    for local_category in ARXIV_CATEGORY_MAP.keys():
        try:
            saved, new_ids = fetch_arxiv_papers(query=local_category, max_results=per_category)
            total_saved += saved
            all_new_ids.extend(new_ids)
            print(f"  [arXiv] Category '{local_category}': saved={saved}, new_ids={len(new_ids)}")
        except Exception as e:
            error_msg = f"Category '{local_category}' failed: {str(e)[:150]}"
            print(f"  [arXiv] ERROR: {error_msg}")
            fetch_errors.append(error_msg)
            # Tiếp tục category tiếp theo, không throw
            continue

    # Gọi batch Google AI, chunk 6 bài/lần để tránh timeout
    # Nếu AI lỗi → giữ status= pending để retry sau
    # Nếu AI thành công → status= posted (được set trong batch_translate_and_summarize)
    ai_processed = 0
    ai_errors = []
    CHUNK_SIZE = 6
    if all_new_ids:
        for i in range(0, len(all_new_ids), CHUNK_SIZE):
            chunk_ids = all_new_ids[i:i + CHUNK_SIZE]
            try:
                result = batch_translate_and_summarize(chunk_ids)
                ai_processed += result
            except Exception as e:
                ai_errors.append(f"Chunk {i // CHUNK_SIZE + 1}: {str(e)[:100]}")

    # Gộp lỗi fetch + AI
    all_errors = fetch_errors + ai_errors
    ai_error = '; '.join(all_errors) if all_errors else None
    return total_saved, ai_processed, ai_error
