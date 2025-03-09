import logging
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query

from api.deps.auth import get_current_user
from api.schemas.group import (
    GroupInviteRequest, GroupInviteResponse, GroupInviteAcceptRequest,
    GroupUserInviteRequest, GroupUserInviteResponse
)
from core.database import get_db
from core.email import email_manager
from repository.group_repository import GroupRepository
from repository.user_repository import UserRepository
from repository.invitation_repository import InvitationRepository
from service.invitation_service import invitation_service

router = APIRouter(tags=["invitations"])
logger = logging.getLogger(__name__)


@router.get("/users/search", response_model=List[Dict[str, Any]])
async def search_users(
        q: str = Query(..., min_length=2, description="검색어 (이메일 또는 사용자명)"),
        limit: int = Query(10, ge=1, le=50, description="결과 최대 개수"),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """이메일이나 사용자명으로 사용자를 검색합니다."""
    user_repo = UserRepository(db)

    # 사용자 검색
    users = await user_repo.search_users(
        search_term=q,
        limit=limit
    )

    # 자기 자신은 결과에서 제외
    users = [user for user in users if user["user_id"] != current_user["user_id"]]

    return users


@router.post("/groups/{group_id}/invite-user", response_model=GroupUserInviteResponse)
async def invite_user_to_group(
        invite_data: GroupUserInviteRequest,
        group_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """사용자 ID를 사용하여 그룹에 초대합니다."""
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
            detail="그룹에 초대할 권한이 없습니다."
        )

    # 초대할 사용자 정보 조회
    user = await user_repo.get_user_by_id(invite_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="초대할 사용자를 찾을 수 없습니다."
        )

    # 자기 자신을 초대하는지 확인
    if user["user_id"] == current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자기 자신을 초대할 수 없습니다."
        )

    # 이미 멤버인지 확인
    existing_member = await group_repo.get_member_by_user_and_group(
        user_id=user["user_id"],
        group_id=group_id
    )
    if existing_member and existing_member["is_accpet"] and existing_member["is_active"]:
        return {
            "success": False,
            "message": "이미 그룹의 활성 멤버입니다.",
            "user_info": {
                "user_id": user["user_id"],
                "username": user["username"],
                "email": user["email"]
            }
        }

    try:
        # 초대 생성
        invitation_repo = InvitationRepository(db)

        invitation_id, error = await invitation_repo.create_invitation(
            group_id=group_id,
            user_id=user["user_id"],
            invited_by=current_user["user_id"],
            note=invite_data.note
        )

        if not invitation_id:
            return {
                "success": False,
                "message": error or "초대 생성에 실패했습니다.",
                "user_info": {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "email": user["email"]
                }
            }

        return {
            "success": True,
            "message": f"{user['username']}님을 그룹에 초대했습니다.",
            "invitation_id": invitation_id,
            "user_info": {
                "user_id": user["user_id"],
                "username": user["username"],
                "email": user["email"]
            }
        }

    except Exception as e:
        logger.error(f"사용자 초대 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"초대 과정에서 오류가 발생했습니다: {str(e)}"
        )


@router.post("/groups/{group_id}/invite", response_model=GroupInviteResponse)
async def invite_to_group(
        invite_data: GroupInviteRequest,
        group_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """이메일로 그룹 초대를 보냅니다."""
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
            detail="그룹에 초대할 권한이 없습니다."
        )

    # 초대할 이메일 주소로 사용자가 이미 존재하는지 확인
    user_repo = UserRepository(db)
    existing_user = await user_repo.get_user_by_email(invite_data.email)

    # 이미 초대된 멤버인지 확인
    if existing_user:
        # 사용자가 있으면 사용자 ID로 초대하도록 리다이렉트
        invitation_repo = InvitationRepository(db)

        # 기존 초대 확인
        invitations = await invitation_repo.get_user_invitations(
            user_id=existing_user["user_id"],
            status="pending"
        )

        for invitation in invitations:
            if invitation["group_id"] == group_id:
                return {
                    "message": "이미 초대된 사용자입니다.",
                    "invitation_sent": False,
                    "email": invite_data.email
                }

        # 사용자 ID로 초대 생성
        invitation_id, error = await invitation_repo.create_invitation(
            group_id=group_id,
            user_id=existing_user["user_id"],
            invited_by=current_user["user_id"],
            note=invite_data.note
        )

        if invitation_id:
            return {
                "message": "기존 사용자를 그룹에 초대했습니다.",
                "invitation_sent": True,
                "email": invite_data.email
            }

    # 이메일이 존재하지 않는 사용자에게 초대장 발송
    try:
        # Redis에 초대 정보 저장
        import secrets
        from datetime import datetime, timedelta

        invitation_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)

        success, error = await invitation_service.store_invitation(
            group_id=group_id,
            email=invite_data.email,
            invited_by=current_user["user_id"],
            token=invitation_token,
            expires_at=expires_at
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error or "초대 정보 저장에 실패했습니다."
            )

        # 초대 이메일 전송 시도
        try:
            email_sent = await email_manager.send_invitation_email(
                email=invite_data.email,
                inviter_name=current_user["username"],
                group_name=group["name"],
                invitation_token=invitation_token
            )
        except Exception as e:
            logger.error(f"이메일 발송 실패: {e}")
            email_sent = False

        if not email_sent:
            logger.warning(f"그