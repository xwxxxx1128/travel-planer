"""评价检索缓存单测：mock Tavily，验证「一个月内同地先查库」与 force_refresh 行为。"""

import pytest
from unittest.mock import AsyncMock, patch

from tools import reviews_tools
from app.db.session import SessionLocal, init_db
from app.models.review import Review


class FakeTavilyClient:
    """替代 TavilyMcpClient 的假客户端：__aenter__ 返回自身，search 返回预置结果。"""

    def __init__(self, items):
        self._items = items
        self.search = AsyncMock(return_value=items)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def _setup():
    # 确保表存在，并清空 reviews，避免与其他用例共享 in-memory DB 互相干扰
    init_db()
    with SessionLocal() as s:
        s.query(Review).delete()
        s.commit()
    yield
    with SessionLocal() as s:
        s.query(Review).delete()
        s.commit()


def _factory(items, counter):
    def _make(*_a, **_k):
        counter["n"] += 1
        return FakeTavilyClient(items)

    return _make


def test_cache_second_call_skips_tavily():
    items = [{"title": "故宫好评", "url": "https://example.com/1", "content": "很棒"}]
    counter = {"n": 0}

    with patch("tools.reviews_tools.TavilyMcpClient", _factory(items, counter)):
        first = reviews_tools.fetch_tavily_reviews_sync("故宫", city="北京")
        second = reviews_tools.fetch_tavily_reviews_sync("故宫", city="北京")

    assert first and second
    assert first[0]["title"] == "故宫好评"
    # 第二次命中本地缓存，不应再构造/调用 Tavily 客户端
    assert counter["n"] == 1


def test_force_refresh_bypasses_cache():
    items = [{"title": "外滩夜景", "url": "https://example.com/2", "content": "漂亮"}]
    counter = {"n": 0}

    with patch("tools.reviews_tools.TavilyMcpClient", _factory(items, counter)):
        reviews_tools.fetch_tavily_reviews_sync("外滩", city="上海")
        reviews_tools.fetch_tavily_reviews_sync("外滩", city="上海", force_refresh=True)

    # 强制刷新会再调一次 Tavily
    assert counter["n"] == 2


def test_cached_rows_persisted_with_expiry():
    items = [{"title": "豫园小吃", "url": "https://example.com/3", "content": "好吃"}]

    with patch("tools.reviews_tools.TavilyMcpClient", _factory(items, {"n": 0})):
        reviews_tools.fetch_tavily_reviews_sync("豫园", city="上海", time_range="month")

    with SessionLocal() as s:
        rows = s.query(Review).filter(Review.poi_name == "豫园").all()
    assert len(rows) == 1
    assert rows[0].source == "tavily"
    assert rows[0].time_range == "month"
    assert rows[0].expires_at is not None
