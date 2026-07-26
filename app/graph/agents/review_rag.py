from dataclasses import dataclass

from app.schemas.plan import PlanRequest
from app.services.knowledge import crawler_service, vector_store, CrawlRequest


@dataclass
class ReviewRAGAgent:
    def run(self, payload: PlanRequest) -> list[dict]:
        results = []
        for poi_name in payload.destinations[:3]:
            if crawler_service.need_refresh(poi_name):
                reviews = crawler_service.crawl_reviews(CrawlRequest(poi_name=poi_name, city=payload.city, category='poi'))
                vector_store.upsert_reviews(reviews)
            results.extend(vector_store.search_reviews(poi_name))
        return results
