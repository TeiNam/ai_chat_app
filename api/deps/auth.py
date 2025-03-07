import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError

from api.schemas.auth import TokenData
from core.config import settings
from core.database import get_db
from repository.user_repository import UserRepository

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
        request: Request,
        token: Optional[str] = Depends(oauth2_scheme),
        db=Depends(get_db)
):
    """현재 인증된 사용자를 가져옵니다."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="토큰이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 토큰이 헤더에 없으면 쿠키에서 확인
    if not token:
        cookie_token = request.cookies.get("access_token")
        if cookie_token and cookie_token.startswith("Bearer "):
            token = cookie_token.split(" ")[1]

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: int = int(payload.get("sub"))
        email: str = payload.get("email")

        if user_id is None or email is None:
            raise credentials_exception

        pwd_change_required = payload.get("pwd_change_required", False)
        token_data = TokenData(user_id=user_id, email=email, pwd_change_required=pwd_change_required)
    except (JWTError, ValidationError) as e:
        logger.error(f"토큰 검증 실패: {e}")
        raise credentials_exception

    # 사용자 정보 조회
    user_repo = UserRepository(db)
    user = await user_repo.get_user_by_id(token_data.user_id)

    if user is None:
        raise credentials_exception

    # 사용자 활성화 상태 확인
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="계정이 비활성화되어 있습니다",
        )

    return user


async def get_current_active_user(current_user=Depends(get_current_user)):
    """현재 활성화된 사용자를 가져옵니다."""
    if not current_user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="계정이 비활성화되어 있습니다",
        )
    return current_user


async def get_current_admin_user(current_user=Depends(get_current_user)):
    """현재 관리자 사용자를 가져옵니다."""
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 작업에 대한 권한이 없습니다. 관리자만 가능합니다.",
        )
    return current_user


async def get_current_admin_user(current_user=Depends(get_current_user)):
    """현재 관리자 사용자를 가져옵니다."""
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 작업에 대한 권한이 없습니다. 관리자만 가능합니다.",
        )
    return current_user


async def check_password_age(
        request: Request,
        token: Optional[str] = Depends(oauth2_scheme),
):
    """비밀번호 변경이 필요한지 확인합니다."""
    # 토큰이 헤더에 없으면 쿠키에서 확인
    if not token:
        cookie_token = request.cookies.get("access_token")
        if cookie_token and cookie_token.startswith("Bearer "):
            token = cookie_token.split(" ")[1]

    if not token:
        return {"password_change_required": False}

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        pwd_change_required = payload.get("pwd_change_required", False)

        if pwd_change_required:
            return {
                "password_change_required": True,
                "message": "비밀번호를 180일 이상 변경하지 않았습니다. 보안을 위해 비밀번호를 변경해주세요."
            }

        return {"password_change_required": False}

    except (JWTError, ValidationError) as e:
        logger.error(f"토큰 검증 실패: {e}")
        return {"password_change_required": False}