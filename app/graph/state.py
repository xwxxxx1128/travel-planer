from dataclasses import dataclass


@dataclass
class TravelGraphState:
    user_input: str = ''
    route_plan: dict | None = None
    lodging_plan: dict | None = None
    rag_notes: list[dict] | None = None
    itinerary_id: int | None = None
