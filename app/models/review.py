from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Review(Base):
    __tablename__ = 'reviews'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poi_id: Mapped[int | None] = mapped_column(nullable=True)
    poi_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    city: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default='crawler')
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    # ---- 评价缓存扩展：Tavily 联网检索结果的本地缓存 ----
    # 命中后一个月内（REVIEW_CACHE_TTL_DAYS）再问同一地点，优先从本表返回，避免重复调 Tavily。
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    time_range: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    max_results: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
