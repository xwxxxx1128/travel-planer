"""鉴权链路单测：受保护接口需令牌、/me 走 Header、refresh 续期、令牌类型校验。

注意：原先用例用 `/api/graph/status` 作为「受保护接口」探针，但该路由已随第二套
规划实现一并移除；现改用同样受 `get_current_user` 保护的 `/api/wishlist` 作为探针。
"""
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
    # 未带令牌访问受保护接口应被拒（401）
    resp = client.get("/api/wishlist")
    assert resp.status_code == 401


def test_invalid_token_rejected():
    client = _client()
    # 伪造令牌应被拒（401）
    resp = client.get("/api/wishlist", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_login_returns_tokens_and_me_reads_header():
    client = _client()
    data = _register_and_login(client, "alice")
    assert data["access_token"] and data["refresh_token"]

    headers = {"Authorization": f"Bearer {data['access_token']}"}
    # 带有效令牌访问受保护接口应成功（200）
    assert client.get("/api/wishlist", headers=headers).status_code == 200

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_refresh_issues_new_access_token():
    client = _client()
    data = _register_and_login(client, "bob")

    r = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 200
    new_access = r.json()["access_token"]

    ok = client.get("/api/wishlist", headers={"Authorization": f"Bearer {new_access}"})
    assert ok.status_code == 200


def test_refresh_rejects_access_token():
    client = _client()
    data = _register_and_login(client, "carol")

    # 用访问令牌去刷新应被拒绝（令牌类型不符）
    r = client.post("/api/auth/refresh", json={"refresh_token": data["access_token"]})
    assert r.status_code == 401
