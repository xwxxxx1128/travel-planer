from fastapi import APIRouter

from app.schemas.crawl import CrawlReviewsRequest, CrawlReviewsResponse
from app.services.knowledge import crawler_service, vector_store, CrawlRequest

router = APIRouter()


@router.post('/reviews', response_model=CrawlReviewsResponse)
def crawl_reviews(payload: CrawlReviewsRequest):
    should_crawl = payload.force_refresh or crawler_service.need_refresh(payload.poi_name)
    if should_crawl:
        reviews = crawler_service.crawl_reviews(CrawlRequest(poi_name=payload.poi_name, city=payload.city, category=payload.category))
        vector_store.upsert_reviews(reviews)
        return CrawlReviewsResponse(poi_name=payload.poi_name, city=payload.city, crawled=True, reviews=reviews)

    reviews = vector_store.search_reviews(payload.poi_name)
    return CrawlReviewsResponse(poi_name=payload.poi_name, city=payload.city, crawled=False, reviews=reviews)
