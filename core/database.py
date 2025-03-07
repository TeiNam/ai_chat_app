import logging
from typing import AsyncGenerator

import asyncmy
from asyncmy.cursors import DictCursor
from asyncmy.pool import Pool
from fastapi import Depends, Request

from core.config import settings

logger = logging.getLogger(__name__)


async def get_connection_pool() -> Pool:
    """데이터베이스 연결 풀을 생성합니다."""
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
        )
        return pool
    except Exception as e:
        logger.error(f"데이터베이스 연결 풀 생성 실패: {e}")
        raise


async def get_db(request: Request) -> AsyncGenerator:
    """요청별 데이터베이스 연결을 제공하는 의존성 주입 함수입니다."""
    if not hasattr(request.app.state, "db_pool"):
        request.app.state.db_pool = await get_connection_pool()

    async with request.app.state.db_pool.acquire() as conn:
        async with conn.cursor(DictCursor) as cursor:
            try:
                yield cursor
            except Exception as e:
                logger.error(f"데이터베이스 쿼리 실행 중 오류 발생: {e}")
                await conn.rollback()
                raise