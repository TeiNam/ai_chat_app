import logging
from typing import AsyncGenerator, Optional

import asyncmy
from asyncmy.cursors import DictCursor
from asyncmy.pool import Pool
from fastapi import Depends, Request, HTTPException, status

from core.config import settings

logger = logging.getLogger(__name__)


async def get_connection_pool() -> Optional[Pool]:
    """데이터베이스 연결 풀을 생성합니다. 실패해도 None을 반환하고 계속 진행합니다."""
    try:
        pool = await asyncmy.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            db=settings.DB_NAME,
            maxsize=settings.DB_POOL_MAX_SIZE,
            minsize=settings.DB_POOL_SIZE,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=5
        )
        logger.info("데이터베이스 연결 풀 생성 성공")
        return pool
    except Exception as e:
        logger.error(f"데이터베이스 연결 풀 생성 실패: {e}")
        return None


async def check_db_connection(pool: Optional[Pool] = None) -> bool:
    """
    데이터베이스 연결 상태를 확인합니다.

    Args:
        pool: 기존 연결 풀 (없으면 새로 생성 시도)

    Returns:
        bool: 연결 성공 여부
    """
    try:
        if pool is None:
            pool = await get_connection_pool()
            if pool is None:
                return False

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                return result is not None and result[0] == 1

    except Exception as e:
        logger.error(f"데이터베이스 연결 확인 실패: {e}")
        return False


async def get_db(request: Request) -> AsyncGenerator:
    """요청별 데이터베이스 연결을 제공하는 의존성 주입 함수입니다."""
    if not hasattr(request.app.state, "db_pool") or request.app.state.db_pool is None:
        # 재연결 시도
        request.app.state.db_pool = await get_connection_pool()

    if request.app.state.db_pool is None:
        # DB 연결이 없어도 정상 동작하는 API도 있을 수 있으므로 예외 발생 대신 로그만 기록
        logger.error("데이터베이스 연결 없음, 해당 API 요청 실패 가능성 있음")
        # 예외 발생 대신 None을 yield할 경우 해당 API에서 적절히 처리해야 함
        yield None
        return

    async with request.app.state.db_pool.acquire() as conn:
        async with conn.cursor(DictCursor) as cursor:
            try:
                yield cursor
            except Exception as e:
                logger.error(f"데이터베이스 쿼리 실행 중 오류 발생: {e}")
                await conn.rollback()
                raise