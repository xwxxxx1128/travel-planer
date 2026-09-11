"""路线规划 MCP 工具（get_route_distance）单元测试（mock，离线）。

验证：格式化输出是否包含距离/时间，以及调用异常时是否优雅降级。
通过 monkeypatch 掉 _get_route_mcp_client，避免真正拉起 route MCP Server。
"""
import asyncio

from tools import route_planner


class _FakeRouteClient:
    def __init__(self, payload):
        self._payload = payload

    async def get_route_distance(self, origin, destination, transport_mode="driving"):
        return self._payload


def test_get_route_distance_format(monkeypatch):
    payload = {
        "from": "北京",
        "to": "上海",
        "distance": 1000,
        "distance_km": 1.0,
        "duration": 600,
        "duration_minutes": 10,
        "transport_mode": "driving",
        "transport_mode_label": "开车",
    }
    async def _fake_get_client():
        return _FakeRouteClient(payload)

    monkeypatch.setattr(route_planner, "_get_route_mcp_client", _fake_get_client)
    # get_route_distance 是 @tool 装饰的异步 StructuredTool，底层协程函数存在 .coroutine
    out = asyncio.run(
        route_planner.get_route_distance.coroutine("北京", "上海", "driving")
    )
    assert "距离：1000米" in out
    assert "公里" in out
    assert "预计时间" in out
    assert "开车" in out


def test_get_route_distance_error(monkeypatch):
    class _ErrClient:
        async def get_route_distance(self, origin, destination, transport_mode="driving"):
            raise RuntimeError("SSE 连接失败")

    async def _fake_get_client():
        return _ErrClient()

    monkeypatch.setattr(route_planner, "_get_route_mcp_client", _fake_get_client)
    out = asyncio.run(route_planner.get_route_distance.coroutine("A", "B", "driving"))
    assert "获取路线失败" in out
