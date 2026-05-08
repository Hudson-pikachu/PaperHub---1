import arxiv
from datetime import datetime
from ..database.models import Paper, Category, db
from .ai_service import translate_and_summarize_paper

ARXIV_CATEGORY_MAP = {
    "Học Máy": "cs.LG",
    "Xử Lý Ngôn Ngữ": "cs.CL",
    "Thị Giác Máy Tính": "cs.CV",
    "Mạng Máy Tính": "cs.NI",
    "Kiến Trúc Máy Tính": "cs.AR",
    "Tối Ưu Hóa": "cs.DS",
}


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


def fetch_arxiv_papers(query: str = "Học Máy", max_results: int = 20) -> int:
    """Lấy tối đa max_results bài viết mới nhất từ arXiv và lưu vào database."""
    query_code = _resolve_arxiv_query(query)
    category_id = _resolve_category_id(query)

    search = arxiv.Search(
        query=query_code,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    saved = 0
    new_paper_ids = []
    for result in search.results():
        if Paper.query.filter_by(link=result.pdf_url).first():
            continue

        paper = Paper()
        paper.title = result.title
        paper.published_date = result.published.strftime("%Y-%m-%d")
        paper.authors = ", ".join(author.name for author in result.authors)
        paper.publisher = result.primary_category
        paper.abstract = result.summary
        paper.link = result.pdf_url
        paper.category_id = category_id
        paper.cited_count = 0

        db.session.add(paper)
        db.session.flush()
        new_paper_ids.append(paper.id)
        saved += 1

    db.session.commit()

    for paper_id in new_paper_ids:
        try:
            translate_and_summarize_paper(paper_id)
        except Exception:
            # Nếu Google AI lỗi thì giữ paper ở trạng thái pending và tiếp tục xử lý bài khác.
            continue

    return saved


def fetch_arxiv_for_all_categories(per_category: int = 2) -> int:
    """Lấy mỗi category trong ARXIV_CATEGORY_MAP per_category bài."""
    total_saved = 0
    for local_category in ARXIV_CATEGORY_MAP.keys():
        total_saved += fetch_arxiv_papers(query=local_category, max_results=per_category)
    return total_saved
