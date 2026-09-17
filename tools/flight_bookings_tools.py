"""个人航班（「我的航班」）对话工具：查看 / 预订 / 取消。

这些工具在 LangGraph 图内被「航班子助手」调用。因航班订单按用户隔离，工具需要
知道「当前是哪个用户」：用户身份通过图运行配置 config.configurable.user_id 注入
（见 app/services/langgraph_chat.py 的 _make_config），LangChain 会把 RunnableConfig
自动注入到带该注解的参数，不进入工具参数 schema。
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.services import flight as flight_service

logger = logging.getLogger(__name__)


def _user_id_from_config(config: Optional[RunnableConfig]) -> Optional[int]:
    if not config:
        return None
    configurable = config.get("configurable") or {}
    raw = configurable.get("user_id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


@tool
def list_my_flights(config: RunnableConfig = None) -> str:
    """查看当前登录用户本人的航班预订单（我的航班 / 我的机票 / 我的行程 / 我的预订）。

    与 search_flights 的区别：search_flights 查的是任意城市之间的航班班次；
    本工具查的是当前用户本人已登记的航班订单（存于应用自己的库，按用户隔离）。
    """
    user_id = _user_id_from_config(config)
    if not user_id:
        return "无法识别当前用户，请先登录后再查看「我的航班」。"

    items = flight_service.list_items(user_id)
    if not items:
        return "你当前还没有已预订的航班。"

    lines = []
    for it in items:
        line = (
            f"- {it['flight_no']} {it['departure_city']}→{it['arrival_city']} "
            f"起飞 {it['depart_time']} 到达 {it['arrive_time']}"
        )
        if it.get("price") is not None:
            line += f"，价格 {it['price']}"
        if it.get("booking_no"):
            line += f"（订单号 {it['booking_no']}）"
        lines.append(line)
    return "你当前共有 %d 条航班预订单：\n%s" % (len(items), "\n".join(lines))


@tool
def book_flight(
    flight_no: str,
    departure_city: str,
    arrival_city: str,
    depart_time: str,
    arrive_time: str,
    price: float = 0.0,
    config: RunnableConfig = None,
) -> str:
    """为当前登录用户登记一条航班预订单（下单即写入「我的航班」）。

    参数应来自用户确认的航班：航班号 flight_no、出发城市 departure_city、到达城市
    arrival_city、起飞时间 depart_time、到达时间 arrive_time、价格 price。
    时间请用「YYYY-MM-DD HH:MM」这类可读格式。
    """
    user_id = _user_id_from_config(config)
    if not user_id:
        return "无法识别当前用户，请先登录后再预订航班。"

    item = flight_service.add_item(
        user_id,
        flight_no=flight_no,
        departure_city=departure_city,
        arrival_city=arrival_city,
        depart_time=depart_time,
        arrive_time=arrive_time,
        price=price or None,
    )
    return (
        f"已为你预订 {item['flight_no']} {item['departure_city']}→{item['arrival_city']}"
        f"（起飞 {item['depart_time']}，到达 {item['arrive_time']}），"
        f"订单号 {item['booking_no']}。"
    )


@tool
def cancel_my_flight(flight_no_or_id: str, config: RunnableConfig = None) -> str:
    """取消当前登录用户「我的航班」中的某条预订单（按航班号精确匹配，或按订单 id）。"""
    user_id = _user_id_from_config(config)
    if not user_id:
        return "无法识别当前用户，请先登录后再取消航班。"

    text = (flight_no_or_id or "").strip()
    if not text:
        return "请提供要取消的航班号或订单 id。"

    count = flight_service.cancel_by_flight_no(user_id, text)
    if count:
        return f"已取消你的航班订单（{text}），共 {count} 条。"

    if text.isdigit():
        row = flight_service.cancel_item(user_id, int(text))
        if row:
            return f"已取消订单 id={text}（{row['flight_no']}）。"

    return f"「我的航班」中没有找到航班号为 {text} 的未取消订单。"
