import json
import logging
from typing import Any, Dict, Optional, Union

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from core.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis 연결 및 캐시 관리를 위한 클래스"""

    def __init__(self):
        self._pool = None
        self._client = None
        self._is_connected = False

    async def initialize(self) -> bool:
        """Redis 연결 풀 초기화"""
        try:
            # 연결 풀 생성
            self._pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                encoding="utf-8"
            )

            # Redis 클라이언트 생성
            self._client = redis.Redis(connection_pool=self._pool)

            # 연결 테스트
            await self._client.ping()

            self._is_connected = True
            logger.info("Redis 연결 성공")
            return True

        except Exception as e:
            self._is_connected = False
            logger.error(f"Redis 연결 실패: {e}")
            return False

    async def close(self) -> None:
        """Redis 연결 종료"""
        if self._pool:
            await self._pool.disconnect()
            logger.info("Redis 연결 종료")

    async def get(self, key: str) -> Optional[Any]:
        """
        Redis에서 키에 해당하는 값을 가져옵니다.
        JSON 형식으로 저장된 값은 자동으로 파싱합니다.
        """
        if not self._is_connected or not self._client:
            logger.warning("Redis에 연결되어 있지 않습니다")
            return None

        try:
            # 키 조회
            value = await self._client.get(key)

            if value is None:
                return None

            # JSON 파싱 시도
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # JSON이 아니면 원래 값 반환
                return value

        except Exception as e:
            logger.error(f"Redis 데이터 조회 실패: {e}")
            return None

    async def set(
            self,
            key: str,
            value: Any,
            expire: Optional[int] = None
    ) -> bool:
        """
        Redis에 키-값 쌍을 저장합니다.
        딕셔너리나 리스트 등의 객체는 자동으로 JSON으로 직렬화합니다.

        Args:
            key: 저장할 키
            value: 저장할 값 (객체는 JSON으로 직렬화됨)
            expire: 만료 시간(초), None이면 만료 없음

        Returns:
            bool: 저장 성공 여부
        """
        if not self._is_connected or not self._client:
            logger.warning("Redis에 연결되어 있지 않습니다")
            return False

        try:
            # 딕셔너리나 리스트 등은 JSON으로 직렬화
            if isinstance(value, (dict, list, tuple, set)):
                value = json.dumps(value)

            # 키-값 저장
            await self._client.set(key, value)

            # 만료 시간 설정
            if expire is not None:
                await self._client.expire(key, expire)

            return True

        except Exception as e:
            logger.error(f"Redis 데이터 저장 실패: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Redis에서 키를 삭제합니다."""
        if not self._is_connected or not self._client:
            logger.warning("Redis에 연결되어 있지 않습니다")
            return False

        try:
            await self._client.delete(key)
            return True

        except Exception as e:
            logger.error(f"Redis 데이터 삭제 실패: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Redis에 키가 존재하는지 확인합니다."""
        if not self._is_connected or not self._client:
            logger.warning("Redis에 연결되어 있지 않습니다")
            return False

        try:
            return bool(await self._client.exists(key))

        except Exception as e:
            logger.error(f"Redis 키 존재 여부 확인 실패: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        """Redis 연결 상태 확인"""
        return self._is_connected


# 싱글톤 인스턴스 생성
redis_manager = RedisManager()