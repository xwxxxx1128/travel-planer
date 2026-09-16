from datetime import datetime

from pydantic import BaseModel, Field


class WishlistItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    city: str | None = None
    address: str | None = None
    lng: float | None = None
    lat: float | None = None
    note: str | None = None
    source: str | None = "manual"


class WishlistItemResponse(BaseModel):
    id: int
    name: str
    city: str | None = None
    address: str | None = None
    lng: float | None = None
    lat: float | None = None
    note: str | None = None
    source: str | None = None
    created_at: datetime | None = None
