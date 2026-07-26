from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    user_id: int | None = None
    trip_name: str = Field(default='智能行程')
    travel_days: int = Field(default=2, ge=1, le=30)
    destinations: list[str] = Field(default_factory=list)
    preference: str = Field(default='省时')
    city: str | None = None


class DayPlanItem(BaseModel):
    time: str
    name: str
    category: str
    transport_mode: str | None = None
    distance_km: float | None = None
    duration_min: int | None = None
    note: str | None = None


class PlanResponse(BaseModel):
    day_index: int
    title: str
    items: list[DayPlanItem]
    meals: list[str]
    note: str


class TravelPlanResponse(BaseModel):
    itinerary_id: int | None = None
    trip_name: str
    preference: str
    summary: str
    days: list[PlanResponse]
    hotel_suggestions: list[dict]
    restaurant_suggestions: list[dict]
    review_snippets: list[dict]
    transport_summary: list[dict]
