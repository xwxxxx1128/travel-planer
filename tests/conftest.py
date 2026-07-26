import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from main import Server
from db import DBModelBase


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
