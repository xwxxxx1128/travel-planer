"""工具异常降级单测：各工具在「无 Key / 外部 API 失败 / 无结果」等异常路径下应优雅降级。

Agent 的健壮性体现在：工具在异常路径下应返回友好提示字符串，而不是抛异常导致整条
链路崩断。本测试逐一触发各工具的异常/降级路径，断言「触发异常路径后仍优雅降级（不抛异常）」。
"""
import asyncio
import json

from tools import route_planner
from tools.amap_tools import amap_search_poi
from tools.weather_tools import amap_get_weather
from tools.reviews_tools import search_reviews
from tools import retriever_vector as rv


def _runs_without_raising(fn):
    """执行 fn，返回 (是否不抛异常, 返回结果)。"""
    try:
        return True, fn()
    except Exception as exc:  # noqa: BLE001
        return False, repr(exc)


def test_tool_degradation_success_rate(monkeypatch):
    """触发各工具异常路径，统计优雅降级成功率。"""
    # 1) 高德 POI 搜索：无 Key → 返回失败提示（不抛异常）
    monkeypatch.setattr("tools.amap_tools.get_amap_api_key", lambda user_id=None: "")

    cases = []
    # amap_search_poi 无 Key
    cases.append(("amap_search_poi.no_key", lambda: amap_search_poi.invoke({"keywords": "酒店"})))
    # amap_get_weather 无 Key
    monkeypatch.setattr("tools.weather_tools.get_amap_key", lambda user_id=None: "")
    cases.append(("amap_get_weather.no_key", lambda: amap_get_weather.invoke({"location": "北京"})))

    # 2) 路线规划：核心函数抛异常 → plan_route 捕获并返回「路径规划失败」
    def _boom(*a, **k):
        raise RuntimeError("高德不可用")
    monkeypatch.setattr(route_planner, "plan_route_core", _boom)
    cases.append(("plan_route.exception", lambda: route_planner.plan_route.invoke({"destinations": ["A", "B"]})))

    # 3) get_route_distance：MCP 客户端抛异常 → 返回「获取路线失败」
    class _ErrClient:
        async def get_route_distance(self, origin, destination, transport_mode="driving"):
            raise RuntimeError("SSE 连接失败")
    async def _fake_get_client():
        return _ErrClient()
    monkeypatch.setattr(route_planner, "_get_route_mcp_client", _fake_get_client)
    route_distance_coroutine = getattr(route_planner.get_route_distance, "coroutine")
    cases.append((
        "get_route_distance.exception",
        lambda: asyncio.run(route_distance_coroutine("A", "B")),
    ))

    # 4) 评价检索：Tavily 无结果 → 返回「未检索到」
    async def _empty_reviews(*a, **k):
        return []
    monkeypatch.setattr("tools.reviews_tools.fetch_tavily_reviews", _empty_reviews)
    search_reviews_coroutine = getattr(search_reviews, "coroutine")
    cases.append(("search_reviews.empty", lambda: asyncio.run(search_reviews_coroutine("故宫"))))

    # 5) 政策 RAG：Chroma 不可用 → 降级 numpy 内存向量（返回非空，不抛异常）
    from unittest.mock import MagicMock
    fake_vs = MagicMock()
    fake_vs.available.return_value = False
    monkeypatch.setattr(rv, "vector_store", fake_vs)
    monkeypatch.setattr(rv, "get_embeddings_model", lambda: type(
        "_Emb", (), {
            "embed_query": lambda s, q: [0.1] * 8,
            "embed_documents": lambda s, ts: [[0.1] * 8 for _ in ts],
        }
    )())
    cases.append(("lookup_policy.chroma_down", lambda: rv.lookup_policy.invoke({"query": "退票政策"})))

    # 统计：所有异常路径都应优雅降级（不抛异常）
    results = {}
    for name, fn in cases:
        ok, out = _runs_without_raising(fn)
        results[name] = {"ok": ok, "returns_str": isinstance(out, str)}
        assert ok, f"{name} 应优雅降级而非抛异常: {out}"

    success = sum(1 for v in results.values() if v["ok"])
    print("[METRIC] tool_degradation =", json.dumps({
        "total_paths": len(results),
        "graceful_degraded": success,
        "success_rate": round(success / len(results), 4),
        "details": results,
    }, ensure_ascii=False))
    assert success == len(results)
