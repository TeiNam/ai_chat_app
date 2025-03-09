# api/router/invitation_router.py
import logging
from typing import Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query

from api.deps.auth import get_current_user
from api.schemas.group import (
    GroupUserInviteRequest, GroupUserInviteResponse
)
from core.database import get_db
from repository.group_repository import GroupRepository
from repository.invitation_repository import InvitationRepository
from repository.user_repository import UserRepository

router = APIRouter(tags=["invitations"])
logger = logging.getLogger(__name__)


@router.post("/groups/{group_id}/invite-user", response_model=GroupUserInviteResponse)
async def invite_user_to_group(
        invite_data: GroupUserInviteRequest,
        group_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """내부 사용자를 그룹에 초대합니다."""
    group_repo = GroupRepository(db)
    user_repo = UserRepository(db)
    invitation_repo = InvitationRepository(db)

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
            detail="그룹에 초대할 권한이 없습니다."
        )

    # 초대할 사용자 정보 확인
    user = await user_repo.get_user_by_id(invite_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="초대할 사용자를 찾을 수 없습니다."
        )

    # 자기 자신은 초대할 수 없음
    if user["user_id"] == current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자기 자신은 초대할 수 없습니다."
        )

    # 이미 그룹 멤버인지 확인
    existing_member = await group_repo.get_member_by_user_and_group(
        user_id=user["user_id"],
        group_id=group_id
    )

    if existing_member and existing_member["is_accpet"] and existing_member["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해당 사용자는 이미 그룹의 활성 멤버입니다."
        )

    # 초대 생성
    invitation_id, error = await invitation_repo.create_invitation(
        group_id=group_id,
        user_id=user["user_id"],
        invited_by=current_user["user_id"],
        note=invite_data.note
    )

    if not invitation_id:
        if "이미 초대된 사용자입니다" in error:
            # 이미 초대된 경우는 성공으로 처리
            return {
                "success": True,
                "message": error,
                "invitation_id": None,
                "user_info": {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "email": user["email"]
                }
            }

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "초대 생성에 실패했습니다."
        )

    return {
        "success": True,
        "message": f"{user['username']} 사용자를 그룹에 초대했습니다.",
        "invitation_id": invitation_id,
        "user_info": {
            "user_id": user["user_id"],
            "username": user["username"],
            "email": user["email"]
        }
    }


@router.get("/invitations", response_model=List[Dict[str, Any]])
async def get_user_invitations(
        status: str = Query(None, description="초대 상태(pending, accepted, declined, canceled)"),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """현재 사용자의 그룹 초대 목록을 조회합니다."""
    invitation_repo = InvitationRepository(db)

    invitations = await invitation_repo.get_user_invitations(
        user_id=current_user["user_id"],
        status=status
    )

    return invitations


@router.get("/groups/{group_id}/invitations", response_model=List[Dict[str, Any]])
async def get_group_invitations(
        group_id: int = Path(..., gt=0),
        status: str = Query(None, description="초대 상태(pending, accepted, declined, canceled)"),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹의 초대 목록을 조회합니다."""
    group_repo = GroupRepository(db)
    invitation_repo = InvitationRepository(db)

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
            detail="그룹 초대 목록을 조회할 권한이 없습니다."
        )

    invitations = await invitation_repo.get_group_invitations(
        group_id=group_id,
        status=status
    )

    return invitations


@router.post("/invitations/{invitation_id}/accept", response_model=Dict[str, Any])
async def accept_invitation(
        invitation_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹 초대를 수락합니다."""
    invitation_repo = InvitationRepository(db)
    group_repo = GroupRepository(db)

    # 초대 정보 조회
    invitation = await invitation_repo.get_invitation_by_id(invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="초대를 찾을 수 없습니다."
        )

    # 초대 대상자가 맞는지 확인
    if invitation["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 초대를 수락할 권한이 없습니다."
        )

    # 초대 상태 확인
    if invitation["status"] != "pending":
        if invitation["status"] == "accepted":
            return {"message": "이미 수락한 초대입니다."}

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"이 초대는 현재 {invitation['status']} 상태여서 수락할 수 없습니다."
        )

    # 트랜잭션 시작 (여러 작업을 함께 수행)
    try:
        # 초대 상태 업데이트
        success, error = await invitation_repo.update_invitation_status(
            invitation_id=invitation_id,
            status="accepted"
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error or "초대 상태 업데이트에 실패했습니다."
            )

        # 그룹 멤버로 추가
        member_id, error = await group_repo.add_group_member(
            group_id=invitation["group_id"],
            user_id=current_user["user_id"],
            is_accpet=True
        )

        if not member_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error or "그룹 멤버 추가에 실패했습니다."
            )

        return {
            "message": f"{invitation['group_name']} 그룹 초대를 수락했습니다.",
            "group_id": invitation["group_id"],
            "group_name": invitation["group_name"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"초대 수락 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="초대 수락 중 오류가 발생했습니다."
        )


@router.post("/invitations/{invitation_id}/decline", response_model=Dict[str, str])
async def decline_invitation(
        invitation_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹 초대를 거절합니다."""
    invitation_repo = InvitationRepository(db)

    # 초대 정보 조회
    invitation = await invitation_repo.get_invitation_by_id(invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="초대를 찾을 수 없습니다."
        )

    # 초대 대상자가 맞는지 확인
    if invitation["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 초대를 거절할 권한이 없습니다."
        )

    # 초대 상태 확인
    if invitation["status"] != "pending":
        if invitation["status"] == "declined":
            return {"message": "이미 거절한 초대입니다."}

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"이 초대는 현재 {invitation['status']} 상태여서 거절할 수 없습니다."
        )

    # 초대 상태 업데이트
    success, error = await invitation_repo.update_invitation_status(
        invitation_id=invitation_id,
        status="declined"
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error or "초대 상태 업데이트에 실패했습니다."
        )

    return {"message": f"{invitation['group_name']} 그룹 초대를 거절했습니다."}


@router.post("/invitations/{invitation_id}/cancel", response_model=Dict[str, str])
async def cancel_invitation(
        invitation_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """그룹 초대를 취소합니다 (그룹 소유자만 가능)."""
    invitation_repo = InvitationRepository(db)

    # 초대 정보 조회
    invitation = await invitation_repo.get_invitation_by_id(invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="초대를 찾을 수 없습니다."
        )

    # 그룹 소유자인지 확인
    if invitation["invited_by"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 초대를 취소할 권한이 없습니다."
        )

    # 초대 상태 확인
    if invitation["status"] != "pending":
        if invitation["status"] == "canceled":
            return {"message": "이미 취소된 초대입니다."}

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"이 초대는 현재 {invitation['status']} 상태여서 취소할 수 없습니다."
        )

    # 초대 상태 업데이트
    success, error = await invitation_repo.update_invitation_status(
        invitation_id=invitation_id,
        status="canceled"
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error or "초대 상태 업데이트에 실패했습니다."
        )

    return {"message": f"{invitation['username']} 사용자에 대한 초대를 취소했습니다."}


@router.get("/users/search", response_model=List[Dict[str, Any]])
async def search_users(
        query: str = Query(..., min_length=2, description="검색어 (이메일 또는 사용자명)"),
        limit: int = Query(10, ge=1, le=50, description="결과 최대 개수"),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """사용자 검색 (그룹 초대용)"""
    group_repo = GroupRepository(db)

    users = await group_repo.search_users(
        search_term=query,
        limit=limit
    )

    # 자기 자신은 제외
    users = [user for user in users if user["user_id"] != current_user["user_id"]]

    return users
