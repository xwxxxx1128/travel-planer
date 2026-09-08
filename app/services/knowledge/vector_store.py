from pathlib import Path
import json

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
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))

    def _fallback_file(self) -> Path:
        return self.persist_dir / 'reviews.jsonl'

    def upsert_reviews(self, reviews: list[dict], collection_name: str = 'poi_reviews') -> None:
        if self._client is None:
            with self._fallback_file().open('a', encoding='utf-8') as handle:
                for item in reviews:
                    handle.write(json.dumps(item, ensure_ascii=False) + '\n')
            return

        collection = self._client.get_or_create_collection(collection_name)
        documents = [item['content'] for item in reviews]
        ids = [f"{item.get('poi_name', 'poi')}-{index}" for index, item in enumerate(reviews)]
        metadatas = [{k: v for k, v in item.items() if k != 'content'} for item in reviews]
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def search_reviews(self, query: str, collection_name: str = 'poi_reviews', top_k: int = 3) -> list[dict]:
        if self._client is None:
            path = self._fallback_file()
            if not path.exists():
                return []
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
            return [row for row in rows if query.lower() in row.get('poi_name', '').lower() or query in row.get('content', '')][:top_k]

        collection = self._client.get_or_create_collection(collection_name)
        result = collection.query(query_texts=[query], n_results=top_k)
        documents = result.get('documents', [[]])[0]
        metadatas = result.get('metadatas', [[]])[0]
        return [{**meta, 'content': doc} for meta, doc in zip(metadatas, documents)]

    # ------------------------------------------------------------------
    # 通用文本文档接口（供政策 FAQ 等纯文本知识库的 RAG 召回使用）
    # 与上面的 reviews 接口共用同一个 Chroma 客户端，只是集合名与元数据不同。
    # ------------------------------------------------------------------
    def available(self) -> bool:
        """chroma 是否可用（上层据此决定走向量库还是降级到内存 / numpy）。"""
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
            with self._fallback_file().open('a', encoding='utf-8') as handle:
                for doc in documents:
                    handle.write(json.dumps({'page_content': doc}, ensure_ascii=False) + '\n')
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
