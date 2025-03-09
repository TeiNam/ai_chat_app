import logging
from typing import Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query

from api.deps.auth import get_current_user
from api.schemas.group import (
    GroupCreate, GroupUpdate, GroupResponse, GroupDetailResponse,
    GroupMemberCreate, GroupMemberUpdate, GroupMemberResponse
)
from core.database import get_db
from repository.group_repository import GroupRepository
from repository.user_repository import UserRepository

router = APIRouter(tags=["groups"])
logger = logging.getLogger(__name__)


@router.post("/groups", response_model=GroupResponse)
async def create_group(
        group_data: GroupCreate,
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """새 그룹을 생성합니다."""
    group_repo = GroupRepository(db)

    # API 키가 사용자의 것인지 확인 (추가 검증 필요)
    # TODO: API 키 소유권 검증 로직 추가

    # 그룹 생성
    group_id, error = await group_repo.create_group(
        owner_user_id=current_user["user_id"],
        api_key_id=group_data.api_key_id,
        name=group_data.name
    )

    if not group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "그룹 생성에 실패했습니다."
        )

    # 생성된 그룹 정보 조회
    group = await group_repo.get_group_with_api_key_info(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="그룹이 생성되었지만 정보를 불러올 수 없습니다."
        )

    return group


@router.get("/groups", response_model=List[GroupResponse])
async def get_user_groups(
        include_pending: bool = Query(False, description="대기 중인 초대도 포함할지 여부"),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """사용자가 속한 그룹 목록을 조회합니다."""
    group_repo = GroupRepository(db)

    logger.info(f"사용자 그룹 조회: user_id={current_user['user_id']}, include_pending={include_pending}")

    # 사용자의 그룹 목록 조회
    groups = await group_repo.get_user_groups(
        user_id=current_user["user_id"],
        include_pending=include_pending
    )

    logger.info(f"조회된 그룹 수: {len(groups)}")

    return groups


@router.get("/groups/{group_id}", response_model=GroupDetailResponse)
async def get_group_details(
        group_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹 상세 정보와 멤버 목록을 조회합니다."""
    group_repo = GroupRepository(db)

    # 그룹 정보 조회
    group = await group_repo.get_group_with_api_key_info(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다."
        )

    # 사용자가 그룹 멤버인지 확인
    member = await group_repo.get_member_by_user_and_group(
        user_id=current_user["user_id"],
        group_id=group_id
    )

    if not member or not member["is_accpet"] or not member["is_active"]:
        # 그룹 소유자인지 확인
        if group["owner_user_id"] != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 그룹에 접근할 권한이 없습니다."
            )

    # 그룹 멤버 목록 조회
    members = await group_repo.get_group_members(group_id)

    # 응답 구성
    result = dict(group)
    result["members"] = members

    return result


@router.put("/groups/{group_id}", response_model=GroupResponse)
async def update_group(
        group_data: GroupUpdate,
        group_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹 정보를 업데이트합니다."""
    group_repo = GroupRepository(db)

    # 그룹 정보 조회
    group = await group_repo.get_group_by_id(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다."
        )

    # 그룹 소유자인지 확인
    if group["owner_user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 정보를 수정할 권한이 없습니다."
        )

    # API 키 변경 시 소유권 확인 (필요하면 추가)

    # 그룹 정보 업데이트
    success, error = await group_repo.update_group(
        group_id=group_id,
        name=group_data.name,
        is_active=group_data.is_active,
        api_key_id=group_data.api_key_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "그룹 정보 업데이트에 실패했습니다."
        )

    # 업데이트된 그룹 정보 조회
    updated_group = await group_repo.get_group_with_api_key_info(group_id)

    return updated_group


@router.delete("/groups/{group_id}", response_model=Dict[str, str])
async def delete_group(
        group_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹을 삭제합니다 (비활성화)."""
    group_repo = GroupRepository(db)

    # 그룹 정보 조회
    group = await group_repo.get_group_by_id(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다."
        )

    # 그룹 소유자인지 확인
    if group["owner_user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹을 삭제할 권한이 없습니다."
        )

    # 그룹 삭제
    success, error = await group_repo.delete_group(group_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "그룹 삭제에 실패했습니다."
        )

    return {"message": "그룹이 성공적으로 삭제되었습니다."}


@router.post("/groups/{group_id}/members", response_model=GroupMemberResponse)
async def add_group_member(
        member_data: GroupMemberCreate,
        group_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹에 멤버를 직접 추가합니다 (관리자/소유자 기능)."""
    group_repo = GroupRepository(db)
    user_repo = UserRepository(db)

    # 그룹 정보 조회
    group = await group_repo.get_group_by_id(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다."
        )

    # 그룹 소유자인지 확인
    if group["owner_user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹에 멤버를 추가할 권한이 없습니다."
        )

    # 추가할 사용자가 존재하는지 확인
    user = await user_repo.get_user_by_id(member_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="추가할 사용자를 찾을 수 없습니다."
        )

    # 멤버 추가
    member_id, error = await group_repo.add_group_member(
        group_id=group_id,
        user_id=member_data.user_id,
        is_accpet=True,  # 소유자가 직접 추가하는 경우 자동 승인
        note=member_data.note
    )

    if not member_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "멤버 추가에 실패했습니다."
        )

    # 추가된 멤버 정보 조회
    member = await group_repo.get_member_info(member_id)

    if not member:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="멤버가 추가되었지만 정보를 불러올 수 없습니다."
        )

    return member


@router.put("/groups/{group_id}/members/{member_id}", response_model=GroupMemberResponse)
async def update_group_member(
        member_data: GroupMemberUpdate,
        group_id: int = Path(..., gt=0),
        member_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹 멤버 정보를 업데이트합니다."""
    group_repo = GroupRepository(db)

    # 그룹 정보 조회
    group = await group_repo.get_group_by_id(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다."
        )

    # 그룹 소유자인지 확인
    if group["owner_user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 멤버 정보를 수정할 권한이 없습니다."
        )

    # 멤버 정보 조회 및 그룹 확인
    member = await group_repo.get_member_info(member_id)

    if not member or member["group_id"] != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 그룹에서 멤버를 찾을 수 없습니다."
        )

    # 멤버 정보 업데이트
    success, error = await group_repo.update_group_member(
        member_id=member_id,
        is_accpet=member_data.is_accpet,
        is_active=member_data.is_active,
        note=member_data.note
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "멤버 정보 업데이트에 실패했습니다."
        )

    # 업데이트된 멤버 정보 조회
    updated_member = await group_repo.get_member_info(member_id)

    return updated_member


@router.delete("/groups/{group_id}/members/{member_id}", response_model=Dict[str, str])
async def remove_group_member(
        group_id: int = Path(..., gt=0),
        member_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹에서 멤버를 제거합니다."""
    group_repo = GroupRepository(db)

    # 그룹 정보 조회
    group = await group_repo.get_group_by_id(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다."
        )

    # 멤버 정보 조회 및 그룹 확인
    member = await group_repo.get_member_info(member_id)

    if not member or member["group_id"] != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 그룹에서 멤버를 찾을 수 없습니다."
        )

    # 권한 확인 (그룹 소유자 또는 본인만 제거 가능)
    if (
            group["owner_user_id"] != current_user["user_id"] and
            member["user_id"] != current_user["user_id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 멤버를 제거할 권한이 없습니다."
        )

    # 그룹 소유자는 제거할 수 없음
    if member["user_id"] == group["owner_user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="그룹 소유자는 멤버에서 제거할 수 없습니다."
        )

    # 멤버 제거
    success, error = await group_repo.remove_group_member(member_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "멤버 제거에 실패했습니다."
        )

    return {"message": "멤버가 성공적으로 제거되었습니다."}


@router.get("/groups/{group_id}/pending-members", response_model=List[GroupMemberResponse])
async def get_pending_members(
        group_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹의 대기 중인(승인 대기) 멤버 목록을 조회합니다."""
    group_repo = GroupRepository(db)

    # 그룹 정보 조회
    group = await group_repo.get_group_by_id(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다."
        )

    # 그룹 소유자인지 확인
    if group["owner_user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="대기 중인 멤버 목록을 조회할 권한이 없습니다."
        )

    # 대기 중인 멤버 목록 조회 (is_accpet=0인 멤버)
    pending_members = await group_repo.get_pending_members(group_id)

    return pending_members


@router.post("/groups/{group_id}/members/{member_id}/approve", response_model=GroupMemberResponse)
async def approve_group_member(
        group_id: int = Path(..., gt=0),
        member_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹 관리자가 대기 중인 멤버를 승인합니다."""
    group_repo = GroupRepository(db)

    # 그룹 정보 조회
    group = await group_repo.get_group_by_id(group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다."
        )

    # 그룹 소유자인지 확인
    if group["owner_user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="멤버를 승인할 권한이 없습니다."
        )

    # 멤버 정보 조회 및 그룹 확인
    member = await group_repo.get_member_info(member_id)

    if not member or member["group_id"] != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 그룹에서 멤버를 찾을 수 없습니다."
        )

    # 이미 승인된 멤버인지 확인
    if member["is_accpet"]:
        return member

    # 멤버 승인 (is_accpet=1로 설정)
    success, error = await group_repo.update_group_member(
        member_id=member_id,
        is_accpet=True,
        is_active=True
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error or "멤버 승인 중 오류가 발생했습니다."
        )

    # 업데이트된 멤버 정보 조회
    updated_member = await group_repo.get_member_info(member_id)

    return updated_member


@router.get("/user/api-keys", response_model=List[Dict[str, Any]])
async def get_user_api_keys(
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """사용자가 소유한 API 키 목록을 조회합니다."""
    group_repo = GroupRepository(db)

    # API 키 목록 조회
    api_keys = await group_repo.get_user_owned_api_keys(current_user["user_id"])

    return api_keys