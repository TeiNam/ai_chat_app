from datetime import datetime, timedelta
from typing import Annotated

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

    # JWT 토큰 생성
    access_token = create_access_token(
        data={"sub": str(user["user_id"]), "email": user["email"]}
    )

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

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserOut(
            user_id=user["user_id"],
            email=user["email"],
            username=user["username"],
            is_admin=user["is_admin"],
            is_group_owner=user["is_group_owner"],
            profile_url=user["profile_url"]
        )
    }


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