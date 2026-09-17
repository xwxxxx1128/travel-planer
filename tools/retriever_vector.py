import os
import re
from pathlib import Path

import numpy as np
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings

from app.core.runtime_config import get_runtime_config
# 复用项目统一的 Chroma 单例（与评论检索共用 persist 目录），做真正的向量语义召回。
from app.services.knowledge import vector_store

basic_dir = Path(__file__).resolve().parent.parent

with open(f'{basic_dir}/order_faq.md', encoding='utf8') as f:
    faq_text = f.read()

docs = [{"page_content": txt} for txt in re.split(r"(?=\n##)", faq_text)]

embeddings_model = None


def get_embeddings_model():
    global embeddings_model
    if embeddings_model is None:
        runtime_config = get_runtime_config()
        embeddings_model = OpenAIEmbeddings(
            openai_api_key=runtime_config.openai_api_key or os.getenv('OPENAI_API_KEY'),
            openai_api_base=runtime_config.openai_base_url or os.getenv('OPENAI_BASE_URL'),
        )
    return embeddings_model


class VectorStoreRetriever:
    def __init__(self, docs: list, vectors: list):
        self._arr = np.array(vectors)
        self._docs = docs

    @classmethod
    def from_docs(cls, docs):
        embeddings = get_embeddings_model().embed_documents([doc["page_content"] for doc in docs])
        return cls(docs, embeddings)

    def query(self, query: str, k: int = 5) -> list[dict]:
        embed = get_embeddings_model().embed_query(query)
        scores = np.array(embed) @ self._arr.T
        top_k_idx = np.argpartition(scores, -k)[-k:]
        top_k_idx_sorted = top_k_idx[np.argsort(-scores[top_k_idx])]
        return [{**self._docs[idx], "similarity": float(scores[idx])} for idx in top_k_idx_sorted]


# 政策知识库在 Chroma 中的集合名（与评论集合 poi_reviews 隔离）。
_POLICY_COLLECTION = "policy_faq"


def _ensure_policy_indexed():
    """首次检索前把 FAQ 切片向量化并写入 Chroma 的 policy_faq 集合（仅 chroma 可用时）。"""
    if not vector_store.available():
        return
    if vector_store.count(_POLICY_COLLECTION) > 0:
        return
    emb_model = get_embeddings_model()
    embs = emb_model.embed_documents([d["page_content"] for d in docs])
    vector_store.upsert_documents([d["page_content"] for d in docs], _POLICY_COLLECTION, embs)


retriever = None

# 查询结果缓存：lookup_policy 每次都会触发 embed_query（一次 embedding 网络往返），
# 相同/相似问题重复命中时直接复用，省掉一次网络请求，降低政策类问答的固定延迟。
_policy_cache: dict[str, str] = {}
_POLICY_CACHE_LIMIT = 64


def get_retriever():
    global retriever
    if retriever is None:
        retriever = VectorStoreRetriever.from_docs(docs)
    return retriever


@tool
def lookup_policy(query: str) -> str:
    """在退改签/订单 FAQ 知识库中检索与用户问题最相关的政策片段。
    主路径使用 Chroma 向量库做语义相似度召回（真正的 RAG）；
    当 chroma 不可用（未安装/未初始化）时，降级到 numpy 内存向量 + 点积相似度，保证功能不中断。
    """
    key = (query or "").strip()
    if key and key in _policy_cache:
        return _policy_cache[key]

    emb_model = get_embeddings_model()
    q_emb = emb_model.embed_query(query)

    if vector_store.available():
        # 主路径：Chroma 向量库语义检索
        _ensure_policy_indexed()
        docs_hit = vector_store.query_documents(q_emb, _POLICY_COLLECTION, top_k=3)
    else:
        # 兜底路径：numpy 内存向量 + 点积相似度（无持久化，重启即重建）
        docs_hit = [d["page_content"] for d in get_retriever().query(query, k=3)]

    result = "\n\n".join(docs_hit)
    if key:
        # 简单 LRU：超限时清空，避免无界增长
        if len(_policy_cache) >= _POLICY_CACHE_LIMIT:
            _policy_cache.clear()
        _policy_cache[key] = result
    return result


if __name__ == '__main__':
    print(lookup_policy('怎么才能退票呢？'))
