"""app.services.langgraph_chat

对话 / 人工确认服务层。原仓库中该文件缺失（从未提交至 git），此处基于项目内已有的
`graph_chat` 包（LangGraph 多助理对话图）重建其接口，供 `app/api/routers/chat.py` 调用。

设计要点：
- 直接复用 graph_chat 的构建块编译出与 CLI/Gradio 版本一致的图，但**不**触发
  `finally_graph` 中的副作用（update_dates() 会覆盖航班库、draw_graph 需要额外依赖），
  以保证在 API 进程启动时可安全导入。
- 使用 langgraph 的 SqliteSaver 作为持久化检查点（落盘到 app/data/checkpoints.sqlite，
  容器内即 app_data 卷），每个会话以 session_id 作为 thread_id 隔离；进程重启后会话不丢失。
- 敏感工具（改签/预订/取消）前设置了 interrupt_before，需用户批准后才执行。

对外提供：handle_chat / resume_chat / get_pending_interrupt / get_history
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.constants import START, END
from langgraph.errors import GraphRecursionError
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition

from app.core.config import BASE_DIR
from graph_chat.assistant import CtripAssistant, assistant_runnable, primary_assistant_tools
from graph_chat.base_data_model import (
    ToBookExcursion,
    ToFlightBookingAssistant,
    ToHotelBookingAssistant,
)
from graph_chat.build_child_graph import (
    build_flight_graph,
    builder_excursion_graph,
    builder_hotel_graph,
)
from graph_chat.state import State
from tools.flights_tools import fetch_user_flight_information
from tools.tools_handler import create_tool_node_with_fallback

logger = logging.getLogger(__name__)

DEFAULT_PASSENGER_ID = "3442 587242"

# 单次对话请求的总时长预算（秒）。聊天接口是非流式的，一次查询会串行跑「路由→子助手→
# 工具→子助手→路由」多步，每步都调用大模型。当模型慢/限流时累计很容易超过前端 axios
# 的 120s 超时阈值，导致浏览器主动断开并提示“请求超时”。这里把后端整体限制在
# 预算内返回，确保前端总能收到响应（要么是答案，要么是友好的超时提示），不再出现硬超时。
_REQUEST_BUDGET = 60
# 流式端点专用：从流建立到结束的「总时长」硬上限（秒）。
# 与 _REQUEST_BUDGET（单节点间隔）不同，它是累计预算，确保无论图产出多频繁，
# 流最终一定会结束，杜绝前端“一直思考、只能重启后端”的现象。
# 配合 token 级流式（首字 ~2s 出现）与 recursion_limit=15，正常请求远不会触及该上限；
# 这里仅作为「真正卡死」时的兜底熔断，避免像原 480s 那样让用户空等 8 分钟。
_STREAM_BUDGET = 240
APPROVAL_PROMPT = (
    "AI助手马上根据你要求，执行相关操作。"
    "您是否批准上述操作？输入'y'继续；否则，请说明您请求的更改。"
)

# 真正的“写”类敏感工具集合（改签/预订/取消等会改动订单的操作）。只有在命中这些工具
# 时，才需要用户手动批准。其余一律视为只读/安全工具，不弹审批框。
_KNOWN_SENSITIVE = {
    "update_ticket_to_new_flight",
    "cancel_ticket",
    "book_hotel",
    "update_hotel",
    "cancel_hotel",
    "book_excursion",
    "update_excursion",
    "cancel_excursion",
}
# 只读/查询类工具：绝不需要审批（例如 search_flights 仅在“搜索航班”，不应弹出确认框）。
_READONLY_TOOLS = {
    "search_flights",
    "search_hotels",
    "search_trip_recommendations",
    "lookup_policy",
    "fetch_user_flight_information",
    "amap_search_poi",
    "amap_search_around",
    "amap_geocode",
    "amap_get_weather",
}


# 审批回执台账（approve / reject 后记录，刷新页面不再重复弹框、也不重复执行）
# 以 {session_id: {tool_call_id, ...}} 形式持久化到 data/ 目录，进程重启后依然有效。
# --------------------------------------------------------------------------- #
_APPROVAL_LEDGER_PATH = BASE_DIR / "data" / "approval_ledger.json"
_approval_ledger: Dict[str, set] = {}


def _load_approval_ledger() -> None:
    global _approval_ledger
    try:
        if _APPROVAL_LEDGER_PATH.exists():
            with open(_APPROVAL_LEDGER_PATH, "r", encoding="utf-8") as fh:
                data = _json.load(fh)
            _approval_ledger = {k: set(v) for k, v in data.items() if isinstance(v, list)}
    except Exception:  # noqa: BLE001
        _approval_ledger = {}


def _save_approval_ledger() -> None:
    try:
        with open(_APPROVAL_LEDGER_PATH, "w", encoding="utf-8") as fh:
            _json.dump(
                {k: list(v) for k, v in _approval_ledger.items()},
                fh,
                ensure_ascii=False,
                indent=2,
            )
    except Exception:  # noqa: BLE001
        pass


def _mark_resolved(session_id: str, tool_call_id: Optional[str]) -> None:
    if not tool_call_id:
        return
    _approval_ledger.setdefault(session_id, set()).add(tool_call_id)
    _save_approval_ledger()


def _is_resolved(session_id: str, tool_call_id: Optional[str]) -> bool:
    if not tool_call_id:
        return False
    return tool_call_id in _approval_ledger.get(session_id, set())


# --------------------------------------------------------------------------- #
# 编译对话图（与 graph_chat.finally_graph 结构一致，但不带副作用）
# --------------------------------------------------------------------------- #
# 用户航班信息缓存：fetch_user_flight_information.invoke({}) 每次都新建 sqlite 连接并查询，
# 而该工具在未传入具体乘客配置时始终返回默认乘客信息（进程内不变）。
# 缓存后可免去每次请求的无条件 DB 查询（对标 trip_assistant 中“按需/可缓存”的查询思路），
# 仅在首次请求时真正查库，后续直接复用，降低入口节点的固定开销。
# 注意：务必用默认乘客 ID（字符串）作 key，不能用 state["user_info"]（payload 列表不可哈希，
# 经 checkpointer 还原后会变成列表，直接 .get 会抛 TypeError）。
_user_info_cache: Dict[str, Any] = {}
_user_info_lock = threading.Lock()


def _get_user_info(state: State) -> Dict[str, Any]:
    key = DEFAULT_PASSENGER_ID
    cached = _user_info_cache.get(key)
    if cached is None:
        with _user_info_lock:
            cached = _user_info_cache.get(key)
            if cached is None:
                cached = fetch_user_flight_information.invoke({})
                _user_info_cache[key] = cached
    return {"user_info": cached}


def _route_primary_assistant(state: dict) -> str:
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        if tool_calls[0]["name"] == ToFlightBookingAssistant.__name__:
            return "enter_update_flight"
        if tool_calls[0]["name"] == ToHotelBookingAssistant.__name__:
            return "enter_book_hotel"
        if tool_calls[0]["name"] == ToBookExcursion.__name__:
            return "enter_book_excursion"
        return "primary_assistant_tools"
    raise ValueError("无效的路由")


def _route_to_workflow(state: dict) -> str:
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
    return dialog_state[-1]


def _build_graph():
    builder = StateGraph(State)
    builder.add_node("fetch_user_info", _get_user_info)
    builder.add_edge(START, "fetch_user_info")

    builder = build_flight_graph(builder)
    builder = builder_hotel_graph(builder)
    builder = builder_excursion_graph(builder)

    builder.add_node("primary_assistant", CtripAssistant(assistant_runnable))
    builder.add_node(
        "primary_assistant_tools",
        create_tool_node_with_fallback(primary_assistant_tools),
    )

    builder.add_conditional_edges(
        "primary_assistant",
        _route_primary_assistant,
        [
            "enter_update_flight",
            "enter_book_hotel",
            "enter_book_excursion",
            "primary_assistant_tools",
            END,
        ],
    )
    builder.add_edge("primary_assistant_tools", "primary_assistant")
    builder.add_conditional_edges("fetch_user_info", _route_to_workflow)

    return builder.compile(
        checkpointer=_checkpointer,
        interrupt_before=[
            "update_flight_sensitive_tools",
            "book_hotel_sensitive_tools",
            "book_excursion_sensitive_tools",
        ],
    )


# --------------------------------------------------------------------------- #
# 持久化检查点（SqliteSaver）
# 落盘到 <BASE_DIR>/data/checkpoints.sqlite；容器内 /app/data 即 app_data 卷，
# 重启后端进程后历史会话可恢复。check_same_thread=False 以兼容跨线程访问。
# --------------------------------------------------------------------------- #
_CHECKPOINT_DIR = BASE_DIR / "data"
try:
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
except Exception:  # 极端情况下目录无写权限也不阻塞图编译（退化为异常提示）
    logger.warning("无法创建检查点目录 %s", _CHECKPOINT_DIR)

_CHECKPOINT_PATH = _CHECKPOINT_DIR / "checkpoints.sqlite"
_conn = sqlite3.connect(str(_CHECKPOINT_PATH), check_same_thread=False, timeout=30)
_checkpointer = SqliteSaver(_conn)


graph = _build_graph()
_load_approval_ledger()


# --------------------------------------------------------------------------- #
# 会话辅助
# --------------------------------------------------------------------------- #
def _make_config(session_id: str, passenger_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "configurable": {
            "thread_id": session_id,
            "passenger_id": passenger_id or DEFAULT_PASSENGER_ID,
        }
    }


def _run_graph(input_payload, config) -> str:
    """驱动图并返回最后一条 AI 消息文本；若触发中断则返回审批提示。"""
    result = ""
    try:
        for event in graph.stream(input_payload, config, stream_mode="values", recursion_limit=15):
            messages = event.get("messages")
            if messages:
                message = messages[-1]
                if isinstance(message, AIMessage) and message.content:
                    content = message.content
                    # 多模态/分段 content 可能是 list，统一拼成字符串，避免下游 str 校验失败
                    if isinstance(content, list):
                        parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                parts.append(item.get("text", ""))
                            elif isinstance(item, str):
                                parts.append(item)
                        content = "".join(parts)
                    result = content
    except GraphRecursionError:
        # 模型反复调用工具导致步数超限：返回友好提示，而不是让流裸崩/无限挂起
        return (
            "抱歉，本次任务步骤过多（模型可能在反复调用工具，未能收敛）。"
            "请简化您的问题，或拆成更小的步骤（例如先只查酒店，再单独预订）后重试。"
        )
    state = graph.get_state(config)
    if state.next:  # 命中敏感工具，等待用户批准
        result = APPROVAL_PROMPT
    return result


def _extract_text(content: Any) -> str:
    """把 AIMessage.content（str 或分段 list）统一拼成字符串。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""


# 节点中文别名：让前端进度提示更友好（仅展示用，不影响逻辑）
_NODE_LABELS = {
    "fetch_user_info": "读取用户信息",
    "primary_assistant": "主助手思考",
    "primary_assistant_tools": "调用工具",
    "update_flight": "航班助手处理",
    "update_flight_sensitive_tools": "航班敏感操作",
    "book_hotel": "酒店助手处理",
    "book_hotel_sensitive_tools": "酒店敏感操作",
    "book_excursion": "游览助手处理",
    "book_excursion_sensitive_tools": "游览敏感操作",
    "enter_update_flight": "进入航班流程",
    "enter_book_hotel": "进入酒店流程",
    "enter_book_excursion": "进入游览流程",
}


async def stream_chat_events(req: Dict[str, Any]):
    """节点级 SSE 生成器：边跑图边推送进度/文本事件，连接持续有字节流动，
    前端不会再因“长时间零字节”而触发硬超时。

    产出事件类型：
      - status : 节点/工具进度（{type,node,text}）
      - message: 某节点产出的 AI 文本块（节点级，可能多条）
      - error  : 出错（{type,text}）
      - final  : 最终聚合结果（{type,reply,intent,confirm,escalated}），供前端覆盖文本/弹确认框
    事件以 SSE 的 `data: {json}\\n\\n` 形式 yield 出去。
    """
    session_id = req.get("session_id") or "default"
    message = (req.get("message") or "").strip()
    # 立即落盘用户提问：即使客户端中途刷新/断开，问题也不会丢
    if message:
        await asyncio.to_thread(_append_message, session_id, {"role": "user", "text": message})
    config = _make_config(session_id, req.get("passenger_id"))
    loop = asyncio.get_running_loop()
    queue: "asyncio.Queue" = asyncio.Queue()
    sentinel = object()
    last_reply = ""
    full_reply = ""        # 流式过程中累积的助手文本，用于增量落盘
    last_persist_len = 0   # 上次增量落盘时的长度，做限流

    def worker() -> None:
        nonlocal last_reply
        # 跟踪“当前这条 AI 消息是否已通过 token 流式吐出过文本”。
        # 若已吐出 → updates 送达完整 AIMessage 时不再重复发 message 事件（避免重复文本）；
        # 若未吐出（模型走非流式路径 / 网关不支持流）→ 退回旧行为，发完整 message 兜底。
        deltas_seen_for_current = False
        try:
            if not message:
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"type": "final", "reply": "请输入您的问题。", "intent": "general", "confirm": None, "escalated": False}
                )
                return
            # 关键优化：双流模式。
            # - "updates"：节点级事件（节点标签/工具完成/interrupt），用于进度提示与 final 聚合。
            # - "messages"：LLM token 级流，让首字在 ~2s 内出现，前端不再“一直思考”。
            #   对照 trip_assistant 纯 Python 版“单次 LLM 即返回”的体验：流式把整段等待
            #   摊薄成“逐字出现”，是消除“一直显示主助手在思考”最直接的改造。
            for event in graph.stream(
                {"messages": ("user", message)}, config,
                stream_mode=["updates", "messages"],
                recursion_limit=15,
            ):
                # list 模式下每条事件为 (mode, data, metadata)；防御性兼容各版本
                if isinstance(event, tuple) and len(event) >= 2:
                    mode, data = event[0], event[1]
                else:
                    mode, data = "updates", event
                if mode == "messages":
                    # data 形如 (message_chunk, metadata)
                    chunk = data[0] if isinstance(data, tuple) and data else data
                    if isinstance(chunk, AIMessageChunk):
                        text = _extract_text(chunk.content)
                        if text:
                            deltas_seen_for_current = True
                            last_reply += text  # token 累积为最终正文（兜底也由 updates 的完整消息覆盖）
                            loop.call_soon_threadsafe(
                                queue.put_nowait, {"type": "delta", "text": text}
                            )
                    continue
                # mode == "updates"
                for node, update in (data or {}).items():
                    if node == "__interrupt__":
                        # 命中敏感工具中断：先推一条提示，最终 final 会携带 confirm 载荷供前端弹框
                        loop.call_soon_threadsafe(
                            queue.put_nowait, {"type": "status", "text": APPROVAL_PROMPT}
                        )
                        continue
                    if node in _NODE_LABELS:
                        loop.call_soon_threadsafe(
                            queue.put_nowait, {"type": "status", "text": f"{_NODE_LABELS[node]}…"}
                        )
                    update = update or {}
                    msgs = update.get("messages") or []
                    for m in msgs:
                        if isinstance(m, AIMessage):
                            text = _extract_text(m.content)
                            if text:
                                # 以完整消息为准覆盖 token 累积，避免分片拼接误差
                                last_reply = text
                                # 若 token 流已实时吐出，不再重复发完整 message（防重复文本）；
                                # 否则作为兜底发一次，保证前端可见。
                                if not deltas_seen_for_current:
                                    loop.call_soon_threadsafe(
                                        queue.put_nowait, {"type": "message", "text": text}
                                    )
                            # 下一条 AIMessage 是新一轮 LLM 调用，重置标记
                            deltas_seen_for_current = False
                        elif isinstance(m, ToolMessage):
                            name = getattr(m, "name", "") or "工具"
                            loop.call_soon_threadsafe(
                                queue.put_nowait, {"type": "status", "text": f"工具「{name}」执行完成"}
                            )
        except GraphRecursionError:  # 图步数超限：模型反复调用工具未能收敛
            logger.warning("stream_chat 步数超限（session=%s）", session_id)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "error",
                    "text": "抱歉，本次任务步骤过多（模型可能在反复调用工具，未能收敛）。"
                    "请简化您的问题，或拆成更小的步骤（例如先只查酒店，再单独预订）后重试。",
                },
            )
        except Exception as exc:  # 模型/工具异常：推错误事件，不让流裸崩
            logger.exception("stream_chat worker failed (session=%s)", session_id)
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "text": f"对话处理出错：{exc}"}
            )
            return
        finally:
            # 图跑完（或中断）后，由主协程根据 state 决定 final/confirm，再发结束哨兵
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    # 心跳任务：周期性往队列塞 ping，保证 SSE 连接上始终有字节流动，
    # 避免被 nginx（默认 60s 无数据）或中间代理掐断，导致前端“一直思考到超时”。
    async def _heartbeat():
        try:
            while True:
                await asyncio.sleep(15)
                await queue.put({"__ping__": True})
        except asyncio.CancelledError:
            pass

    hb_task = asyncio.ensure_future(_heartbeat())
    fut = loop.run_in_executor(None, worker)
    deadline = time.monotonic() + _STREAM_BUDGET
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # 总预算耗尽：即便超时也先把已算出的答案落盘，刷新页面即可恢复
                logger.warning("stream_chat 总预算耗尽（session=%s）", session_id)
                await _persist_stream_result(session_id, req, config, last_reply, _pending(config))
                yield _sse_payload({"type": "error", "text": "本次请求处理超时（总时长上限）。请稍后重试，或换一个更简短的问题。"})
                return
            try:
                item = await asyncio.wait_for(queue.get(), timeout=min(remaining, _REQUEST_BUDGET))
            except asyncio.TimeoutError:
                # 两次产出间隔超预算仍无字节 → 超时时同样落盘已有答案，结束流
                logger.warning("stream_chat 产出间隔超时（session=%s）", session_id)
                await _persist_stream_result(session_id, req, config, last_reply, _pending(config))
                yield _sse_payload({"type": "error", "text": "模型响应较慢，本次请求已超时。请稍后重试，或换一个更简短的问题。"})
                return
            if item is sentinel:
                break
            if isinstance(item, dict) and item.get("__ping__"):
                # SSE 注释帧：客户端会忽略，但能保活连接
                yield b": ping\n\n"
                continue
            # 增量落盘：把已流式产出的助手文本实时写入历史，
            # 每累计约 500 字写一次，避免因频繁写盘拖慢响应，
            # 也保证任意时刻刷新都能恢复已产生的部分内容。
            # 注意：_upsert_assistant 每次都重读+重写整份历史文件，阈值过小（如原 120）
            # 会导致长会话里落盘 I/O 累积成 O(n²)；提到 500 可减少约 4 倍写盘次数。
            if item.get("type") in ("message", "delta"):
                chunk = item.get("text") or ""
                if chunk:
                    full_reply += chunk
                    if len(full_reply) - last_persist_len >= 500:
                        await asyncio.to_thread(_upsert_assistant, session_id, full_reply, None)
                        last_persist_len = len(full_reply)
            yield _sse_payload(item)

        # 流正常结束：根据最终状态构造聚合结果
        pending = _pending(config)
        resp = _base_response(req)
        resp.update(
            {
                "reply": last_reply or APPROVAL_PROMPT if pending else last_reply,
                "intent": _current_intent(config) or "general",
                "confirm": _pending_confirm(config) if pending else None,
                "escalated": pending,
            }
        )
        # 持久化本轮对话（用户提问 + 助手回复），刷新页面后可恢复
        await _persist_stream_result(session_id, req, config, resp["reply"], pending)
        yield _sse_payload({"type": "final", **resp})
    finally:
        # 停止心跳并清理 worker 线程；最多等 5s，避免流已结束时被卡住的 worker 拖住事件循环
        if not hb_task.done():
            hb_task.cancel()
        try:
            await asyncio.wait_for(fut, timeout=5)
        except Exception:
            pass


def _sse_payload(data: Dict[str, Any]) -> str:
    """把事件字典序列化成一行 SSE `data:` 帧。"""
    return f"data: {_json.dumps(data, ensure_ascii=False)}\n\n"


def _current_intent(config) -> Optional[str]:
    state = graph.get_state(config)
    dialog_state = (state.values or {}).get("dialog_state") or []
    return dialog_state[-1] if dialog_state else None


def _pending(config) -> bool:
    try:
        return bool(graph.get_state(config).next)
    except Exception:
        return False


def _summarize_tool(name: str, args: dict) -> tuple:
    """根据挂起的敏感工具名与参数，生成确认框的 action 与可读摘要。

    注意：search_flights 等只读工具不应出现在这里；若传入只读工具名直接返回空摘要，
    由调用方判定为“无需审批”。
    """
    if name == "update_ticket_to_new_flight":
        dep = args.get("departure_airport") or ""
        arr = args.get("arrival_airport") or ""
        new_fid = args.get("new_flight_id") or ""
        ticket = args.get("ticket_no") or ""
        return "book", (
            f"将机票 {ticket} 改签/预订至新航班（航班ID {new_fid}，{dep} → {arr}）"
        )
    if name == "cancel_ticket":
        ticket = args.get("ticket_no") or ""
        return "cancel", f"取消机票（票号 {ticket}）"
    if name in ("book_hotel", "update_hotel"):
        return "book", f"预订/修改酒店（{args.get('hotel') or args.get('name') or ''}）"
    if name == "cancel_hotel":
        return "cancel", f"取消酒店预订（{args.get('hotel') or args.get('name') or ''}）"
    if name in ("book_excursion", "update_excursion"):
        return "book", f"预订/修改游览（{args.get('excursion') or ''}）"
    if name == "cancel_excursion":
        return "cancel", f"取消游览预订（{args.get('excursion') or ''}）"
    # 只读/未知工具：返回空摘要，调用方据此跳过审批
    return "book", ""


def _pending_confirm(config) -> dict | None:
    """返回当前挂起的敏感操作的确认信息（含 action / summary / prompt），无则 None。

    关键修复：
    1. 优先选取真正“写”类敏感工具作为展示对象，避免把同批次里的 search_flights
       等只读工具误当成需要审批的操作（修复“执行敏感操作：search_flights”误报）。
    2. 只读工具（search_flights 等）一律视为无需审批，返回 None。
    3. 已在该会话“批准/拒绝”过的同一中断（按 tool_call_id 去重）不再重复要求审批，
       解决刷新页面反复弹框、重复执行的问题。
    """
    session_id = (config.get("configurable") or {}).get("session_id", "")
    try:
        state = graph.get_state(config)
    except Exception:
        return None
    if not state.next:
        return None
    msgs = (state.values or {}).get("messages", [])
    chosen: Optional[dict] = None
    for m in reversed(msgs):
        tcs = getattr(m, "tool_calls", None)
        if not tcs:
            continue
        # 先找真正的敏感工具（批调用中可能有 search_flights + 敏感工具并存）
        for tc in tcs:
            if tc.get("name") in _KNOWN_SENSITIVE:
                chosen = tc
                break
        if chosen is None:
            chosen = tcs[0]
        break
    if chosen is None:
        return None
    name = chosen.get("name") or ""
    args = chosen.get("args", {}) or {}
    tool_call_id = chosen.get("id")
    # 只读工具：绝不需要审批
    if name in _READONLY_TOOLS:
        return None
    # 已解决过的中断（用户已批准/拒绝）不再重复弹框
    if _is_resolved(session_id, tool_call_id):
        return None
    action, summary = _summarize_tool(name, args)
    if not summary:
        return None
    return {
        "action": action,
        "summary": summary,
        "prompt": APPROVAL_PROMPT,
        "id": tool_call_id,
    }


def _base_response(req: Dict[str, Any]) -> Dict[str, Any]:
    """构造 ChatResponse 所需的字段骨架。

    说明：原缺失模块会从工具结果中提取结构化的 flights/hotels/reviews/place，
    此处暂以空值/透传占位，保证接口可用；如需在前端展示结构化结果可在此补充提取逻辑。
    """
    return {
        "flights": [],
        "reviews": [],
        "hotels": [],
        "place": req.get("place") if isinstance(req, dict) else None,
        "handoff": None,
    }


def _error_response(message: str, req: Dict[str, Any]) -> Dict[str, Any]:
    resp = _base_response(req)
    resp.update(
        {
            "reply": message,
            "intent": "general",
            "confirm": None,
            "escalated": True,
            "handoff": {"action": "escalate", "reason": message, "target": "human"},
        }
    )
    return resp


# --------------------------------------------------------------------------- #
# 聊天历史持久化（独立于 LangGraph 检查点，保证刷新页面后可恢复完整消息）
# 落盘到 <BASE_DIR>/data/chat_history/<session_id>.json
# --------------------------------------------------------------------------- #
_CHAT_HISTORY_DIR = BASE_DIR / "data" / "chat_history"
try:
    _CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
except Exception:  # noqa: BLE001
    logger.warning("无法创建聊天历史目录 %s", _CHAT_HISTORY_DIR)

_chat_store_lock = threading.Lock()


def _safe_session_file(session_id: str) -> Path:
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_") or "default"
    return _CHAT_HISTORY_DIR / f"{safe}.json"


def _load_messages(session_id: str) -> List[Dict[str, Any]]:
    path = _safe_session_file(session_id)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _append_message(session_id: str, message: Dict[str, Any]) -> None:
    path = _safe_session_file(session_id)
    with _chat_store_lock:
        messages = _load_messages(session_id)
        messages.append(message)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            _json.dump(messages, fh, ensure_ascii=False, indent=2)
        tmp.replace(path)


def _upsert_assistant(session_id: str, assistant_text: str, confirm=None) -> None:
    """把本轮助手回复写入历史：若末条已是助手消息则覆盖其文本，否则追加。

    用于流式过程中的增量落盘，保证任意时刻刷新都能恢复已产生的内容。
    """
    if not assistant_text:
        return
    path = _safe_session_file(session_id)
    with _chat_store_lock:
        messages = _load_messages(session_id)
        entry = {
            "role": "assistant",
            "text": assistant_text,
            "reviews": [],
            "flights": [],
            "hotels": [],
            "confirm": confirm,
        }
        if messages and messages[-1].get("role") == "assistant":
            messages[-1] = entry
        else:
            messages.append(entry)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            _json.dump(messages, fh, ensure_ascii=False, indent=2)
        tmp.replace(path)


async def _persist_stream_result(
    session_id: str, req: Dict[str, Any], config, reply: str, pending: bool
) -> None:
    """把本轮助手回复落盘到 chat_history。用户提问已在流式开始时落盘，这里只写/更新助手回复。

    即便在超时分支也会调用，确保“答案已算出、只是 SSE 没传完”时，刷新页面即可恢复，
    不再出现“一直思考到超时、刷新才看到答案”的现象。reply 为空时不写空白助手气泡。
    """
    confirm = _pending_confirm(config) if pending else None
    text = (reply or "").strip() or (APPROVAL_PROMPT if pending else "")
    if not text:
        return
    await asyncio.to_thread(_upsert_assistant, session_id, text, confirm)


# --------------------------------------------------------------------------- #
# 对外接口
# --------------------------------------------------------------------------- #
async def handle_chat(req: Dict[str, Any]) -> Dict[str, Any]:
    session_id = req.get("session_id") or "default"
    message = (req.get("message") or "").strip()
    if not message:
        resp = _base_response(req)
        resp.update(
            {
                "reply": "请输入您的问题。",
                "intent": None,
                "confirm": None,
                "escalated": False,
            }
        )
        return resp

    config = _make_config(session_id, req.get("passenger_id"))
    try:
        # 同步图放到线程里执行，并用 wait_for 兜底总时长，避免模型慢/限流时请求无限挂起、
        # 前端在 120s 处主动断开而显示硬性的“请求超时”。
        reply = await asyncio.wait_for(
            asyncio.to_thread(_run_graph, {"messages": ("user", message)}, config),
            timeout=_REQUEST_BUDGET,
        )
    except asyncio.TimeoutError:
        logger.warning("handle_chat 超时（session=%s）", session_id)
        resp = _base_response(req)
        resp.update(
            {
                "reply": "模型响应较慢，本次请求已超时。请稍后重试，或换一个更简短的问题。",
                "intent": "general",
                "confirm": None,
                "escalated": False,
            }
        )
        return resp
    except Exception as exc:  # 模型/工具调用异常时优雅降级
        logger.exception("handle_chat failed for session=%s", session_id)
        return _error_response(f"对话处理出错：{exc}", req)

    pending = _pending(config)
    resp = _base_response(req)
    resp.update(
        {
            "reply": reply,
            "intent": _current_intent(config) or "general",
            "confirm": _pending_confirm(config) if pending else None,
            "escalated": pending,
        }
    )
    # 持久化本轮对话（用户提问 + 助手回复），保证刷新页面后可恢复
    await asyncio.to_thread(_append_message, session_id, {"role": "user", "text": message})
    await asyncio.to_thread(
        _append_message,
        session_id,
        {
            "role": "assistant",
            "text": reply,
            "reviews": resp.get("reviews", []),
            "flights": resp.get("flights", []),
            "hotels": resp.get("hotels", []),
            "confirm": _pending_confirm(config) if pending else None,
        },
    )
    return resp


async def resume_chat(session_id: str, approved: bool) -> Dict[str, Any]:
    config = _make_config(session_id)
    # 先记录本次中断已被处理（批准/拒绝），无论后续是否成功执行，刷新页面都不会再重复弹框
    try:
        confirm = _pending_confirm(config)
        if confirm and confirm.get("id"):
            _mark_resolved(session_id, confirm["id"])
    except Exception:  # noqa: BLE001
        pass
    try:
        if approved:
            try:
                reply = await asyncio.wait_for(
                    asyncio.to_thread(_run_graph, None, config),
                    timeout=_REQUEST_BUDGET,
                )
            except asyncio.TimeoutError:
                logger.warning("resume_chat 超时（session=%s）", session_id)
                resp = _base_response({})
                resp.update(
                    {
                        "reply": "模型响应较慢，本次确认操作已超时。请稍后重试或重新发起预订。",
                        "intent": "general",
                        "confirm": None,
                        "escalated": False,
                    }
                )
                return resp
        else:
            state = graph.get_state(config)
            messages = (state.values or {}).get("messages", [])
            # 找到最后一个待执行的敏感工具调用（即引发中断的那个）
            last_ai = None
            for m in reversed(messages):
                if getattr(m, "tool_calls", None):
                    last_ai = m
                    break
            if last_ai and last_ai.tool_calls:
                tc = last_ai.tool_calls[0]
                # 1) 记录用户拒绝：注入 ToolMessage，使 ToolNode 跳过真实执行
                graph.update_state(
                    config,
                    {
                        "messages": [
                            ToolMessage(
                                tool_call_id=tc["id"],
                                content="用户拒绝执行该敏感操作，操作已取消。",
                            )
                        ]
                    },
                )
                # 2) 清除状态里待确认的工具调用，确保图不会再因 interrupt_before 挂起
                try:
                    graph.update_state(
                        config,
                        {
                            "messages": [
                                AIMessage(
                                    id=last_ai.id,
                                    content=last_ai.content,
                                    tool_calls=[],
                                )
                            ]
                        },
                    )
                except Exception:
                    pass
                # 3) 恢复图（此时已无可执行的敏感工具，直接走向结束）
                try:
                    reply = _run_graph(None, config)
                except Exception:
                    reply = "您已取消该操作，未做任何改动。"
                if not reply:
                    reply = "您已取消该操作，未做任何改动。"
                # 4) 兜底：若仍挂起（例如 LLM 异常），强制结束中断，避免确认框反复弹出
                if _pending(config):
                    try:
                        graph.update_state(config, {"messages": []}, as_node="update_flight")
                    except Exception:
                        pass
            else:
                reply = "未找到待确认的操作。"
    except Exception as exc:
        logger.exception("resume_chat failed for session=%s", session_id)
        return _error_response(f"恢复对话出错：{exc}", {})

    pending = _pending(config)
    resp = _base_response({})
    resp.update(
        {
            "reply": reply,
            "intent": _current_intent(config) or "general",
            "confirm": _pending_confirm(config) if pending else None,
            "escalated": pending,
        }
    )
    # 持久化助手在恢复操作后的回复
    await asyncio.to_thread(
        _append_message,
        session_id,
        {
            "role": "assistant",
            "text": reply,
            "reviews": resp.get("reviews", []),
            "flights": resp.get("flights", []),
            "hotels": resp.get("hotels", []),
            "confirm": None,
        },
    )
    return resp


async def get_pending_interrupt(session_id: str) -> dict | None:
    return _pending_confirm(_make_config(session_id))


async def get_history(session_id: str) -> List[Dict[str, Any]]:
    """返回该会话已持久化的聊天记录（来源为独立 JSON 存储，刷新页面可恢复）。

    返回结构与前端期望一致：每条消息含 role（user/assistant）与 text，
    以及可选的结构化字段 reviews/flights/hotels/confirm。
    """
    return await asyncio.to_thread(_load_messages, session_id)
