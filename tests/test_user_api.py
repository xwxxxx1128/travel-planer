import pytest
from fastapi import status


def test_register_user(client):
    """测试用户注册"""
    response = client.post(
        "/api/register/",
        json={
            "username": "testuser",
            "password": "test123",
            "phone": "13800138000",
            "email": "test@example.com",
            "real_name": "测试用户"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data


def test_register_duplicate_user(client):
    """测试重复用户注册"""
    # 第一次注册
    client.post(
        "/api/register/",
        json={
            "username": "duplicate",
            "password": "test123",
            "phone": "13800138001",
            "email": "dup@example.com"
        }
    )
    
    # 第二次注册相同用户名
    response = client.post(
        "/api/register/",
        json={
            "username": "duplicate",
            "password": "test123",
            "phone": "13800138002",
            "email": "dup2@example.com"
        }
    )
    assert response.status_code == status.HTTP_409_CONFLICT


def test_login_success(client):
    """测试成功登录"""
    # 先注册用户
    client.post(
        "/api/register/",
        json={
            "username": "loginuser",
            "password": "login123",
            "phone": "13800138003",
            "email": "login@example.com"
        }
    )
    
    # 登录
    response = client.post(
        "/api/login/",
        json={
            "username": "loginuser",
            "password": "login123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["username"] == "loginuser"


def test_login_wrong_password(client):
    """测试错误密码登录"""
    # 先注册用户
    client.post(
        "/api/register/",
        json={
            "username": "wrongpass",
            "password": "correct123",
            "phone": "13800138004",
            "email": "wrong@example.com"
        }
    )
    
    # 错误密码登录
    response = client.post(
        "/api/login/",
        json={
            "username": "wrongpass",
            "password": "wrong123"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_users_list(client):
    """测试获取用户列表"""
    # 注册多个用户
    for i in range(3):
        client.post(
            "/api/register/",
            json={
                "username": f"user{i}",
                "password": "test123",
                "phone": f"1380013800{i}",
                "email": f"user{i}@example.com"
            }
        )
    
    response = client.get("/api/users/getUsers/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3


def test_get_user_by_id(client):
    """测试根据ID获取用户"""
    # 注册用户
    register_response = client.post(
        "/api/register/",
        json={
            "username": "getbyid",
            "password": "test123",
            "phone": "13800138005",
            "email": "getbyid@example.com"
        }
    )
    user_id = register_response.json()["id"]
    
    # 根据ID获取用户
    response = client.get(f"/api/users/{user_id}/")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "getbyid"
