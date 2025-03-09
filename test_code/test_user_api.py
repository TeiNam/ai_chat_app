import pytest
import asyncio
from httpx import AsyncClient
import secrets
from main import app


@pytest.fixture
async def test_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def auth_header(test_client):
    """인증된 요청을 위한 헤더 제공"""
    response = await test_client.post(
        "/api/auth/login",
        data={
            "username": "test@example.com",
            "password": "TestPassword1!"
        }
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_register_user(test_client):
    """사용자 등록 테스트"""
    # 중복 방지를 위해 랜덤 이메일 사용
    random_suffix = secrets.token_hex(6)
    response = await test_client.post(
        "/api/users",
        json={
            "email": f"test_{random_suffix}@example.com",
            "username": f"test_user_{random_suffix}",
            "password": "TestPassword1!",
            "confirm_password": "TestPassword1!"
        }
    )
    assert response.status_code == 200
    assert "message" in response.json()
    assert "email_status" in response.json()


@pytest.mark.asyncio
async def test_register_duplicate_email(test_client):
    """중복 이메일로 사용자 등록 테스트"""
    # 첫 번째 사용자 등록
    random_suffix = secrets.token_hex(6)
    email = f"test_{random_suffix}@example.com"

    response1 = await test_client.post(
        "/api/users",
        json={
            "email": email,
            "username": f"test_user_{random_suffix}",
            "password": "TestPassword1!",
            "confirm_password": "TestPassword1!"
        }
    )
    assert response1.status_code == 200

    # 동일 이메일로 두 번째 사용자 등록 시도
    response2 = await test_client.post(
        "/api/users",
        json={
            "email": email,
            "username": f"test_user_2_{random_suffix}",
            "password": "TestPassword1!",
            "confirm_password": "TestPassword1!"
        }
    )
    assert response2.status_code == 400
    assert "이미 등록된 이메일" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_password(test_client):
    """잘못된 형식의 비밀번호로 사용자 등록 테스트"""
    random_suffix = secrets.token_hex(6)

    # 특수문자 없음
    response1 = await test_client.post(
        "/api/users",
        json={
            "email": f"test_{random_suffix}@example.com",
            "username": f"test_user_{random_suffix}",
            "password": "TestPassword1",
            "confirm_password": "TestPassword1"
        }
    )
    assert response1.status_code == 422

    # 대문자 없음
    response2 = await test_client.post(
        "/api/users",
        json={
            "email": f"test_{random_suffix}@example.com",
            "username": f"test_user_{random_suffix}",
            "password": "testpassword1!",
            "confirm_password": "testpassword1!"
        }
    )
    assert response2.status_code == 422

    # 숫자 없음
    response3 = await test_client.post(
        "/api/users",
        json={
            "email": f"test_{random_suffix}@example.com",
            "username": f"test_user_{random_suffix}",
            "password": "TestPassword!",
            "confirm_password": "TestPassword!"
        }
    )
    assert response3.status_code == 422


@pytest.mark.asyncio
async def test_get_current_user(test_client, auth_header):
    """현재 로그인한 사용자 정보 조회 테스트"""
    response = await test_client.get(
        "/api/users/me",
        headers=auth_header
    )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "email" in data
    assert "username" in data


@pytest.mark.asyncio
async def test_update_user(test_client, auth_header):
    """사용자 정보 업데이트 테스트"""
    # 새 사용자 이름 생성
    new_username = f"updated_user_{secrets.token_hex(4)}"

    response = await test_client.put(
        "/api/users/me",
        headers=auth_header,
        json={
            "username": new_username,
            "description": "Updated user description"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == new_username
    assert data["description"] == "Updated user description"


@pytest.mark.asyncio
async def test_update_password(test_client, auth_header):
    """비밀번호 변경 테스트"""
    # 현재 비밀번호에서 새 비밀번호로 변경
    response = await test_client.put(
        "/api/users/me/password",
        headers=auth_header,
        json={
            "current_password": "TestPassword1!",
            "new_password": "NewTestPassword2@",
            "confirm_password": "NewTestPassword2@"
        }
    )
    assert response.status_code == 200
    assert "비밀번호가 성공적으로 변경되었습니다" in response.json()["message"]

    # 다시 원래 비밀번호로 변경
    response = await test_client.put(
        "/api/users/me/password",
        headers=auth_header,
        json={
            "current_password": "NewTestPassword2@",
            "new_password": "TestPassword1!",
            "confirm_password": "TestPassword1!"
        }
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_password_status(test_client, auth_header):
    """비밀번호 상태 확인 테스트"""
    response = await test_client.get(
        "/api/users/me/password-status",
        headers=auth_header
    )
    assert response.status_code == 200
    data = response.json()
    assert "days_since_change" in data
    assert "change_required" in data
    assert "last_changed" in data


# 테스트 실행을 위한 메인 블록
if __name__ == "__main__":
    asyncio.run(pytest.main(["-v", "test_user_api.py"]))