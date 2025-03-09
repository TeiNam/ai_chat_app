import pytest
import asyncio
from httpx import AsyncClient
from main import app
import os
import sys

# 애플리케이션 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(scope="session")
def event_loop():
    """테스트에서 사용할 이벤트 루프 생성"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_client():
    """테스트 클라이언트 생성"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="function")
async def registered_user(test_client):
    """테스트용 사용자 등록 및 정보 반환"""
    import secrets

    # 고유한 사용자 생성
    suffix = secrets.token_hex(6)
    email = f"testuser_{suffix}@example.com"
    username = f"testuser_{suffix}"
    password = "TestPassword1!"

    # 사용자 등록
    await test_client.post(
        "/api/users",
        json={
            "email": email,
            "username": username,
            "password": password,
            "confirm_password": password
        }
    )

    # 테스트용 사용자 정보 반환
    return {
        "email": email,
        "username": username,
        "password": password
    }


@pytest.fixture(scope="function")
async def auth_token(test_client, registered_user):
    """테스트 사용자의 인증 토큰 생성 및 반환"""
    # 이메일 인증이 필요한 구현이므로, 실제 테스트에서는 DB에서 직접 is_active를 설정하거나
    # 인증 토큰 검증 로직을 우회하도록 수정해야 함

    # 참고: 실제 테스트에서는 아래 로직이 동작하지 않을 수 있으므로 수정 필요
    response = await test_client.post(
        "/api/auth/login",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"]
        }
    )

    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        # 로그인 실패 시 None 반환 (테스트는 실패할 것임)
        return None


@pytest.fixture(scope="function")
async def auth_header(auth_token):
    """인증 헤더 생성"""
    if auth_token:
        return {"Authorization": f"Bearer {auth_token}"}
    return {}