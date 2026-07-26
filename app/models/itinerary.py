from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, Integer, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Itinerary(Base):
    __tablename__ = 'itineraries'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    trip_name: Mapped[str] = mapped_column(String(128), nullable=False)
    travel_days: Mapped[int] = mapped_column(Integer, default=1)
    preference: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class ItineraryDay(Base):
    __tablename__ = 'itinerary_days'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    itinerary_id: Mapped[int] = mapped_column(ForeignKey('itineraries.id'), index=True)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    meals: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ItineraryItem(Base):
    __tablename__ = 'itinerary_items'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    day_id: Mapped[int] = mapped_column(ForeignKey('itinerary_days.id'), index=True)
    poi_id: Mapped[int | None] = mapped_column(ForeignKey('pois.id'), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default='scenic')
    arrival_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    departure_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    transport_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
