from pydantic import BaseModel


class CrawlReviewsRequest(BaseModel):
    poi_name: str
    city: str | None = None
    category: str = 'poi'
    force_refresh: bool = False


class CrawlReviewsResponse(BaseModel):
    poi_name: str
    city: str | None = None
    crawled: bool
    reviews: list[dict]
