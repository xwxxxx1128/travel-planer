"""管理员门禁回归测试：服务配置接口 /api/config/runtime 仅管理员可读写。

验证点：
- 未登录访问 GET/POST 返回 401；
- 普通登录用户 GET/POST 返回 403，且登录/me 返回的 is_admin 为 False；
- 管理员（用户名在 ADMIN_USERNAMES 名单内）GET 200、me.is_admin 为 True、POST 200。
"""
from fastapi.testclient import TestClient

from app.core import config as config_module
from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def _register_and_login(client: TestClient, username: str, password: str = "secret123") -> dict:
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_config_requires_login():
    client = _client()
    assert client.get("/api/config/runtime").status_code == 401
    assert client.post("/api/config/runtime", json={}).status_code == 401


def test_non_admin_cannot_access_config(monkeypatch):
    # 固定为空名单，避免受开发者本机 .env 中 ADMIN_USERNAMES 影响
    monkeypatch.setattr(config_module.settings, "ADMIN_USERNAMES", "")

    client = _client()
    data = _register_and_login(client, "normal_user")
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    assert data["user"]["is_admin"] is False
    assert client.get("/api/config/runtime", headers=headers).status_code == 403
    assert client.post("/api/config/runtime", json={}, headers=headers).status_code == 403


def test_admin_can_access_config(monkeypatch):
    # 仅本用例内把 adminuser 设为管理员；测试结束自动还原
    monkeypatch.setattr(config_module.settings, "ADMIN_USERNAMES", "adminuser,root")

    client = _client()
    data = _register_and_login(client, "adminuser")
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    # is_admin 随登录/me 透出
    assert data["user"]["is_admin"] is True
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["is_admin"] is True

    # 管理员可读
    assert client.get("/api/config/runtime", headers=headers).status_code == 200

    # 管理员可写：替换 save_runtime_config，避免测试真的回写宿主机 .env
    from app.api.routers import config as config_router_module
    from app.core.runtime_config import RuntimeConfig

    monkeypatch.setattr(config_router_module, "save_runtime_config", lambda updates: RuntimeConfig())
    resp = client.post("/api/config/runtime", json={"openai_model": "gpt-4o-mini"}, headers=headers)
    assert resp.status_code == 200
