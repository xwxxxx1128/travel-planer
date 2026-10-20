import pytest

from app.db.session import SessionLocal, init_db
from app.models.review import Review


@pytest.fixture(autouse=True)
def _reset_review_cache():
    """每个用例前清空评价缓存表：pytest 下 sqlite 为共享 in-memory，避免缓存跨用例串数据。"""
    init_db()
    with SessionLocal() as session:
        session.query(Review).delete()
        session.commit()
    yield
