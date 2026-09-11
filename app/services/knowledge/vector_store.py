from pathlib import Path
from urllib.parse import urlparse

try:
    import chromadb
except Exception:  # pragma: no cover
    chromadb = None

from app.core.config import settings


class ChromaStore:
    def __init__(self) -> None:
        self.persist_dir = Path(settings.CHROMA_PERSIST_DIR)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        if chromadb is not None:
            # 优先连独立的 Chroma HTTP 服务（docker-compose 里的 chroma 服务），
            # 仅在未配置 CHROMA_HTTP_URL 时退回本地嵌入式 PersistentClient（便于本地开发）。
            if settings.CHROMA_HTTP_URL:
                self._client = self._build_http_client(settings.CHROMA_HTTP_URL)
            else:
                self._client = chromadb.PersistentClient(path=str(self.persist_dir))

    @staticmethod
    def _build_http_client(url: str):
        parsed = urlparse(url)
        host = parsed.hostname or url
        port = parsed.port or 8000
        # HttpClient 创建时并不立即建连，真正请求时才连 chroma 服务。
        return chromadb.HttpClient(host=host, port=port)

    # ------------------------------------------------------------------
    # 通用文本文档接口（供政策 FAQ 等纯文本知识库的 RAG 召回使用）
    # ------------------------------------------------------------------
    def available(self) -> bool:
        """chroma 是否可用（上层据此决定走向量库还是降级到 numpy 内存向量）。"""
        return self._client is not None

    def count(self, collection_name: str = 'policy_faq') -> int:
        """返回指定集合的文档数量（chroma 不可用时为 0）。"""
        if self._client is None:
            return 0
        return self._client.get_or_create_collection(collection_name).count()

    def upsert_documents(
        self,
        documents: list[str],
        collection_name: str = 'policy_faq',
        embeddings: list | None = None,
    ) -> None:
        """
        写入文本片段到指定集合。
        :param embeddings: 若提供则直接写入预计算向量（保证与查询向量同属一个 embedding 空间）；
                           不提供则交由 chroma 默认 embedding 函数处理。
        """
        if self._client is None:
            # 无 chroma 时的兜底：本路径在实践中不会被 RAG 主流程命中
            # （lookup_policy 在 chroma 不可用时走 numpy 内存向量），此处仅做无操作。
            return

        collection = self._client.get_or_create_collection(collection_name)
        ids = [f'doc-{index}' for index in range(len(documents))]
        if embeddings is not None:
            collection.upsert(ids=ids, documents=documents, embeddings=embeddings)
        else:
            collection.upsert(ids=ids, documents=documents)

    def query_documents(
        self,
        query_embedding: list[float],
        collection_name: str = 'policy_faq',
        top_k: int = 3,
    ) -> list[str]:
        """用预计算的查询向量在指定集合里取 top-k 最相似片段（返回文档原文列表）。"""
        if self._client is None:
            return []
        collection = self._client.get_or_create_collection(collection_name)
        result = collection.query(query_embeddings=[query_embedding], n_results=top_k)
        return result.get('documents', [[]])[0]
