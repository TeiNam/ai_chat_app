import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import EmailStr

from api.deps.auth import get_current_user
from api.schemas.user import (
    UserCreate, UserResponse, UserUpdate, UserPasswordUpdate,
    VerifyEmailRequest, RequestPasswordResetRequest, ResetPasswordRequest
)
from core.config import settings
from core.database import get_db
from core.email import email_manager
from core.security import get_password_hash, verify_password
from repository.user_repository import UserRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/users", response_model=Dict[str, str])
async def register_user(user_data: UserCreate, db=Depends(get_db)):
    """새 사용자를 등록합니다."""
    user_repo = UserRepository(db)

    # 이메일 중복 확인
    existing_user = await user_repo.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다."
        )

    # 사용자 생성
    user_id = await user_repo.create_user(
        email=user_data.email,
        username=user_data.username,
        password=user_data.password,
        is_active=False  # 이메일 인증 전이므로 비활성화 상태로 생성
    )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 등록 중 오류가 발생했습니다."
        )

    # 이메일 인증 토큰 생성
    verification_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=24)

    # 인증 토큰 저장
    await user_repo.store_verification_token(
        user_id=user_id,
        token=verification_token,
        token_type="email_verification",
        expires_at=expires_at
    )

    # 인증 이메일 발송
    email_sent = await email_manager.send_verification_email(
        email=user_data.email,
        verification_token=verification_token
    )

    if not email_sent:
        logger.warning(f"인증 이메일 발송 실패: {user_data.email}")
        return {
            "message": "회원가입이 완료되었지만 이메일 서버 문제로 인증 이메일을 발송하지 못했습니다.",
            "email_status": "failed",
            "note": "관리자에게 문의하여 계정 활성화를 요청하세요."
        }

    return {"message": "회원가입이 완료되었습니다. 이메일 인증을 진행해주세요.", "email_status": "sent"}


@router.post("/users/verify-email", response_model=Dict[str, str])
async def verify_email(verification_data: VerifyEmailRequest, db=Depends(get_db)):
    """이메일 인증을 처리합니다."""
    user_repo = UserRepository(db)

    # 토큰 검증
    user_id = await user_repo.verify_token(
        token=verification_data.token,
        token_type="email_verification"
    )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않거나 만료된 인증 토큰입니다."
        )

    # 사용자 활성화
    success = await user_repo.activate_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 활성화 중 오류가 발생했습니다."
        )

    return {"message": "이메일 인증이 완료되었습니다. 이제 로그인할 수 있습니다."}


@router.get("/users/me", response_model=UserResponse)
async def get_current_user_info(
        current_user: Dict[str, Any] = Depends(get_current_user),
):
    """현재 로그인한 사용자의 정보를 가져옵니다."""
    return UserResponse(
        user_id=current_user["user_id"],
        email=current_user["email"],
        username=current_user["username"],
        is_active=current_user["is_active"],
        is_admin=current_user["is_admin"],
        is_group_owner=current_user["is_group_owner"],
        description=current_user["description"],
        profile_url=current_user["profile_url"],
        create_at=current_user["create_at"],
        update_at=current_user["update_at"]
    )


@router.put("/users/me", response_model=UserResponse)
async def update_user_info(
        user_data: UserUpdate,
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """현재 로그인한 사용자의 정보를 업데이트합니다."""
    user_repo = UserRepository(db)

    success = await user_repo.update_user(
        user_id=current_user["user_id"],
        username=user_data.username,
        description=user_data.description,
        profile_url=user_data.profile_url
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보 업데이트 중 오류가 발생했습니다."
        )

    # 업데이트된 사용자 정보 조회
    updated_user = await user_repo.get_user_by_id(current_user["user_id"])

    return UserResponse(
        user_id=updated_user["user_id"],
        email=updated_user["email"],
        username=updated_user["username"],
        is_active=updated_user["is_active"],
        is_admin=updated_user["is_admin"],
        is_group_owner=updated_user["is_group_owner"],
        description=updated_user["description"],
        profile_url=updated_user["profile_url"],
        create_at=updated_user["create_at"],
        update_at=updated_user["update_at"]
    )


@router.put("/users/me/password", response_model=Dict[str, str])
async def update_password(
        password_data: UserPasswordUpdate,
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """사용자 비밀번호를 업데이트합니다."""
    user_repo = UserRepository(db)

    # 현재 비밀번호 확인
    user_password = await user_repo.get_user_password(current_user["user_id"])

    if not user_password or not verify_password(
            password_data.current_password, user_password["password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다."
        )

    # 비밀번호 업데이트
    success = await user_repo.update_password(
        user_id=current_user["user_id"],
        new_password=password_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="비밀번호 업데이트 중 오류가 발생했습니다."
        )

    return {"message": "비밀번호가 성공적으로 변경되었습니다."}


@router.get("/users/me/password-status", response_model=Dict[str, Any])
async def get_password_status(
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """사용자 비밀번호 상태를 확인합니다."""
    user_repo = UserRepository(db)

    # 현재 비밀번호 정보 조회
    user_password = await user_repo.get_user_password(current_user["user_id"])

    if not user_password:
        return {
            "days_since_change": 0,
            "change_required": False,
            "last_changed": None
        }

    # 비밀번호 변경 후 경과 일수 계산
    password_age = datetime.now() - user_password["update_at"]
    days_since_change = password_age.days

    return {
        "days_since_change": days_since_change,
        "change_required": days_since_change >= 180,
        "last_changed": user_password["update_at"]
    }


@router.delete("/users/me", response_model=Dict[str, str])
async def delete_user(
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """사용자 계정을 삭제합니다 (비활성화)."""
    user_repo = UserRepository(db)

    success = await user_repo.delete_user(current_user["user_id"])

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 삭제 중 오류가 발생했습니다."
        )

    return {"message": "계정이 성공적으로 삭제되었습니다."}


@router.post("/users/reset-password/request", response_model=Dict[str, str])
async def request_password_reset(
        reset_data: RequestPasswordResetRequest,
        db=Depends(get_db)
):
    """비밀번호 재설정 요청을 처리합니다."""
    user_repo = UserRepository(db)

    # 이메일로 사용자 조회
    user = await user_repo.get_user_by_email(reset_data.email)

    if not user:
        # 보안을 위해 사용자가 존재하지 않아도 성공 메시지 반환
        return {"message": "비밀번호 재설정 이메일이 발송되었습니다."}

    # 비밀번호 재설정 토큰 생성
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=1)

    # 토큰 저장
    await user_repo.store_verification_token(
        user_id=user["user_id"],
        token=reset_token,
        token_type="password_reset",
        expires_at=expires_at
    )

    # 이메일 내용 구성
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    html_content = f"""
    <html>
        <body>
            <h2>AI 챗봇 서비스 비밀번호 재설정</h2>
            <p>안녕하세요,</p>
            <p>비밀번호 재설정을 요청하셨습니다. 아래 링크를 클릭하여 비밀번호를 재설정하세요:</p>
            <p><a href="{reset_url}">비밀번호 재설정하기</a></p>
            <p>링크는 1시간 동안 유효합니다.</p>
            <p>요청하지 않으셨다면 이 이메일을 무시하시기 바랍니다.</p>
            <p>감사합니다.</p>
        </body>
    </html>
    """

    # 이메일 발송
    await email_manager.send_email(
        to_email=[reset_data.email],
        subject="AI 챗봇 서비스 비밀번호 재설정",
        html_content=html_content
    )

    return {"message": "비밀번호 재설정 이메일이 발송되었습니다."}


@router.post("/users/reset-password", response_model=Dict[str, str])
async def reset_password(
        reset_data: ResetPasswordRequest,
        db=Depends(get_db)
):
    """비밀번호 재설정을 처리합니다."""
    user_repo = UserRepository(db)

    # 토큰 검증
    user_id = await user_repo.verify_token(
        token=reset_data.token,
        token_type="password_reset"
    )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않거나 만료된 토큰입니다."
        )

    # 비밀번호 업데이트
    success = await user_repo.update_password(
        user_id=user_id,
        new_password=reset_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="비밀번호 업데이트 중 오류가 발생했습니다."
        )

    return {"message": "비밀번호가 성공적으로 재설정되었습니다. 이제 로그인할 수 있습니다."}


@router.post("/users/invite", response_model=Dict[str, str])
async def invite_user(
        email: EmailStr,
        group_id: int,
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """다른 사용자를 그룹에 초대합니다."""
    # 그룹 소유자 확인
    if not current_user["is_group_owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 소유자만 초대할 수 있습니다."
        )

    # TODO: 그룹 소유권 확인 로직 추가

    # 초대 토큰 생성
    invitation_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=7)

    # 초대 정보 저장
    # TODO: 그룹 초대 정보 저장 로직 추가

    # 초대 이메일 발송
    await email_manager.send_invitation_email(
        email=email,
        inviter_name=current_user["username"],
        group_name="그룹 이름",  # TODO: 실제 그룹 이름 조회
        invitation_token=invitation_token
    )

    return {"message": f"{email}에게 초대 이메일이 발송되었습니다."}