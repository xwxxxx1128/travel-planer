from fastapi import APIRouter

from app.schemas.crawl import CrawlReviewsRequest, CrawlReviewsResponse
from tools.reviews_tools import fetch_tavily_reviews_sync

router = APIRouter()


@router.post('/reviews', response_model=CrawlReviewsResponse)
def crawl_reviews(payload: CrawlReviewsRequest):
    """评价检索接口：改用 Tavily 网页搜索（不再使用 Bing 爬虫）。

    返回近一个月内的互联网公开评价/攻略材料；调用失败或无结果时 reviews 为空。
    """
    reviews = fetch_tavily_reviews_sync(
        payload.poi_name, city=payload.city or "", max_results=5, time_range='month',
        force_refresh=payload.force_refresh,
    )
    return CrawlReviewsResponse(
        poi_name=payload.poi_name,
        city=payload.city,
        crawled=False,
        reviews=reviews,
    )
