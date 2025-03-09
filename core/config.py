from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI ChatBot API"
    PROJECT_DESCRIPTION: str = "FastAPI 기반 AI ChatBot 백엔드 API"
    PROJECT_VERSION: str = "0.1.0"

    # 서버 설정
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DEBUG_MODE: bool = True

    # 데이터베이스 설정
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "ai_chat_bot"
    DB_POOL_SIZE: int = 5
    DB_POOL_MAX_SIZE: int = 20

    # JWT 설정
    SECRET_KEY: str = "your-secret-key-replace-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 시간

    # CORS 설정
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # 쿠키 설정
    COOKIE_SECURE: bool = False  # 개발 환경에서는 False, 프로덕션에서는 True로 변경

    # 암호화 설정
    CRYPTO_SALT: str = "ai_chat_bot_salt"  # 프로덕션에서는 반드시 변경

    # 이메일 설정
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your-email@gmail.com"
    SMTP_PASSWORD: str = "your-app-password"
    SMTP_FROM_EMAIL: str = "your-email@gmail.com"
    SMTP_USE_TLS: bool = True

    # 프론트엔드 URL (이메일 인증 링크 등에 사용)
    FRONTEND_URL: str = "http://localhost:3000"

    # Redis 설정
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 1
    REDIS_PASSWORD: str = ""
    REDIS_SSL: bool = False
    REDIS_INVITATION_EXPIRE: int = 60 * 60 * 24 * 7  # 초대 토큰 만료 시간 (7일)

    @property
    def REDIS_URL(self) -> str:
        """Redis 연결 URL 생성"""
        auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        protocol = "rediss" if self.REDIS_SSL else "redis"
        return f"{protocol}://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()