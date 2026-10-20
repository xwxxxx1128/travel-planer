"""审批台账幂等去重单测：验证 HITL 确认框刷新后不重复弹/不重复执行。

针对「刷新页面后敏感操作确认框反复弹出 / 重复执行」的问题，审批台账以
{session_id: {tool_call_id}} 形式持久化，批准/拒绝后按 tool_call_id 去重，
刷新页面不再重复弹框、不重复执行。

本测试验证：
1) 幂等去重：同一 tool_call_id 被反复标记 N 次，台账仍只保留 1 条（去重率）。
2) 会话隔离：不同 session / 不同 tool_call_id 互不影响。
3) 持久化：重新加载台账文件（模拟进程重启）后去重标记仍生效。
"""
import json

import app.services.langgraph_chat as lc


def test_approval_ledger_idempotency(monkeypatch, tmp_path):
    """验证幂等去重 + 会话隔离 + 持久化恢复。"""
    ledger_file = tmp_path / "approval_ledger.json"
    monkeypatch.setattr(lc, "_APPROVAL_LEDGER_PATH", ledger_file)
    monkeypatch.setattr(lc, "_approval_ledger", {})

    # 模拟同一 tool_call_id 被重复标记 100 次（如用户反复刷新触发）
    repeat = 100
    for _ in range(repeat):
        lc._mark_resolved("sess-1", "tc-1")
    # 另一会话、另一 tool_call_id 各 1 次
    lc._mark_resolved("sess-1", "tc-2")
    lc._mark_resolved("sess-2", "tc-1")

    # 幂等去重：sess-1 下应只有 tc-1、tc-2 两条，而非 102 条
    sess1 = lc._approval_ledger.get("sess-1", set())
    assert len(sess1) == 2
    assert lc._is_resolved("sess-1", "tc-1")
    assert lc._is_resolved("sess-1", "tc-2")
    # 会话隔离：sess-2 的 tc-1 不影响 sess-1 的判定（且互不重复）
    assert lc._is_resolved("sess-2", "tc-1")
    assert not lc._is_resolved("sess-1", "tc-999")

    # 持久化恢复：清空内存、重新加载台账文件（模拟进程重启）
    lc._approval_ledger = {}
    lc._load_approval_ledger()
    assert lc._is_resolved("sess-1", "tc-1")

    print("[METRIC] approval_idempotency =", json.dumps({
        "repeat_marks": repeat,
        "deduped_records": len(lc._approval_ledger.get("sess-1", set())),
        "dedup_rate": round(1 - len(lc._approval_ledger.get("sess-1", set())) / repeat, 4),
        "persisted_after_reload": lc._is_resolved("sess-1", "tc-1"),
    }, ensure_ascii=False))
