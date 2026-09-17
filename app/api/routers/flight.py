"""个人航班（「我的航班」）接口：查看 / 取消（按当前登录用户隔离）。

注意：**不提供“自助登记”接口**——航班订单只能由 AI 助手在对话中代为预订
（见 tools/flight_bookings_tools.py 的 book_flight），避免用户手工录入与真实班次无关的数据。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.schemas.flight import FlightBookingResponse
from app.services import flight as flight_service

router = APIRouter()


@router.get('', response_model=list[FlightBookingResponse])
def list_flights(
    include_cancelled: bool = False,
    current: dict = Depends(get_current_user),
):
    """返回当前用户的航班预订单（默认只返回未取消的）。"""
    return flight_service.list_items(current["id"], include_cancelled=include_cancelled)


@router.delete('/{item_id}')
def cancel_flight(item_id: int, current: dict = Depends(get_current_user)):
    """取消当前用户的一条航班预订单（软取消，保留记录）。"""
    row = flight_service.cancel_item(current["id"], item_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="航班预订单不存在或无权操作",
        )
    return {"success": True, "id": item_id, "status": row["status"]}
