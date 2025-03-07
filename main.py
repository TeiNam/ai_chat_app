import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.password_check import PasswordChangeMiddleware
from api.router import auth_router, user_router
from core.config import settings
from core.database import get_connection_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB 커넥션 풀 초기화
    app.state.db_pool = await get_connection_pool()
    logger.info("Database connection pool established")

    yield

    # DB 커넥션 풀 정리
    if hasattr(app.state, "db_pool"):
        await app.state.db_pool.close()
        logger.info("Database connection pool closed")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 비밀번호 변경 체크 미들웨어 추가
app.add_middleware(PasswordChangeMiddleware)

# 라우터 등록
app.include_router(auth_router.router, prefix="/api", tags=["auth"])
app.include_router(user_router.router, prefix="/api", tags=["users"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG_MODE
    )
