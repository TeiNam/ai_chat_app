import pytest
import asyncio
import secrets
from httpx import AsyncClient
from fastapi import status

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
            "username": "test@example.com",  # 테스트 사용자 이메일
            "password": "TestPassword1!"  # 테스트 사용자 비밀번호
        }
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_api_key_id(test_client, auth_header):
    """테스트용 API 키 ID 조회"""
    response = await test_client.get(
        "/api/user/api-keys",
        headers=auth_header
    )
    api_keys = response.json()

    # API 키가 존재하는지 확인
    if not api_keys:
        pytest.skip("테스트 사용자의 API 키가 없습니다.")

    return api_keys[0]["api_key_id"]


@pytest.fixture
async def test_group(test_client, auth_header, test_api_key_id):
    """테스트용 그룹 생성"""
    # 고유한 그룹명 생성
    group_name = f"Test Group {secrets.token_hex(4)}"

    # 그룹 생성
    response = await test_client.post(
        "/api/groups",
        headers=auth_header,
        json={
            "name": group_name,
            "api_key_id": test_api_key_id
        }
    )

    assert response.status_code == 200
    group = response.json()

    yield group

    # 테스트 후 그룹 삭제
    try:
        await test_client.delete(
            f"/api/groups/{group['group_id']}",
            headers=auth_header
        )
    except Exception:
        pass


@pytest.fixture
async def test_user_to_invite(test_client, auth_header):
    """초대할 테스트 사용자 검색"""
    # 참고: 이 테스트는 실제로 다른 사용자가 시스템에 등록되어 있어야 함
    search_response = await test_client.get(
        "/api/users/search?query=test",
        headers=auth_header
    )

    if search_response.status_code != 200 or not search_response.json():
        pytest.skip("초대할 테스트 사용자를 찾을 수 없습니다.")

    return search_response.json()[0]  # 첫 번째 검색 결과 사용자 반환


@pytest.fixture
async def test_invitation(test_client, auth_header, test_group, test_user_to_invite):
    """테스트용 초대 생성"""
    invite_response = await test_client.post(
        f"/api/groups/{test_group['group_id']}/invite-user",
        headers=auth_header,
        json={
            "user_id": test_user_to_invite["user_id"],
            "note": "Test invitation"
        }
    )

    assert invite_response.status_code == 200
    invitation_data = invite_response.json()

    # 생성된 초대 ID 조회
    invitations_response = await test_client.get(
        f"/api/groups/{test_group['group_id']}/invitations",
        headers=auth_header
    )

    assert invitations_response.status_code == 200
    invitations = invitations_response.json()

    if not invitations:
        pytest.skip("테스트 초대를 찾을 수 없습니다.")

    # 방금 생성한 초대 찾기
    invitation = next(
        (inv for inv in invitations if inv["user_id"] == test_user_to_invite["user_id"]),
        invitations[0]  # 찾지 못하면 첫 번째 초대 사용
    )

    return {
        "invitation_id": invitation["invitation_id"],
        "group_id": test_group["group_id"],
        "user_id": test_user_to_invite["user_id"]
    }


@pytest.mark.asyncio
async def test_search_users(test_client, auth_header):
    """사용자 검색 테스트"""
    response = await test_client.get(
        "/api/users/search?query=test",
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # 검색 결과 구조 확인 (결과가 있는 경우)
    if data:
        user = data[0]
        assert "user_id" in user
        assert "email" in user
        assert "username" in user


@pytest.mark.asyncio
async def test_invite_user_to_group(test_client, auth_header, test_group, test_user_to_invite):
    """내부 사용자 초대 테스트"""
    invite_response = await test_client.post(
        f"/api/groups/{test_group['group_id']}/invite-user",
        headers=auth_header,
        json={
            "user_id": test_user_to_invite["user_id"],
            "note": "Testing user invitation"
        }
    )

    assert invite_response.status_code == 200
    invite_data = invite_response.json()
    assert invite_data["success"] is True
    assert "user_info" in invite_data
    assert invite_data["user_info"]["user_id"] == test_user_to_invite["user_id"]


@pytest.mark.asyncio
async def test_get_group_invitations(test_client, auth_header, test_group, test_invitation):
    """그룹 초대 목록 조회 테스트"""
    response = await test_client.get(
        f"/api/groups/{test_group['group_id']}/invitations",
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # 생성한 초대가 목록에 있는지 확인
    invitation_in_response = False
    for invitation in data:
        if invitation["invitation_id"] == test_invitation["invitation_id"]:
            invitation_in_response = True
            assert invitation["group_id"] == test_group["group_id"]
            assert invitation["user_id"] == test_invitation["user_id"]
            assert "status" in invitation
            break

    assert invitation_in_response is True


@pytest.mark.asyncio
async def test_get_user_invitations(test_client, auth_header):
    """사용자의 초대 목록 조회 테스트"""
    response = await test_client.get(
        "/api/invitations",
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_cancel_invitation(test_client, auth_header, test_invitation):
    """초대 취소 테스트"""
    cancel_response = await test_client.post(
        f"/api/invitations/{test_invitation['invitation_id']}/cancel",
        headers=auth_header
    )

    assert cancel_response.status_code == 200
    data = cancel_response.json()
    assert "message" in data


# 두 번째 사용자 로그인이 필요한 복잡한 테스트는 실제 환경에서만 가능
"""
@pytest.mark.asyncio
async def test_accept_invitation(test_client, invited_user_auth_header, test_invitation):
    이 테스트는 초대된 사용자의 인증 정보가 필요하므로 실제 환경에서만 가능

    accept_response = await test_client.post(
        f"/api/invitations/{test_invitation['invitation_id']}/accept",
        headers=invited_user_auth_header
    )

    assert accept_response.status_code == 200
    data = accept_response.json()
    assert "message" in data
    assert "group_id" in data
    assert "group_name" in data
"""

# 테스트 실행을 위한 메인 블록
if __name__ == "__main__":
    asyncio.run(pytest.main(["-v", "test_invitation_api.py"]))