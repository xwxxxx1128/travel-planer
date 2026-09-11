"""Tavily 网页搜索相关单元测试（全程 mock，可离线运行）。

覆盖：
- TavilyMcpClient.search 是否按要求透传 time_range 时效参数；
- search_reviews 工具是否正确拼装「标题+来源链接+摘要」并优雅降级；
- fetch_tavily_reviews 返回结构（含 source='tavily'）。
"""
import asyncio
import json

import pytest

from tools.mcp_tavily_client import TavilyMcpClient
from tools import reviews_tools


class _FakeResult:
    def __init__(self, text: str):
        self.content = [type("C", (), {"text": text})()]


class _FakeSession:
    def __init__(self, recorded):
        self._recorded = recorded

    async def initialize(self):
        return None

    async def list_tools(self):
        tool = type("T", (), {"name": "tavily-search"})()
        return type("L", (), {"tools": [tool]})()

    async def call_tool(self, name, args):
        self._recorded.append((name, args))
        payload = {"results": [{"title": "故宫攻略", "url": "https://example.com/gugong", "content": "值得一看"}]}
        return _FakeResult(json.dumps(payload))


class _FakeClient(TavilyMcpClient):
    """覆盖 connect，避免真正拉起 tavily-mcp 子进程。"""

    def __init__(self):
        super().__init__()
        self._recorded = []

    async def connect(self):
        from contextlib import AsyncExitStack
        self._stack = AsyncExitStack()
        self._session = _FakeSession(self._recorded)
        self._tool_name = "tavily-search"
        self._ready = True


def _make_client(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(reviews_tools, "TavilyMcpClient", _FakeClient)
    return client


def test_search_passes_time_range(monkeypatch):
    client = _make_client(monkeypatch)
    asyncio.run(client.connect())
    asyncio.run(client.search("故宫 评价", time_range="month"))
    name, args = client._recorded[0]
    assert name == "tavily-search"
    assert args["query"] == "故宫 评价"
    assert args["time_range"] == "month"
    assert args["search_depth"] == "advanced"


def test_search_omits_time_range_when_none(monkeypatch):
    client = _make_client(monkeypatch)
    asyncio.run(client.connect())
    asyncio.run(client.search("故宫 评价"))
    _, args = client._recorded[0]
    assert "time_range" not in args


def test_search_reviews_formats_with_links(monkeypatch):
    _make_client(monkeypatch)
    # search_reviews 是 @tool 装饰的异步 StructuredTool，底层协程函数存在 .coroutine
    result = asyncio.run(reviews_tools.search_reviews.coroutine("故宫"))
    assert "来源链接" in result
    assert "https://example.com/gugong" in result
    assert "故宫攻略" in result


def test_search_reviews_empty_result(monkeypatch):
    # 让 call_tool 返回空 results
    class _EmptySession(_FakeSession):
        async def call_tool(self, name, args):
            return _FakeResult(json.dumps({"results": []}))

    class _EmptyClient(_FakeClient):
        async def connect(self):
            from contextlib import AsyncExitStack
            self._stack = AsyncExitStack()
            self._session = _EmptySession(self._recorded)
            self._tool_name = "tavily-search"
            self._ready = True

    monkeypatch.setattr(reviews_tools, "TavilyMcpClient", _EmptyClient)
    result = asyncio.run(reviews_tools.search_reviews.coroutine("故宫"))
    assert "未检索到" in result


def test_fetch_tavily_reviews_shape(monkeypatch):
    _make_client(monkeypatch)
    items = reviews_tools.fetch_tavily_reviews_sync("故宫", city="北京")
    assert isinstance(items, list) and items
    item = items[0]
    assert item["source"] == "tavily"
    assert item["poi_name"] == "故宫"
    assert item["city"] == "北京"
    assert set(["title", "url", "content"]) <= set(item.keys())
