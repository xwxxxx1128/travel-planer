"""路线规划 MCP Server（stdio 本地子进程）传输握手单测。

验证路线规划 MCP Server（tools/mcp_route_server.py）能通过 stdio 传输被 MCP 客户端
（RouteMcpClient）拉起、完成协议握手（initialize）、并暴露正确的工具列表。

说明：
- 本测试通过 stdio 拉起本地 python 子进程（mcp_route_server.py），不依赖高德 Key
  （initialize / list_tools 无需调用高德接口），离线可复现。
- SSE 传输需独立部署的 MCP Server 常驻服务（MCP_TRANSPORT=sse），不在单测中拉起。
"""
import asyncio
import json
import os

from tools.mcp_route_client import RouteMcpClient

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_route_mcp_stdio_handshake_and_tools(monkeypatch):
    """验证 stdio 握手成功 + 暴露 plan_route / get_route_distance 两个工具。

    部署前提：stdio 子进程模式下，RouteMcpClient 直接以
    `python mcp_route_server.py` 拉起子进程，其 `import tools` 需要项目根目录
    位于子进程的 sys.path（PYTHONPATH）。Docker 内已配置工作目录，本地测试需
    显式注入 PYTHONPATH，否则子进程报 `No module named 'tools'`。
    """
    monkeypatch.setenv(
        "PYTHONPATH", _ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")
    )

    async def run():
        async with RouteMcpClient() as client:
            tools = await client._session.list_tools()
            return sorted(t.name for t in tools.tools)

    names = asyncio.run(run())

    print("[METRIC] mcp_stdio =", json.dumps({
        "transport": "stdio",
        "handshake": "ok",
        "exposed_tools": names,
    }, ensure_ascii=False))
    assert "plan_route" in names
    assert "get_route_distance" in names
