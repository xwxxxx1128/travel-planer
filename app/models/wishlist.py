from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WishlistItem(Base):
    """旅行清单条目：用户想去的景点/地点，按用户隔离。

    取代原「游览预订」语义（booked 标记）。数据存于应用自身的库（SQLAlchemy），
    与旅行 demo 库 travel_new.sqlite 解耦，不会被测试期的 update_dates() 重置。
    """

    __tablename__ = 'travel_wishlist'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 来源：manual（手动添加）/ assistant（对话中加入）/ recommend（推荐卡片加入）
    source: Mapped[str] = mapped_column(String(32), default='manual')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
