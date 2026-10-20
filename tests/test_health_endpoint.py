"""健康检查接口单测：GET /health 应返回 200 且 status=ok。"""
from fastapi.testclient import TestClient

from app.main import create_app


def test_health():
    client = TestClient(create_app())
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
