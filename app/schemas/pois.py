from pydantic import BaseModel


class POIResponse(BaseModel):
    id: int
    name: str
    city: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    tags: str | None = None
    description: str | None = None


class HotelResponse(BaseModel):
    id: int
    name: str
    rating: float | None = None
    price_level: int | None = None
    tags: str | None = None
    address: str | None = None
    note: str | None = None


class RestaurantResponse(BaseModel):
    id: int
    name: str
    rating: float | None = None
    price_level: int | None = None
    cuisine: str | None = None
    tags: str | None = None
    note: str | None = None


class ReviewResponse(BaseModel):
    id: int
    poi_name: str
    source: str
    rating: float | None = None
    label: str | None = None
    content: str
