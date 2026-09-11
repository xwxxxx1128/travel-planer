"""政策 RAG（lookup_policy）单元测试（mock，离线）。

验证两条路径：
- chroma 可用时：走 Chroma 向量语义召回，并首次自动建索引（upsert_documents）；
- chroma 不可用时：降级到 numpy 内存向量，绝不调用 chroma。
"""
from unittest.mock import MagicMock

from tools import retriever_vector as rv


class _FakeEmb:
    """返回固定维度假向量，避免真实调用 OpenAI Embeddings（省网络）。"""

    def embed_documents(self, texts):
        return [[0.1] * 8 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 8


def test_lookup_policy_chroma_path(monkeypatch):
    fake = MagicMock()
    fake.available.return_value = True
    fake.count.return_value = 0  # 首次 → 触发索引写入
    fake.query_documents.return_value = ["退票规则A", "退票规则B"]
    monkeypatch.setattr(rv, "vector_store", fake)
    monkeypatch.setattr(rv, "get_embeddings_model", lambda: _FakeEmb())

    # lookup_policy 是 @tool 装饰的 StructuredTool，用公开 .invoke() 调用底层函数
    out = rv.lookup_policy.invoke("怎么才能退票呢")
    assert "退票规则A" in out and "退票规则B" in out
    fake.upsert_documents.assert_called_once()  # 首次检索前自动建索引


def test_lookup_policy_chroma_skip_reindex(monkeypatch):
    fake = MagicMock()
    fake.available.return_value = True
    fake.count.return_value = 5  # 已索引 → 不应重复写入
    fake.query_documents.return_value = ["已有索引的片段"]
    monkeypatch.setattr(rv, "vector_store", fake)
    monkeypatch.setattr(rv, "get_embeddings_model", lambda: _FakeEmb())

    out = rv.lookup_policy.invoke("退票手续费多少")
    assert "已有索引的片段" in out
    fake.upsert_documents.assert_not_called()


def test_lookup_policy_numpy_fallback(monkeypatch):
    fake = MagicMock()
    fake.available.return_value = False  # chroma 不可用 → 走 numpy 兜底
    monkeypatch.setattr(rv, "vector_store", fake)
    monkeypatch.setattr(rv, "get_embeddings_model", lambda: _FakeEmb())

    out = rv.lookup_policy.invoke("酒店预订相关政策")
    assert isinstance(out, str) and out.strip()
    # 兜底路径不得触碰 chroma 查询
    fake.query_documents.assert_not_called()
    fake.upsert_documents.assert_not_called()
