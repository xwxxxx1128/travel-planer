"""服务配置接口回归测试：/api/config/runtime 按登录用户独立读写（BYOK）。

验证点：
- 未登录访问 GET/POST 返回 401；
- 任意登录用户均可 GET（200）与 POST（200）自己的配置（不再限定管理员）；
- 配置按 user_id 隔离：用户 A 保存的配置不影响用户 B 读到的默认值。
"""
from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def _register_and_login(client: TestClient, username: str, password: str = "secret123") -> dict:
    resp = client.post("/api/auth/register", json={"username": username, "password": password})
    # pytest 下为共享 in-memory 库，同名用户可能已存在，视为可接受
    assert resp.status_code in (200, 409), resp.text
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_config_requires_login():
    client = _client()
    assert client.get("/api/config/runtime").status_code == 401
    assert client.post("/api/config/runtime", json={}).status_code == 401


def test_logged_in_user_can_read_and_write_own_config():
    client = _client()
    data = _register_and_login(client, "cfg_user_a")
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    # 任意登录用户均可读取自己的配置（返回 .env 兜底后的合并结果）
    resp = client.get("/api/config/runtime", headers=headers)
    assert resp.status_code == 200

    # 保存自己的配置（不再限定管理员）
    resp = client.post(
        "/api/config/runtime",
        json={"openai_model": "my-own-model"},
        headers=headers,
    )
    assert resp.status_code == 200

    # 保存后读回：应包含自己填的模型名（非敏感字段明文返回）
    assert (
        client.get("/api/config/runtime", headers=headers).json()["openai_model"]
        == "my-own-model"
    )


def test_config_is_isolated_per_user():
    client = _client()
    a = _register_and_login(client, "cfg_user_x")
    b = _register_and_login(client, "cfg_user_y")

    headers_a = {"Authorization": f"Bearer {a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {b['access_token']}"}

    # A 保存自己的模型配置
    resp = client.post(
        "/api/config/runtime",
        json={"openai_model": "model-for-a"},
        headers=headers_a,
    )
    assert resp.status_code == 200

    # A 读到自己保存的模型
    assert (
        client.get("/api/config/runtime", headers=headers_a).json()["openai_model"]
        == "model-for-a"
    )
    # B 读到的仍是默认值（不受 A 影响）
    assert (
        client.get("/api/config/runtime", headers=headers_b).json()["openai_model"]
        != "model-for-a"
    )
