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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()