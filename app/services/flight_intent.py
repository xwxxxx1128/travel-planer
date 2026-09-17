"""航班班次意图识别 + 确定性预检索。

问题：是否调用 search_flights 完全由大模型自主决定，模型常“凭自身记忆”直接作答，
凭空编造航班号 / 机型 / 飞行时长（例如给出并不存在的 CA1831、波音777）。

方案：在进入对话图之前，用规则识别「查询两城之间的航班班次」意图，命中则**直接查本地
航班班次库**（tools.flights_tools.search_flights），把真实班次作为上下文注入；模型只负责
把真实数据转述给用户，不再依赖其“自觉”调用工具。

两条防线：
- 命中意图且有班次 → 注入【航班班次检索结果·预取】，指令模型仅据此作答；
- 命中意图但无班次 → 注入【航班班次检索结果·无航班】，指令模型如实告知、禁止编造。

可通过环境变量 FLIGHT_PREFETCH_ENABLED=0 关闭本机制（回退为纯模型自主调用工具）。
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.city_names import CITIES
from tools.flights_tools import search_flights

logger = logging.getLogger(__name__)

# 班次库统一按北京时间存储，字符串可直接比较
_TZ = timezone(timedelta(hours=8))

# 开关：FLIGHT_PREFETCH_ENABLED=0/false/no/off 时关闭预检索
_ENABLED = os.getenv("FLIGHT_PREFETCH_ENABLED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# 预取上下文标记。注意：graph_chat/assistant.py 的后置校验依赖该前缀（见 _FLIGHT_CTX_MARK）。
MARK_MATERIAL = "【航班班次检索结果·预取】"
MARK_NO_MATERIAL = "【航班班次检索结果·无航班】"
MARK_PREFIX = "【航班班次检索"

# 命中这些词才视为“查航班班次”，避免把“北京到上海怎么走 / 高铁”误当成查航班
_FLIGHT_WORDS = ("航班", "班机", "飞机", "机票", "班次", "直飞", "航线", "飞往", "飞到", "飞")

# 「我的航班 / 我的机票」属于个人订单，走 list_my_flights，不做班次预检索
_PERSONAL_WORDS = ("我的", "我订", "我买", "已订", "我已", "自己订")

# 其它交通方式：命中则不做航班预检索
_OTHER_TRANSPORT = ("高铁", "动车", "火车", "自驾", "开车", "大巴", "巴士", "地铁", "轮渡")

# 展示的班次条数上限（按航班号去重后）
_LIMIT = 5
# 去重前的原始取数上限：数据集中同一航班号会按日期重复出现，需要多取再按航班号去重
_FETCH_LIMIT = 60

_TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})")


def is_enabled() -> bool:
    return _ENABLED


def _fmt_time(value: Any) -> str:
    """把 '2026-08-23 18:47:14.634156-04:00' 规整为 '2026-08-23 18:47'。"""
    if not value:
        return "-"
    text = str(value)
    matched = _TIME_RE.match(text)
    return f"{matched.group(1)} {matched.group(2)}" if matched else text


def detect_route_intent(message: str) -> Optional[Tuple[str, str]]:
    """命中「查询 X 到 Y 的航班班次」意图时返回 (出发城市, 到达城市)；否则返回 None。"""
    if not _ENABLED or not message:
        return None
    if any(w in message for w in _PERSONAL_WORDS):
        return None
    if any(w in message for w in _OTHER_TRANSPORT):
        return None
    if not any(w in message for w in _FLIGHT_WORDS):
        return None

    # 按在问句中出现的位置排序，取前两个不同城市作为「出发 → 到达」
    found: List[Tuple[int, str]] = []
    for city in CITIES:
        idx = message.find(city)
        if idx >= 0:
            found.append((idx, city))
    found.sort()

    ordered: List[str] = []
    for _, city in found:
        if city not in ordered:
            ordered.append(city)
    if len(ordered) < 2:
        return None
    return ordered[0], ordered[1]


def _row_summary(index: int, dep: str, arr: str, row: Dict[str, Any]) -> str:
    return (
        f"[{index}] 航班号 {row.get('flight_no') or '-'} | "
        f"{dep}（{row.get('departure_airport') or '-'}）→ "
        f"{arr}（{row.get('arrival_airport') or '-'}） | "
        f"计划起飞 {_fmt_time(row.get('scheduled_departure'))} | "
        f"计划到达 {_fmt_time(row.get('scheduled_arrival'))} | "
        f"状态 {row.get('status') or '-'} | "
        f"机型代码 {row.get('aircraft_code') or '-'}"
    )


def _format_material(dep: str, arr: str, rows: List[Dict[str, Any]]) -> str:
    head = (
        f"{MARK_MATERIAL}\n"
        f"已直接查询本地航班班次库，得到「{dep} → {arr}」共 {len(rows)} 个班次（如下，已按航班号去重）。"
        f"请仅依据以下数据如实转述：航班号、起降机场、计划起降时间、状态一律原样呈现；"
        f"机型只呈现数据库给出的「机型代码」，不要翻译或想象成波音/空客等具体机型名称；"
        f"本数据集不包含票价与飞行时长，禁止编造或推测这些字段，若用户问及请说明暂无该信息；"
        f"日期与时间一律按数据原样呈现，不要自行改写成「今天/明天」等相对说法；"
        f"不要新增、替换、合并或改写任何一条班次。\n"
    )
    return head + "\n".join(
        _row_summary(i, dep, arr, r) for i, r in enumerate(rows, 1)
    )


def _format_no_material(dep: str, arr: str) -> str:
    return (
        f"{MARK_NO_MATERIAL}\n"
        f"已直接查询本地航班班次库，但「{dep} → {arr}」未匹配到任何班次。"
        f"请如实告知用户未查询到该路线的航班；"
        f"严禁凭自身知识编造航班号、起降时刻、机型或票价。"
    )


def _dedupe_nearest(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同一航班号会按日期重复出现：每个航班号只保留「最近的一班」。

    优先取尚未起飞的最近班次；若某航班号只有历史班次，则取其最近的一条。
    结果按起飞时间升序，最多 _LIMIT 个航班号。
    """
    now_str = datetime.now(_TZ).strftime("%Y-%m-%d %H:%M:%S.%f") + "+08:00"
    upcoming: List[Dict[str, Any]] = []
    history: List[Dict[str, Any]] = []
    for row in rows:
        dep = str(row.get("scheduled_departure") or "")
        (upcoming if dep >= now_str else history).append(row)
    upcoming.sort(key=lambda r: str(r.get("scheduled_departure") or ""))
    history.sort(key=lambda r: str(r.get("scheduled_departure") or ""), reverse=True)

    chosen: List[Dict[str, Any]] = []
    seen: set = set()
    for row in upcoming + history:
        flight_no = row.get("flight_no")
        if flight_no in seen:
            continue
        seen.add(flight_no)
        chosen.append(row)
        if len(chosen) >= _LIMIT:
            break
    chosen.sort(key=lambda r: str(r.get("scheduled_departure") or ""))
    return chosen


def build_flight_context(dep: str, arr: str) -> Tuple[str, List[Dict[str, Any]]]:
    """直查本地班次库并返回 (上下文, 结构化班次)。异常或无结果时降级为“无航班”上下文。"""
    try:
        rows = search_flights.invoke(
            {"departure_airport": dep, "arrival_airport": arr, "limit": _FETCH_LIMIT}
        ) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("航班班次预检索失败（%s -> %s）：%s", dep, arr, exc)
        rows = []

    deduped = _dedupe_nearest(rows)
    if deduped:
        return _format_material(dep, arr, deduped), deduped
    return _format_no_material(dep, arr), []


def no_flight_context(dep: str, arr: str) -> str:
    """供超时/异常分支直接构造“无航班”上下文。"""
    return _format_no_material(dep, arr)


def to_card_flights(dep: str, arr: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把真实班次转成前端航班卡片所需的结构（字段名与 Chat.vue 保持一致）。

    除展示字段外，额外带上结构化原始字段（城市名 / 机场代码 / 班次时间），
    供卡片上的「加入我的航班」按钮原样回传后端发起预订，避免从展示文案里反解析。
    """
    cards: List[Dict[str, Any]] = []
    for row in rows:
        cards.append(
            {
                # 展示字段
                "flight_no": row.get("flight_no") or "",
                "status": row.get("status") or "",
                "departure": f"{dep}（{row.get('departure_airport') or '-'}）",
                "arrival": f"{arr}（{row.get('arrival_airport') or '-'}）",
                "dep_time": _fmt_time(row.get("scheduled_departure")),
                "arr_time": _fmt_time(row.get("scheduled_arrival")),
                # 结构化字段（供「加入我的航班」一键预订）
                "departure_city": dep,
                "arrival_city": arr,
                "departure_code": row.get("departure_airport") or "",
                "arrival_code": row.get("arrival_airport") or "",
            }
        )
    return cards
