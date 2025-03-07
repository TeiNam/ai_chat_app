from datetime import datetime, timedelta
from typing import Annotated, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import EmailStr

from api.schemas.auth import Token, UserLogin, UserOut
from core.config import settings
from core.database import get_db
from core.security import create_access_token, get_password_hash, verify_password
from repository.user_repository import UserRepository

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/auth/login", response_model=Token)
async def login(
        response: Response,
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        db=Depends(get_db)
):
    user_repo = UserRepository(db)
    user = await user_repo.get_user_by_email(form_data.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 사용자 비밀번호 확인
    user_password = await user_repo.get_user_password(user["user_id"])
    if not user_password or not verify_password(form_data.password, user_password["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 사용자 활성화 상태 확인
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="계정이 비활성화되어 있습니다",
        )

    # 비밀번호 변경 필요 여부 확인 (180일 이상 지난 경우)
    password_change_required = False
    password_days_old = 0

    if user_password and user_password["update_at"]:
        password_age = datetime.now() - user_password["update_at"]
        password_days_old = password_age.days
        if password_days_old >= 180:  # 180일 이상 경과
            password_change_required = True

    # JWT 토큰 생성
    token_data = {
        "sub": str(user["user_id"]),
        "email": user["email"],
        "pwd_change_required": password_change_required
    }
    access_token = create_access_token(data=token_data)

    # 로그인 기록 저장
    await user_repo.create_login_history(user["user_id"])

    # 쿠키에 토큰 저장
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )

    # 응답 생성
    response_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserOut(
            user_id=user["user_id"],
            email=user["email"],
            username=user["username"],
            is_admin=user["is_admin"],
            is_group_owner=user["is_group_owner"],
            profile_url=user["profile_url"]
        ),
        "password_age": {
            "days": password_days_old,
            "change_required": password_change_required
        }
    }

    return response_data


@router.post("/auth/logout")
async def logout(response: Response):
    # 쿠키 삭제
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )
    return {"message": "로그아웃 되었습니다"}