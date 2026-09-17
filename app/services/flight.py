"""个人航班（「我的航班」）服务：按用户隔离的 增 / 查 / 取消。

数据存于应用自身的库（SQLAlchemy，表 flight_bookings），与 demo 班次库
（travel_new.sqlite 的 flights 班次表）彻底解耦，不会被班次数据集的重置 / 日期平移影响。

供两处复用：
- REST 接口（app/api/routers/flight.py）：前端「我的航班」页面 查看 / 取消；
- 对话工具（tools/flight_bookings_tools.py）：子助手在对话中 预订 / 取消 / 查看
  （订单只能由 AI 代订，前端不提供自助登记）。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.db.session import SessionLocal
from app.models.flight import FlightBooking

logger = logging.getLogger(__name__)

STATUS_BOOKED = "booked"
STATUS_CANCELLED = "cancelled"


def _gen_booking_no() -> str:
    """生成订单号（形如 FB-XXXXXXXXXX），便于软取消后追溯。"""
    return "FB-" + uuid.uuid4().hex[:10].upper()


def _to_dict(item: FlightBooking) -> Dict[str, Any]:
    return {
        "id": item.id,
        "booking_no": item.booking_no,
        "flight_no": item.flight_no,
        "departure_city": item.departure_city,
        "arrival_city": item.arrival_city,
        "depart_time": item.depart_time,
        "arrive_time": item.arrive_time,
        "price": item.price,
        "status": item.status,
        "created_at": item.created_at,
    }


def list_items(user_id: int, include_cancelled: bool = False) -> List[Dict[str, Any]]:
    """返回该用户的航班预订单（最新在前）。默认不含已取消的。"""
    session = SessionLocal()
    try:
        query = session.query(FlightBooking).filter(FlightBooking.user_id == user_id)
        if not include_cancelled:
            query = query.filter(FlightBooking.status != STATUS_CANCELLED)
        rows = query.order_by(FlightBooking.id.desc()).all()
        return [_to_dict(r) for r in rows]
    finally:
        session.close()


def add_item(
    user_id: int,
    flight_no: str,
    departure_city: str,
    arrival_city: str,
    depart_time: str,
    arrive_time: str,
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """为当前用户登记一条航班预订单。

    同一用户、同一航班号且同一起飞时间视为重复预订，直接返回已有项（不重复写入）。
    """
    session = SessionLocal()
    try:
        existing = (
            session.query(FlightBooking)
            .filter(
                FlightBooking.user_id == user_id,
                FlightBooking.flight_no == flight_no,
                FlightBooking.depart_time == depart_time,
                FlightBooking.status != STATUS_CANCELLED,
            )
            .first()
        )
        if existing:
            return _to_dict(existing)

        item = FlightBooking(
            user_id=user_id,
            booking_no=_gen_booking_no(),
            flight_no=flight_no,
            departure_city=departure_city,
            arrival_city=arrival_city,
            depart_time=depart_time,
            arrive_time=arrive_time,
            price=price,
            status=STATUS_BOOKED,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return _to_dict(item)
    finally:
        session.close()


def cancel_item(user_id: int, item_id: int) -> Optional[Dict[str, Any]]:
    """按 id 取消（软取消，校验归属）。返回取消后的记录；不存在或无权操作返回 None。"""
    session = SessionLocal()
    try:
        row = (
            session.query(FlightBooking)
            .filter(FlightBooking.user_id == user_id, FlightBooking.id == item_id)
            .first()
        )
        if not row:
            return None
        row.status = STATUS_CANCELLED
        session.commit()
        session.refresh(row)
        return _to_dict(row)
    finally:
        session.close()


def cancel_by_flight_no(user_id: int, flight_no: str) -> int:
    """按航班号取消（仅未取消的），返回取消条数。"""
    session = SessionLocal()
    try:
        rows = (
            session.query(FlightBooking)
            .filter(
                FlightBooking.user_id == user_id,
                FlightBooking.flight_no == flight_no,
                FlightBooking.status != STATUS_CANCELLED,
            )
            .all()
        )
        for row in rows:
            row.status = STATUS_CANCELLED
        session.commit()
        return len(rows)
    finally:
        session.close()
