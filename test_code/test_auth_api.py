import pytest
import asyncio
from httpx import AsyncClient
from main import app


@pytest.fixture
async def test_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_login_success(test_client):
    """성공적인 로그인 테스트"""
    response = await test_client.post(
        "/api/auth/login",
        data={
            "username": "test@example.com",  # 가입된 이메일
            "password": "TestPassword1!"  # 올바른 비밀번호
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert "password_age" in data


@pytest.mark.asyncio
async def test_login_wrong_password(test_client):
    """잘못된 비밀번호로 로그인 테스트"""
    response = await test_client.post(
        "/api/auth/login",
        data={
            "username": "test@example.com",  # 가입된 이메일
            "password": "WrongPassword1!"  # 잘못된 비밀번호
        }
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(test_client):
    """존재하지 않는 사용자로 로그인 테스트"""
    response = await test_client.post(
        "/api/auth/login",
        data={
            "username": "nonexistent@example.com",  # 존재하지 않는 이메일
            "password": "TestPassword1!"
        }
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(test_client):
    """로그아웃 테스트"""
    # 먼저 로그인
    login_response = await test_client.post(
        "/api/auth/login",
        data={
            "username": "test@example.com",
            "password": "TestPassword1!"
        }
    )
    assert login_response.status_code == 200

    # 로그아웃
    response = await test_client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "로그아웃 되었습니다"


# 테스트 실행을 위한 메인 블록
if __name__ == "__main__":
    asyncio.run(pytest.main(["-v", "test_auth_api.py"]))