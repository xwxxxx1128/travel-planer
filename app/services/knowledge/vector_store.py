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
