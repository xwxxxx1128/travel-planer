from dataclasses import dataclass


@dataclass
class VectorSearchTool:
    """Chroma 检索占位实现；可后续接真实向量库。"""

    def search_reviews(self, poi_name: str, top_k: int = 3) -> list[dict]:
        return [
            {'poi_name': poi_name, 'content': f'{poi_name} 用户评论摘要 1', 'score': 0.92},
            {'poi_name': poi_name, 'content': f'{poi_name} 用户评论摘要 2', 'score': 0.88},
        ][:top_k]
