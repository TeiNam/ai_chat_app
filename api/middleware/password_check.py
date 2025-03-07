from typing import Callable

from fastapi import Request
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings


class PasswordChangeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # 비밀번호 변경 필요 여부를 확인하지 않아도 되는 경로
        excluded_paths = [
            "/api/auth/login",
            "/api/auth/logout",
            "/api/users",
            "/api/users/verify-email",
            "/api/users/reset-password",
            "/api/users/reset-password/request",
            "/api/users/me/password"
        ]

        # 제외된 경로인 경우 미들웨어 처리 생략
        if any(request.url.path.startswith(path) for path in excluded_paths):
            return await call_next(request)

        # JWT 토큰 확인
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            # 쿠키에서 토큰 확인
            cookie_token = request.cookies.get("access_token")
            if cookie_token and cookie_token.startswith("Bearer "):
                token = cookie_token.split(" ")[1]

        # 토큰이 없으면 그냥 통과
        if not token:
            return await call_next(request)

        try:
            # 토큰 디코딩
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            # 비밀번호 변경 필요 여부 확인
            pwd_change_required = payload.get("pwd_change_required", False)

            # 비밀번호 변경이 필요한 경우 특별 헤더 추가
            response = await call_next(request)

            if pwd_change_required:
                response.headers["X-Password-Change-Required"] = "true"
                response.headers["X-Password-Change-Message"] = "비밀번호를 180일 이상 변경하지 않았습니다. 보안을 위해 비밀번호를 변경해주세요."

            return response

        except JWTError:
            # 토큰 디코딩 실패 시 그냥 통과
            return await call_next(request)
