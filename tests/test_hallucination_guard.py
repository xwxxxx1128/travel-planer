"""幻觉拦截（后置校验）单测：验证「未检索即作答」的强制检索触发/不触发判定。

针对「模型未检索工具却凭自身知识直接作答」导致幻觉（编造评价 / 航班号）的问题，
主助手节点内做了后置校验：评价类 / 航班类提问若「未调用工具 + 无系统预取材料」即
直接作答，则注入一次「强制检索」提示后重试。

本测试直接复刻 assistant.py 中后置校验的判定条件（_is_review_query /
_called_search_reviews / _has_prefetched_review_ctx / _is_flight_query /
_called_any_flight_tool / _has_prefetched_flight_ctx），用一组「应拦截 / 不应拦截」
场景验证判定规则的正确率。
"""
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from graph_chat.assistant import (
    _is_review_query,
    _called_search_reviews,
    _has_prefetched_review_ctx,
    _is_flight_query,
    _called_any_flight_tool,
    _has_prefetched_flight_ctx,
)

_REVIEW_CTX_MARK = "【评价检索"
_FLIGHT_CTX_MARK = "【航班班次检索"


def _ai_text(text):
    return AIMessage(content=text)


def _ai_tool(name):
    return AIMessage(content="", tool_calls=[{"name": name, "args": {}, "id": "1"}])


def _should_nudge_review(messages):
    """复刻 tripAssistant 中评价类「强制检索」的触发条件。"""
    return (
        _is_review_query(messages)
        and not _called_search_reviews(messages)
        and not _has_prefetched_review_ctx(messages)
    )


def _should_nudge_flight(messages):
    """复刻 tripAssistant 中航班类「强制检索」的触发条件。"""
    return (
        _is_flight_query(messages)
        and not _called_any_flight_tool(messages)
        and not _has_prefetched_flight_ctx(messages)
    )


def _evaluate_guard(cases):
    """cases: [(消息列表, 期望是否拦截)]，返回正确率与统计。"""
    correct = sum(1 for msgs, expect in cases if (_should_nudge_review(msgs) or _should_nudge_flight(msgs)) == expect)
    return {
        "total": len(cases),
        "correct": correct,
        "accuracy": round(correct / len(cases), 4),
    }


def test_review_guard_coverage():
    """评价类后置校验：应拦截（未检索即作答）与不应拦截（已检索/有材料）的判定。"""
    cases = [
        # 应拦截：评价提问 + 未调用 search_reviews + 无预取材料
        ([HumanMessage(content="故宫值得去吗"), _ai_text("故宫是著名景点")], True),
        ([HumanMessage(content="西湖好玩吗")], True),
        ([HumanMessage(content="青岛小珠山的游客评价怎么样")], True),
        # 不应拦截：已调用 search_reviews
        ([HumanMessage(content="故宫值得去吗"), _ai_tool("search_reviews")], False),
        # 不应拦截：已有系统预取材料
        ([HumanMessage(content=f"{_REVIEW_CTX_MARK}材料·预取】..."), _ai_text("基于材料作答")], False),
        # 不应拦截：非评价类提问（天气）
        ([HumanMessage(content="北京今天天气怎么样")], False),
    ]
    r = _evaluate_guard(cases)
    assert r["accuracy"] == 1.0
    print("[METRIC] review_guard =", json.dumps(r, ensure_ascii=False))


def test_flight_guard_coverage():
    """航班类后置校验：应拦截（未调用航班工具）与不应拦截的判定。"""
    cases = [
        # 应拦截：航班提问 + 未调用任何航班工具 + 无预取
        ([HumanMessage(content="北京到上海有哪些航班")], True),
        ([HumanMessage(content="广州飞深圳的班次")], True),
        # 不应拦截：已调用 search_flights
        ([HumanMessage(content="北京到上海有哪些航班"), _ai_tool("search_flights")], False),
        # 不应拦截：已有系统预取班次材料
        ([HumanMessage(content=f"{_FLIGHT_CTX_MARK}结果·预取】..."), _ai_text("基于数据作答")], False),
        # 不应拦截：非航班类提问
        ([HumanMessage(content="帮我规划行程")], False),
    ]
    r = _evaluate_guard(cases)
    assert r["accuracy"] == 1.0
    print("[METRIC] flight_guard =", json.dumps(r, ensure_ascii=False))
