from pydantic import BaseModel


class FlightResponse(BaseModel):
    id: int
    flight_no: str
    departure_city: str
    arrival_city: str
    depart_time: str
    arrive_time: str
    price: float | None = None
