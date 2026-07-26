from datetime import datetime

from sqlalchemy import String, DateTime, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FlightBooking(Base):
    __tablename__ = 'flights'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(index=True)
    flight_no: Mapped[str] = mapped_column(String(32), nullable=False)
    departure_city: Mapped[str] = mapped_column(String(64), nullable=False)
    arrival_city: Mapped[str] = mapped_column(String(64), nullable=False)
    depart_time: Mapped[str] = mapped_column(String(32), nullable=False)
    arrive_time: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
