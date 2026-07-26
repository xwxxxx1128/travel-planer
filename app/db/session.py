import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base

_is_pytest = 'pytest' in os.sys.modules or os.environ.get('PYTEST_CURRENT_TEST') is not None
_db_url = 'sqlite:///:memory:' if _is_pytest else os.environ.get('DATABASE_URL', settings.DATABASE_URL)

_engine_kwargs = {'future': True, 'echo': False}
if _db_url.startswith('sqlite'):
    _engine_kwargs['connect_args'] = {'check_same_thread': False}
if _db_url == 'sqlite:///:memory:':
    _engine_kwargs['poolclass'] = StaticPool

engine = create_engine(_db_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from app.models import user, itinerary, poi, hotel, restaurant, review, flight
    Base.metadata.create_all(bind=engine)
