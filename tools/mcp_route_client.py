"""路线规划 MCP 客户端封装。

当路线规划以独立 MCP Server（`mcp_route_server.py`）方式部署时，本项目内
部（如 HTTP 接口、其他 Agent）可通过本客户端以 MCP 协议调用它，而不是直
接 import `route_planner` 的核心函数。这样实现「调用方」与「实现方」解耦：
- 实现方可独立扩展、独立部署、独立扩缩容；
- 调用方只依赖 MCP 协议（工具名 + JSON 入参），不感知底层是高德还是本地估算。

两种调用模式：
1) 本地子进程（stdio）：由本客户端拉起 `mcp_route_server.py` 子进程，通过
   stdio 通信。无需额外端口，适合同机部署。
2) 远程 SSE：连接已常驻的 MCP Server（如 Docker 内 `mcp-route` 服务暴露的
   SSE 端口），跨进程/跨容器调用。

环境变量：
- MCP_ROUTE_MODE: local（默认，stdio 子进程） | remote（SSE 远程）
- MCP_ROUTE_URL: remote 模式下的 SSE 地址，默认 http://localhost:8001/sse

注意：本文件不使用 `from __future__ import annotations`，保持类型注解为真实
对象，与 mcp 的字符串注解解析兼容（详见 mcp_route_server.py 顶部说明）。
"""

import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

# mcp 客户端依赖（requirements.txt 已包含 mcp==1.9.4）
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client

_DEFAULT_SSE_URL = os.getenv("MCP_ROUTE_URL", "http://localhost:8001/sse")


class RouteMcpClient:
    """路线规划 MCP 客户端。

    典型用法（异步上下文管理器，自动管理子进程/连接生命周期）：
        async with RouteMcpClient() as client:
            result = await client.plan_route(["故宫", "颐和园"])
    """

    def __init__(self, mode: Optional[str] = None) -> None:
        # mode 默认读环境变量，缺省为本地 stdio 子进程模式。
        self.mode = (mode or os.getenv("MCP_ROUTE_MODE", "local")).lower()
        self._stack = AsyncExitStack()
        self._session: Optional[ClientSession] = None
        # 缓存已初始化标志，避免重复拉起子进程。
        self._ready = False

    async def __aenter__(self) -> "RouteMcpClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        """建立与 MCP Server 的会话连接。"""
        if self._ready:
            return

        if self.mode == "remote":
            # 远程 SSE：连接常驻的 MCP Server SSE 端点。
            read, write = await self._stack.enter_async_context(
                sse_client(_DEFAULT_SSE_URL)
            )
        else:
            # 本地 stdio：拉起 mcp_route_server.py 子进程并通信。
            server_script = os.path.join(
                os.path.dirname(__file__), "mcp_route_server.py"
            )
            params = StdioServerParameters(
                command="python",
                args=[server_script],
                # 透传高德 Key，保证子进程能正常调用路线规划。
                env={**os.environ, "MCP_TRANSPORT": "stdio"},
            )
            read, write = await self._stack.enter_async_context(
                stdio_client(params)
            )

        self._session = await self._stack.enter_async_context(
            ClientSession(read, write)
        )
        # initialize 握手：交换协议版本与能力信息。
        await self._session.initialize()
        self._ready = True

    async def close(self) -> None:
        """关闭连接并释放子进程/网络资源。"""
        await self._stack.aclose()
        self._session = None
        self._ready = False

    async def plan_route(
        self,
        destinations: List[str],
        start_point: str = "",
        end_point: str = "",
        transport_mode: str = "driving",
    ) -> Dict[str, Any]:
        """调用 MCP 工具 `plan_route`（多目的地路线规划）。"""
        if not self._session:
            raise RuntimeError("MCP 客户端未连接，请先调用 connect() 或使用 async with")
        result = await self._session.call_tool(
            "plan_route",
            {
                "destinations": destinations,
                "start_point": start_point,
                "end_point": end_point,
                "transport_mode": transport_mode,
            },
        )
        return _parse_tool_result(result)

    async def get_route_distance(
        self,
        origin: str,
        destination: str,
        transport_mode: str = "driving",
    ) -> Dict[str, Any]:
        """调用 MCP 工具 `get_route_distance`（两点距离与时间）。"""
        if not self._session:
            raise RuntimeError("MCP 客户端未连接，请先调用 connect() 或使用 async with")
        result = await self._session.call_tool(
            "get_route_distance",
            {
                "origin": origin,
                "destination": destination,
                "transport_mode": transport_mode,
            },
        )
        return _parse_tool_result(result)


def _parse_tool_result(result: Any) -> Dict[str, Any]:
    """把 MCP 工具返回内容解析为 Python 字典。

    MCP 工具返回的是结构化的 Content 列表，文本内容多为 JSON 字符串，
    这里尽量还原为可序列化的 dict，失败则原样返回文本。
    """
    try:
        text = result.content[0].text
    except (AttributeError, IndexError, TypeError):
        return {"raw": str(result)}
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return {"message": text}


def run_sync(coro):
    """兼容同步代码的事件循环辅助：在已有/新建 loop 中运行协程。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # 已在异步上下文中，用 run_until_complete 的替代方案需另起线程，
        # 这里简单回退到新建 loop 的嵌套执行不推荐，故直接抛错提示。
        raise RuntimeError("已在异步事件中，请直接使用 async 接口")
    return asyncio.new_event_loop().run_until_complete(coro)
