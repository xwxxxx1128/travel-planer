from datetime import datetime

from pydantic import BaseModel


class FlightBookingResponse(BaseModel):
    """个人航班订单的响应模型（订单由 AI 助手在对话中代为预订，不支持自助登记）。"""

    id: int
    booking_no: str | None = None
    flight_no: str
    departure_city: str
    arrival_city: str
    depart_time: str
    arrive_time: str
    price: float | None = None
    # booked=已预订；cancelled=已取消
    status: str = "booked"
    created_at: datetime | None = None
