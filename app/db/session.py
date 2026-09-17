import logging
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base

logger = logging.getLogger(__name__)

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


def _safe_db_url() -> str:
    """隐藏密码后的数据库地址，便于日志展示。"""
    url = str(engine.url)
    if "@" in url and "//" in url:
        head, tail = url.split("//", 1)
        if "@" in tail:
            cred, host = tail.split("@", 1)
            user = cred.split(":", 1)[0]
            return f"{head}//{user}:***@{host}"
    return url


# create_all 只会新建“不存在”的表，不会给已存在的表补列。这里做一次轻量迁移，
# 确保历史库也能补上评价缓存新增列（尤其是 poi_key），避免旧库缺列导致评价缓存
# 静默失效（读取抛异常 → 每次都重复调用 Tavily）。
_REVIEW_COLUMNS: dict = {
    "poi_key": "VARCHAR(256)",
    "title": "VARCHAR(256)",
    "url": "VARCHAR(512)",
    "time_range": "VARCHAR(32)",
    "max_results": "INTEGER",
    "fetched_at": "DATETIME",
    "expires_at": "DATETIME",
}


def _ensure_columns() -> None:
    """为已存在的 reviews 表补齐缺失列（轻量迁移，SQLite/PostgreSQL 兼容）。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "reviews" not in set(inspector.get_table_names()):
        return
    existing = {col["name"] for col in inspector.get_columns("reviews")}
    missing = {name: ddl for name, ddl in _REVIEW_COLUMNS.items() if name not in existing}
    if not missing:
        return
    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE reviews ADD COLUMN {name} {ddl}"))
            logger.info("评价表补齐缺失列：reviews.%s", name)
        # poi_key 需要索引以支撑“按归一化 key 命中缓存”的查询
        try:
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_reviews_poi_key ON reviews (poi_key)")
            )
        except Exception:  # 个别方言不支持 IF NOT EXISTS 时忽略索引创建
            logger.warning("创建 reviews.poi_key 索引失败（可忽略）")


def _migrate_flight_bookings() -> None:
    """个人航班表迁移（轻量迁移）。

    历史库中该表名为 flights（与 demo 班次库同名、易混淆），现统一为 flight_bookings，
    并补齐 status / booking_no 列。必须在 create_all 之前执行，以便保留已有数据。
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "flight_bookings" not in tables and "flights" in tables:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE flights RENAME TO flight_bookings"))
        logger.info("个人航班表迁移：flights -> flight_bookings")
        tables.discard("flights")
        tables.add("flight_bookings")

    if "flight_bookings" not in tables:
        return

    existing = {col["name"] for col in inspect(engine).get_columns("flight_bookings")}
    with engine.begin() as conn:
        if "status" not in existing:
            conn.execute(
                text("ALTER TABLE flight_bookings ADD COLUMN status VARCHAR(16) DEFAULT 'booked'")
            )
            logger.info("个人航班表补齐缺失列：flight_bookings.status")
        if "booking_no" not in existing:
            conn.execute(
                text("ALTER TABLE flight_bookings ADD COLUMN booking_no VARCHAR(32)")
            )
            logger.info("个人航班表补齐缺失列：flight_bookings.booking_no")


def _drop_legacy_user_columns() -> None:
    """清理历史遗留列。

    passenger_id 已废弃（个人航班订单改为按 user_id 隔离，见 app/models/flight.py）。
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "users" not in set(inspector.get_table_names()):
        return
    existing = {col["name"] for col in inspector.get_columns("users")}
    if "passenger_id" not in existing:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users DROP COLUMN passenger_id"))
        logger.info("用户表清理遗留列：users.passenger_id")
    except Exception:  # 个别 sqlite 版本不支持 DROP COLUMN，忽略即可（该列已不再被使用）
        logger.warning("清理 users.passenger_id 失败（可忽略）")


def init_db() -> None:
    """建表 + 轻量迁移（强化库表建立环节）。

    强化点：
    - 输出明确的初始化日志（含数据库地址），便于排查“评价缓存未生效”类问题；
    - 通过 _ensure_columns 为历史库补齐评价缓存新增列（poi_key 等），
      避免 create_all 不补列导致旧库缺列、缓存静默降级为每次现调 Tavily；
    - 通过 _migrate_flight_bookings 把历史 flights 表迁移为 flight_bookings 并补列；
    - 通过 _drop_legacy_user_columns 清理 users.passenger_id 等遗留列；
    - 初始化失败时记录完整堆栈并抛出，不再静默吞掉。
    """
    try:
        from app.models import (  # noqa: F401
            user,
            itinerary,
            poi,
            hotel,
            restaurant,
            review,
            flight,
        )

        # 需在 create_all 之前执行：把历史 flights 改名为 flight_bookings 以保留数据
        _migrate_flight_bookings()
        Base.metadata.create_all(bind=engine)
        _ensure_columns()
        _drop_legacy_user_columns()
        logger.info("数据库初始化完成：%s", _safe_db_url())
    except Exception:
        logger.exception("数据库初始化失败：%s", _safe_db_url())
        raise
