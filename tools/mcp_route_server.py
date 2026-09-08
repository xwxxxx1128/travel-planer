"""路线规划 MCP Server。

本文件把 `route_planner.py` 中已实现的路线规划能力以 MCP（Model Context
Protocol）标准协议对外暴露，便于被任意支持 MCP 的客户端（Claude Desktop、
Cursor、自研 Agent 等）以统一方式调用，而不必关心底层是高德接口还是本地估算。

设计原则：
- 保留原实现：复用 `route_planner` 中的 `plan_route_core` 与
  `get_route_distance_core`，这两个是无状态的纯函数，直接调用即可，
  不重复实现路线规划逻辑，避免两套代码失真。
- 原 LangChain `@tool` 路径（`route_planner.py` 末尾的 `plan_route` /
  `get_route_distance`）保持不变，继续供 graph 内部 Agent 使用。
- MCP 工具仅做「协议适配层」：把核心函数的入参/出参映射到 MCP 的 JSON
  Schema，并保留原有中文注释与算法说明。
- Key 来源：高德 Key 优先读环境变量 `AMAP_WEB_API_KEY`，与项目运行期配置
  保持一致；MCP server 本身无状态，可直接独立部署在容器内。

启动方式（二选一）：
1) stdio（本地进程间通信，最常见的 MCP 接入方式）：
       python tools/mcp_route_server.py
2) SSE（远程/跨进程 HTTP 长连接，便于服务化部署）：
       MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8001 python tools/mcp_route_server.py

注意：本文件刻意不使用 `from __future__ import annotations`，因为 mcp 1.9.4
的 `from_function` 在解析参数注解时直接 `issubclass(annotation, Context)`，
而该 future import 会把注解变成字符串导致判定失败。保持注解为真实对象即可。
"""

import os

from mcp.server.fastmcp import FastMCP

# ---- 复用原路线规划核心逻辑（无状态纯函数，不重复实现） ----
from tools.route_planner import get_route_distance_core, plan_route_core

# 高德 Key 与运行期配置共用同一个环境变量，保证本地/容器内取值一致。
# 若运行环境已通过 runtime_config 写入 .env，这里也能直接读取。
AMAP_WEB_KEY = os.getenv("AMAP_WEB_API_KEY", "")

# ---- 创建 MCP Server 实例 ----
# FastMCP 会自动根据函数签名与类型注解生成 JSON Schema，
# 因此工具描述（docstring）与参数类型都很重要。
mcp = FastMCP(
    "route-planner",
    # 通过环境变量切换传输方式，默认 stdio（本地进程通信）。
    transport=os.getenv("MCP_TRANSPORT", "stdio"),
)


@mcp.tool(description="路径规划工具，根据多个地点之间的交通方式规划最佳路线（旅行商问题 TSP 优化）")
def plan_route(
    destinations: list,
    start_point: str = "",
    end_point: str = "",
    transport_mode: str = "driving",
) -> dict:
    """规划多个地点之间的最佳路线。

    内部实现要点（与 route_planner 保持一致）：
    - 并发请求高德方向 API：N 个点对用线程池并发，8 点约 3-5s，避免逐对串行的 1-2 分钟。
    - TSP 规模自适应：≤8 点暴力枚举最优顺序；>8 点贪心近似，保证响应速度。
    - 容错：高德不可用或无 Key 时自动降级为本地直线估算，不抛错。

    参数:
        destinations: 目的地列表（地址文本，或 "lng,lat" 坐标串）。
        start_point: 可选起点；不传则把第一个目的地当作起点。
        end_point: 可选终点；传入后固定为路线末尾。
        transport_mode: 交通方式 driving / walking / transit / smart。
    """
    return plan_route_core(destinations, start_point, end_point, transport_mode)


@mcp.tool(description="获取两点之间的路程和时间工具，根据交通方式计算两点之间的距离和预计时间")
def get_route_distance(
    origin: str,
    destination: str,
    transport_mode: str = "driving",
) -> dict:
    """获取两点之间的路程和时间。

    内部实现要点（与 route_planner 保持一致）：
    - smart 模式先用本地估算挑交通方式，再调真实接口。
    - 高德失败时降级为本地估算（直线距离 * 经验速度）。

    参数:
        origin: 起点（地址文本，或 "lng,lat" 坐标串）。
        destination: 终点（地址文本，或 "lng,lat" 坐标串）。
        transport_mode: 交通方式 driving / walking / transit / smart。
    """
    return get_route_distance_core(origin, destination, transport_mode)


def main() -> None:
    """入口：按 MCP_TRANSPORT 选择 stdio 或 sse 启动。

    - stdio：标准输入/输出通信，适合本地 CLI / 桌面客户端拉起子进程。
    - sse：Server-Sent Events over HTTP，适合服务化部署（如容器内常驻）。
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        # SSE 模式下显式指定监听地址与端口，便于 Docker 暴露。
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8001"))
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="sse")
    else:
        # 默认 stdio：由父进程通过 stdin/stdout 通信，无需端口。
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
