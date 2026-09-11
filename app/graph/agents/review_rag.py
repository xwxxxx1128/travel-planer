from app.schemas.plan import PlanRequest
from tools.reviews_tools import fetch_tavily_reviews_sync


class ReviewRAGAgent:
    """景点评价 RAG Agent。

    改用 Tavily 网页搜索获取互联网公开的评价/攻略材料（不再使用 Bing 自研爬虫），
    返回 [{poi_name, city, title, url, content, source}] 供行程计划页展示。
    调用失败 / 无结果时返回空列表，由上层如实告知，绝不编造。
    """

    def run(self, payload: PlanRequest) -> list[dict]:
        results = []
        for poi_name in payload.destinations[:3]:
            results.extend(
                fetch_tavily_reviews_sync(poi_name, city=payload.city or "")
            )
        return results
