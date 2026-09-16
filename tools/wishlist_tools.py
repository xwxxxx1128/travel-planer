"""旅行清单对话工具（加入 / 移出 / 查看）。

这些工具在 LangGraph 图内被「旅行清单子助手」调用。因清单按用户隔离，工具需要
知道「当前是哪个用户」：用户身份通过图运行配置 config.configurable.user_id 注入
（见 app/services/langgraph_chat.py 的 _make_config），LangChain 会把 RunnableConfig
自动注入到带该注解的参数，不进入工具参数 schema。
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.services import wishlist as wishlist_service

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
def add_to_wishlist(
    name: str,
    city: str = "",
    address: str = "",
    note: str = "",
    config: RunnableConfig = None,
) -> str:
    """把景点/地点加入当前用户的「旅行清单」。name 为名称；city/address/note 可选。"""
    user_id = _user_id_from_config(config)
    if not user_id:
        return "无法识别当前用户，请先登录后再加入旅行清单。"
    item = wishlist_service.add_item(
        user_id,
        name=name,
        city=city or None,
        address=address or None,
        note=note or None,
        source="assistant",
    )
    return f"已将「{item['name']}」加入旅行清单。"


@tool
def remove_from_wishlist(name_or_id: str, config: RunnableConfig = None) -> str:
    """从当前用户的「旅行清单」移出某项。name_or_id 可传清单项名称或数字 id。"""
    user_id = _user_id_from_config(config)
    if not user_id:
        return "无法识别当前用户，请先登录后再操作旅行清单。"

    text = (name_or_id or "").strip()
    if not text:
        return "请提供要移出的清单项名称或 id。"

    if text.isdigit():
        ok = wishlist_service.remove_item(user_id, int(text))
        return f"已从旅行清单移出 id={text} 的项目。" if ok else f"旅行清单中没有 id={text} 的项目。"

    count = wishlist_service.remove_by_name(user_id, text)
    if count:
        return f"已从旅行清单移出 {count} 个与「{text}」匹配的项目。"
    return f"旅行清单中没有找到「{text}」。"


@tool(description="查看当前用户的旅行清单全部内容。")
def list_wishlist(config: RunnableConfig = None) -> str:
    """返回当前用户旅行清单的条目列表。"""
    user_id = _user_id_from_config(config)
    if not user_id:
        return "无法识别当前用户，请先登录后再查看旅行清单。"

    items = wishlist_service.list_items(user_id)
    if not items:
        return "当前旅行清单还是空的，可以让我先推荐几个景点。"

    lines = [
        f"- {it['name']}（{it.get('city') or '未知城市'}）"
        + (f"，备注：{it['note']}" if it.get("note") else "")
        for it in items
    ]
    return "当前旅行清单共 %d 项：\n%s" % (len(items), "\n".join(lines))
