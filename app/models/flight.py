from datetime import datetime

from sqlalchemy import String, DateTime, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FlightBooking(Base):
    """个人航班预订单（「我的航班」）。

    与 demo 班次库（travel_new.sqlite 里的 flights 班次表）彻底区分：
    本表存的是「某个用户订了哪些航班」，按 user_id 隔离，一个账号一份。
    """

    __tablename__ = 'flight_bookings'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(index=True, nullable=False)
    # 订单号（软取消时保留记录，便于追溯）
    booking_no: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    flight_no: Mapped[str] = mapped_column(String(32), nullable=False)
    departure_city: Mapped[str] = mapped_column(String(64), nullable=False)
    arrival_city: Mapped[str] = mapped_column(String(64), nullable=False)
    depart_time: Mapped[str] = mapped_column(String(32), nullable=False)
    arrive_time: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    # booked=已预订；cancelled=已取消（软取消，不删数据）
    status: Mapped[str] = mapped_column(String(16), default='booked', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
