"""旅行清单接口：查看 / 手动添加 / 删除（按当前登录用户隔离）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.schemas.wishlist import WishlistItemCreate, WishlistItemResponse
from app.services import wishlist as wishlist_service

router = APIRouter()


@router.get('', response_model=list[WishlistItemResponse])
def list_wishlist(current: dict = Depends(get_current_user)):
    """返回当前用户的旅行清单。"""
    return wishlist_service.list_items(current["id"])


@router.post('', response_model=WishlistItemResponse)
def add_wishlist(payload: WishlistItemCreate, current: dict = Depends(get_current_user)):
    """向当前用户的旅行清单加入一项。"""
    return wishlist_service.add_item(
        current["id"],
        name=payload.name,
        city=payload.city,
        address=payload.address,
        lng=payload.lng,
        lat=payload.lat,
        note=payload.note,
        source=payload.source or "manual",
    )


@router.delete('/{item_id}')
def delete_wishlist(item_id: int, current: dict = Depends(get_current_user)):
    """删除当前用户清单中的某一项。"""
    ok = wishlist_service.remove_item(current["id"], item_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="清单项不存在或无权操作")
    return {"success": True, "id": item_id}
