"""鉴权链路单测：受保护接口需令牌、/me 走 Header、refresh 续期、类型校验。"""
from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def _register_and_login(client: TestClient, username: str, password: str = "secret123") -> dict:
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_protected_endpoint_requires_token():
    client = _client()
    resp = client.get("/api/graph/status")
    assert resp.status_code == 401


def test_invalid_token_rejected():
    client = _client()
    resp = client.get("/api/graph/status", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_login_returns_tokens_and_me_reads_header():
    client = _client()
    data = _register_and_login(client, "alice")
    assert data["access_token"] and data["refresh_token"]

    headers = {"Authorization": f"Bearer {data['access_token']}"}
    assert client.get("/api/graph/status", headers=headers).status_code == 200

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_refresh_issues_new_access_token():
    client = _client()
    data = _register_and_login(client, "bob")

    r = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 200
    new_access = r.json()["access_token"]

    ok = client.get("/api/graph/status", headers={"Authorization": f"Bearer {new_access}"})
    assert ok.status_code == 200


def test_refresh_rejects_access_token():
    client = _client()
    data = _register_and_login(client, "carol")

    # 用访问令牌去刷新应被拒绝（令牌类型不符）
    r = client.post("/api/auth/refresh", json={"refresh_token": data["access_token"]})
    assert r.status_code == 401
