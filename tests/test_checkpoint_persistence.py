"""SqliteSaver 检查点持久化单测：验证 LangGraph 会话状态落盘后可恢复。

LangGraph 图用 SqliteSaver 把每个会话（thread_id）的状态落盘到 sqlite，进程重启
后会话可恢复。本测试用一个最小 StateGraph + 临时 sqlite 文件，模拟「跑图 → 关闭
连接（进程重启）→ 新连接恢复状态」的完整往返，统计多会话恢复成功率。
"""
import json
import sqlite3

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict


class _St(TypedDict):
    messages: Annotated[list, add_messages]


def _build_saver(db_file):
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    return conn, SqliteSaver(conn)


def _make_graph(checkpointer):
    builder = StateGraph(_St)

    def noop(state):
        return {"messages": [("assistant", "已收到")]}

    builder.add_node("noop", noop)
    builder.add_edge(START, "noop")
    builder.add_edge("noop", END)
    return builder.compile(checkpointer=checkpointer)


def test_checkpoint_persistence_roundtrip(tmp_path):
    """跑图 → 关连接（模拟重启）→ 新连接恢复，统计多会话恢复成功率。"""
    db_file = tmp_path / "checkpoints.sqlite"
    n_sessions = 5

    # 第一阶段：写入 N 个会话
    conn, saver = _build_saver(db_file)
    graph = _make_graph(saver)
    configs = []
    for i in range(n_sessions):
        cfg = {"configurable": {"thread_id": f"th-{i}"}}
        result = graph.invoke({"messages": [HumanMessage(content=f"hello {i}")]}, cfg)
        assert result["messages"][-1].content == "已收到"
        configs.append(cfg)
    conn.close()  # 模拟进程重启：关闭数据库连接

    # 第二阶段：新连接 + 新 saver + 重新编译图，恢复各会话状态
    conn2, saver2 = _build_saver(db_file)
    graph2 = _make_graph(saver2)
    recovered = 0
    for cfg in configs:
        state = graph2.get_state(cfg)
        if state is not None and state.values and state.values.get("messages"):
            recovered += 1
    conn2.close()

    print("[METRIC] checkpoint_persistence =", json.dumps({
        "sessions": n_sessions,
        "recovered": recovered,
        "recovery_rate": round(recovered / n_sessions, 4),
        "note": "SqliteSaver 落盘 sqlite，进程重启后可恢复会话状态",
    }, ensure_ascii=False))
    assert recovered == n_sessions
