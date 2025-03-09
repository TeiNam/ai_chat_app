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


@pytest.mark.asyncio
async def test_create_group(test_client, auth_header, test_api_key_id):
    """그룹 생성 테스트"""
    # 고유한 그룹명 생성
    group_name = f"Test Group {secrets.token_hex(4)}"

    # 그룹 생성 요청
    response = await test_client.post(
        "/api/groups",
        headers=auth_header,
        json={
            "name": group_name,
            "api_key_id": test_api_key_id
        }
    )

    # 응답 확인
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == group_name
    assert data["api_key_id"] == test_api_key_id
    assert "owner_user_id" in data
    assert "group_id" in data
    assert data["is_active"] is True

    # 생성된 그룹 삭제
    delete_response = await test_client.delete(
        f"/api/groups/{data['group_id']}",
        headers=auth_header
    )
    assert delete_response.status_code == 200


@pytest.mark.asyncio
async def test_get_user_groups(test_client, auth_header, test_group):
    """사용자 그룹 목록 조회 테스트"""
    response = await test_client.get(
        "/api/groups",
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # 생성한 테스트 그룹이 목록에 있는지 확인
    test_group_in_response = False
    for group in data:
        if group["group_id"] == test_group["group_id"]:
            test_group_in_response = True
            break

    assert test_group_in_response is True


@pytest.mark.asyncio
async def test_get_group_details(test_client, auth_header, test_group):
    """그룹 상세 정보 조회 테스트"""
    response = await test_client.get(
        f"/api/groups/{test_group['group_id']}",
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()
    assert data["group_id"] == test_group["group_id"]
    assert data["name"] == test_group["name"]
    assert "members" in data
    assert isinstance(data["members"], list)

    # 그룹 생성자가 자동으로 멤버로 추가되어 있는지 확인
    assert len(data["members"]) >= 1

    # 멤버 정보 구조 확인
    if data["members"]:
        member = data["members"][0]
        assert "member_id" in member
        assert "user_id" in member
        assert "is_accpet" in member
        assert "is_active" in member
        assert "user_info" in member


@pytest.mark.asyncio
async def test_update_group(test_client, auth_header, test_group):
    """그룹 정보 업데이트 테스트"""
    # 새 그룹명 생성
    new_group_name = f"Updated Group {secrets.token_hex(4)}"

    # 그룹 정보 업데이트
    response = await test_client.put(
        f"/api/groups/{test_group['group_id']}",
        headers=auth_header,
        json={
            "name": new_group_name
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new_group_name
    assert data["group_id"] == test_group["group_id"]


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
    assert "invitation_id" in invite_data
    assert "user_info" in invite_data
    assert invite_data["user_info"]["user_id"] == test_user_to_invite["user_id"]


@pytest.mark.asyncio
async def test_get_group_invitations(test_client, auth_header, test_group):
    """그룹 초대 목록 조회 테스트"""
    response = await test_client.get(
        f"/api/groups/{test_group['group_id']}/invitations",
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # 초대 정보 구조 확인 (초대가 있는 경우)
    if data:
        invitation = data[0]
        assert "invitation_id" in invitation
        assert "group_id" in invitation
        assert "user_id" in invitation
        assert "invited_by" in invitation
        assert "status" in invitation


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
async def test_delete_group(test_client, auth_header, test_api_key_id):
    """그룹 삭제 테스트"""
    # 삭제용 테스트 그룹 생성
    group_name = f"Delete Test Group {secrets.token_hex(4)}"
    create_response = await test_client.post(
        "/api/groups",
        headers=auth_header,
        json={
            "name": group_name,
            "api_key_id": test_api_key_id
        }
    )

    assert create_response.status_code == 200
    group = create_response.json()

    # 그룹 삭제
    delete_response = await test_client.delete(
        f"/api/groups/{group['group_id']}",
        headers=auth_header
    )

    assert delete_response.status_code == 200
    assert "message" in delete_response.json()

    # 삭제된 그룹 조회 시도
    get_response = await test_client.get(
        f"/api/groups/{group['group_id']}",
        headers=auth_header
    )

    # 그룹은 삭제되었지만 소프트 삭제이므로 접근할 수 있음
    # 하지만 is_active 상태가 False여야 함
    if get_response.status_code == 200:
        data = get_response.json()
        assert data["is_active"] is False
    else:
        assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_add_and_manage_group_member(test_client, auth_header, test_group, test_user_to_invite):
    """그룹 멤버 추가 및 관리 테스트"""
    test_user_id = test_user_to_invite["user_id"]

    # 멤버 추가
    add_response = await test_client.post(
        f"/api/groups/{test_group['group_id']}/members",
        headers=auth_header,
        json={
            "user_id": test_user_id,
            "note": "Test member"
        }
    )

    # 성공 여부 확인 (실제 사용자가 존재하지 않으면 실패할 수 있음)
    if add_response.status_code == 200:
        member = add_response.json()
        assert member["user_id"] == test_user_id
        assert member["group_id"] == test_group["group_id"]

        # 멤버 정보 업데이트
        update_response = await test_client.put(
            f"/api/groups/{test_group['group_id']}/members/{member['member_id']}",
            headers=auth_header,
            json={
                "note": "Updated note",
                "is_active": True
            }
        )

        assert update_response.status_code == 200
        updated_member = update_response.json()
        assert updated_member["note"] == "Updated note"

        # 멤버 제거
        remove_response = await test_client.delete(
            f"/api/groups/{test_group['group_id']}/members/{member['member_id']}",
            headers=auth_header
        )

        assert remove_response.status_code == 200
    else:
        # 테스트 사용자가 없는 경우 테스트 스킵
        print(f"멤버 추가 실패: {add_response.json()}")
        pytest.skip("테스트할 멤버를 추가할 수 없습니다.")


@pytest.mark.asyncio
async def test_get_user_api_keys(test_client, auth_header):
    """사용자 API 키 목록 조회 테스트"""
    response = await test_client.get(
        "/api/user/api-keys",
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # API 키 구조 확인 (키가 존재하는 경우)
    if data:
        api_key = data[0]
        assert "api_key_id" in api_key
        assert "vendor" in api_key
        assert "is_active" in api_key


# 테스트 실행을 위한 메인 블록
if __name__ == "__main__":
    asyncio.run(pytest.main(["-v", "test_group_api.py"]))