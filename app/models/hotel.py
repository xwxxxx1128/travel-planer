from sqlalchemy import String, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Hotel(Base):
    __tablename__ = 'hotels'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poi_id: Mapped[int | None] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
