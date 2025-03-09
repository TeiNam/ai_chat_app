import pytest
import asyncio
from httpx import AsyncClient
from main import app


@pytest.fixture
async def test_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health_check(test_client):
    """서버 상태 확인 API 테스트"""
    response = await test_client.get("/api/health")

    assert response.status_code == 200
    data = response.json()

    # 기본 구조 확인
    assert "status" in data
    assert "server" in data["status"]
    assert "database" in data["status"]
    assert "email_server" in data["status"]

    # 서버는 항상 실행 중
    assert data["status"]["server"] is True

    # 데이터베이스와 이메일 서버는 설정에 따라 달라질 수 있음
    assert isinstance(data["status"]["database"], bool)
    assert isinstance(data["status"]["email_server"], bool)


# 테스트 실행을 위한 메인 블록
if __name__ == "__main__":
    asyncio.run(pytest.main(["-v", "test_health_api.py"]))