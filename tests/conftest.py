import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from main import Server
from db import DBModelBase


@pytest.fixture(autouse=True)
def _reset_review_cache():
    """每个用例前清空评价缓存表：pytest 下 sqlite 为共享 in-memory，避免缓存跨用例串数据。"""
    from app.db.session import SessionLocal, init_db
    from app.models.review import Review

    init_db()
    with SessionLocal() as session:
        session.query(Review).delete()
        session.commit()
    yield


@pytest.fixture
def test_db():
    """创建测试数据库"""
    engine = create_engine("sqlite:///:memory:")
    DBModelBase.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(test_db):
    """创建测试客户端"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    from api.system_mgt import user_views
    from utils.dependencies import get_db
    user_views.get_db = override_get_db
    
    app = Server().app
    yield TestClient(app)
