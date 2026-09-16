"""旅行清单服务：按用户隔离的增 / 删 / 查。

供两处复用：
- REST 接口（app/api/routers/wishlist.py）：可视化模块的增删查；
- 对话工具（tools/wishlist_tools.py）：子助手在对话中加入/移出清单。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.db.session import SessionLocal
from app.models.wishlist import WishlistItem

logger = logging.getLogger(__name__)


def _to_dict(item: WishlistItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "city": item.city,
        "address": item.address,
        "lng": item.lng,
        "lat": item.lat,
        "note": item.note,
        "source": item.source,
        "created_at": item.created_at,
    }


def list_items(user_id: int) -> List[Dict[str, Any]]:
    """返回该用户全部清单项（最新在前）。"""
    session = SessionLocal()
    try:
        rows = (
            session.query(WishlistItem)
            .filter(WishlistItem.user_id == user_id)
            .order_by(WishlistItem.id.desc())
            .all()
        )
        return [_to_dict(r) for r in rows]
    finally:
        session.close()


def add_item(
    user_id: int,
    name: str,
    city: Optional[str] = None,
    address: Optional[str] = None,
    lng: Optional[float] = None,
    lat: Optional[float] = None,
    note: Optional[str] = None,
    source: str = "manual",
) -> Dict[str, Any]:
    """加入清单。同名（同一用户）已存在时不重复添加，返回已存在项。"""
    session = SessionLocal()
    try:
        existing = (
            session.query(WishlistItem)
            .filter(WishlistItem.user_id == user_id, WishlistItem.name == name)
            .first()
        )
        if existing:
            if note and note != existing.note:
                existing.note = note
                session.commit()
                session.refresh(existing)
            return _to_dict(existing)

        item = WishlistItem(
            user_id=user_id,
            name=name,
            city=city,
            address=address,
            lng=lng,
            lat=lat,
            note=note,
            source=source,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return _to_dict(item)
    finally:
        session.close()


def remove_item(user_id: int, item_id: int) -> bool:
    """按 id 删除（校验归属），返回是否删除成功。"""
    session = SessionLocal()
    try:
        row = (
            session.query(WishlistItem)
            .filter(WishlistItem.user_id == user_id, WishlistItem.id == item_id)
            .first()
        )
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
    finally:
        session.close()


def remove_by_name(user_id: int, name: str) -> int:
    """按名称（模糊匹配）删除，返回删除条数。"""
    session = SessionLocal()
    try:
        rows = (
            session.query(WishlistItem)
            .filter(WishlistItem.user_id == user_id, WishlistItem.name.like(f"%{name}%"))
            .all()
        )
        for row in rows:
            session.delete(row)
        session.commit()
        return len(rows)
    finally:
        session.close()
