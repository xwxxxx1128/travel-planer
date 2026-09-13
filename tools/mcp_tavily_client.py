"""Tavily 网页搜索 MCP 客户端封装。

评价功能（search_reviews）改用 Tavily 网页搜索获取互联网公开游记/攻略材料，
不再使用自研爬虫抓取。本客户端以 MCP 协议连接 Tavily MCP Server（stdio 拉起子
进程），调用其搜索工具拿到标题、摘要与来源链接，交给大模型聚合提炼。

设计要点（对应需求）：
- 不持久化第三方原文：本客户端只把搜索结果在内存中返回给调用方（Agent），
  由 Agent 工具把材料交给大模型，不在本地库/向量库落盘。
- 优雅降级：缺少 TAVILY_API_KEY 或 MCP Server 拉起失败时，search() 抛错，
  调用方据此如实告知用户「未获取到相关材料」，绝不编造。

环境变量：
- TAVILY_API_KEY: Tavily API Key（务必配置，否则无结果）
- TAVILY_MCP_COMMAND: 启动 Tavily MCP Server 的命令，默认 `npx -y tavily-mcp`
  （需要 Node 环境；也可指向 Python 版 `uvx tavily-mcp` 或自托管 SSE 服务地址）

注意：本文件不使用 `from __future__ import annotations`，保持类型注解为真实
对象，与 mcp 的注解解析兼容（详见 mcp_route_client.py 顶部说明）。
"""

import json
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# 显式把项目根 .env 加载进进程环境变量：本模块用 os.getenv 读取 TAVILY_API_KEY /
# TAVILY_MCP_COMMAND，而 pydantic-settings 只把 .env 读进 settings 对象、不会写回
# os.environ。主动 load_dotenv() 后，无论本模块被谁导入、是否裸跑，都能读到 .env，
# 不再依赖"别的模块恰好调过 load_dotenv"这一隐式副作用。
load_dotenv()

# 默认命令 `tavily-mcp` 指 PATH 上的可执行文件：Docker 镜像已在构建期预装，
# 运行时直接执行镜像内二进制（无联网下载、不依赖 Node）。
# 本地开发环境通常未安装该命令，拉起子进程会报 [WinError 2] 系统找不到指定的文件；
# 此时用 TAVILY_MCP_COMMAND 覆盖为隔离形态（避免把 mcp 升级到 2.x 污染项目 venv）：
#   TAVILY_MCP_COMMAND=uvx tavily-mcp     # uvx 在临时隔离环境运行（需 uv）
#   TAVILY_MCP_COMMAND=npx -y tavily-mcp  # Node 官方版（需 Node）
_DEFAULT_MCP_COMMAND = os.getenv("TAVILY_MCP_COMMAND", "tavily-mcp")


class TavilyMcpClient:
    """Tavily 网页搜索 MCP 客户端。

    典型用法（异步上下文管理器，自动管理子进程生命周期）：
        async with TavilyMcpClient() as client:
            results = await client.search("故宫 游客评价 攻略")
        # results: [{"title": ..., "url": ..., "content": ...}, ...]
    """

    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._session: Optional[ClientSession] = None
        # 缓存已发现的搜索工具名（不同 MCP Server 版本命名可能不同）。
        self._tool_name: Optional[str] = None
        self._ready = False

    async def __aenter__(self) -> "TavilyMcpClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        """建立与 Tavily MCP Server 的会话连接（stdio 子进程模式）。"""
        if self._ready:
            return
        if not os.getenv("TAVILY_API_KEY"):
            raise RuntimeError("未配置 TAVILY_API_KEY，无法连接 Tavily MCP Server")

        # 解析启动命令（支持带参数的字符串，如 "npx -y tavily-mcp"）。
        parts = _DEFAULT_MCP_COMMAND.split()
        command, args = parts[0], parts[1:]
        params = StdioServerParameters(
            command=command,
            args=args,
            # 透传 TAVILY_API_KEY，供子进程内的 Tavily MCP Server 鉴权。
            env={**os.environ, "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        # initialize 握手：交换协议版本与能力信息。
        await self._session.initialize()
        # 探测实际搜索工具名（tavily-search / web_search 等）。
        self._tool_name = await self._discover_tool()
        self._ready = True

    async def _discover_tool(self) -> str:
        """在已连接的 Server 上查找网页搜索工具名。"""
        tools = await self._session.list_tools()
        for tool in tools.tools:
            name = tool.name.lower()
            if "tavily" in name or "web" in name or "search" in name:
                return tool.name
        if tools.tools:
            return tools.tools[0].name
        raise RuntimeError("Tavily MCP Server 未暴露任何可用工具")

    async def close(self) -> None:
        """关闭连接并释放子进程资源。"""
        await self._stack.aclose()
        self._session = None
        self._tool_name = None
        self._ready = False

    async def search(
        self,
        query: str,
        max_results: int = 5,
        time_range: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """调用 Tavily 搜索，返回 [{title, url, content}]。

        只取标题、来源链接与摘要，供大模型聚合；不落盘第三方原文。
        :param time_range: 时效范围（如 "day"/"week"/"month"/"year"），用于召回较新内容；
                            为 None 时由 server 默认（通用搜索）。
        """
        if not self._session or not self._tool_name:
            raise RuntimeError("Tavily MCP 客户端未连接，请先 connect() 或使用 async with")
        args: Dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
        }
        # Tavily MCP Server 不识别 None，仅在显式传入时附带时效参数。
        if time_range:
            args["time_range"] = time_range
        result = await self._session.call_tool(self._tool_name, args)
        return _normalize(result)


def _normalize(result: Any) -> List[Dict[str, Any]]:
    """把 MCP 工具返回内容规整为统一的 [{title, url, content}] 列表。"""
    try:
        text = result.content[0].text
    except (AttributeError, IndexError, TypeError):
        return []

    # Tavily MCP 通常返回 JSON 字符串：{"results":[{"title","url","content"}]}
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return [{"title": "", "url": "", "content": text}]

    items = data.get("results") or data.get("related_results") or []
    out: List[Dict[str, Any]] = []
    for item in items:
        out.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content") or item.get("raw_content") or "",
            }
        )
    return out
