import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import asynccontextmanager

from api.router import auth_router, user_router, health_router
from api.middleware.password_check import PasswordChangeMiddleware
from core.config import settings
from core.database import get_connection_pool, check_db_connection
from core.email import email_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 로그
    logger.info("애플리케이션 시작 중...")

    # DB 커넥션 풀 초기화 (실패해도 계속 진행)
    app.state.db_pool = await get_connection_pool()

    # DB 연결 상태 체크 - 로그 출력용
    if app.state.db_pool:
        is_connected = await check_db_connection(app.state.db_pool)
        if is_connected:
            logger.info("데이터베이스 연결 상태 확인 완료")
        else:
            logger.warning("데이터베이스에 연결되었지만 상태 확인 실패")
    else:
        logger.warning("DB 연결 없이 애플리케이션 실행 중")

    # 이메일 서버 연결 상태 체크 (비동기 함수를 클래스 메서드로 실행)
    email_check_result = await email_manager.check_connection()
    if email_check_result:
        logger.info("이메일 서버 연결 상태 확인 완료")
    else:
        logger.warning("이메일 서비스 연결 실패로 이메일 관련 기능이 제한됩니다")

    # 애플리케이션 실행 준비 완료
    logger.info("애플리케이션 시작 완료")

    yield

    # 애플리케이션 종료 시작
    logger.info("애플리케이션 종료 중...")

    # DB 커넥션 풀 정리
    if hasattr(app.state, "db_pool") and app.state.db_pool:
        await app.state.db_pool.close()
        logger.info("데이터베이스 연결 풀 정리 완료")

    logger.info("애플리케이션 종료 완료")


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
app.include_router(health_router.router, prefix="/api", tags=["system"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG_MODE
    )