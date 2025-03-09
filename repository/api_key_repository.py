import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from asyncmy.cursors import DictCursor

from core.crypto import crypto_manager

logger = logging.getLogger(__name__)


class ApiKeyRepository:
    def __init__(self, db: Optional[DictCursor]):
        self.db = db

    def _check_db_connection(self) -> bool:
        """DB 연결이 존재하는지 확인하고 없으면 로그를 남깁니다."""
        if self.db is None:
            logger.error("데이터베이스 연결이 없어 작업을 수행할 수 없습니다.")
            return False
        return True

    async def create_api_key(
            self, user_id: int, vendor: str, api_key: str, is_active: bool = True
    ) -> Tuple[Optional[int], Optional[str]]:
        """새 API 키를 생성합니다."""
        if not self._check_db_connection():
            return None, "데이터베이스 연결이 없습니다."

        try:
            # API 키 암호화
            encrypted_key = crypto_manager.encrypt(api_key)

            # API 키 저장
            query = """
            INSERT INTO api_key (user_id, vendor, api_key, is_active)
            VALUES (%s, %s, %s, %s)
            """
            await self.db.execute(
                query,
                (user_id, vendor, encrypted_key, 1 if is_active else 0)
            )
            api_key_id = self.db.lastrowid

            return api_key_id, None

        except Exception as e:
            logger.error(f"API 키 생성 실패: {e}")
            return None, f"API 키 생성 중 오류가 발생했습니다: {str(e)}"

    async def get_api_key_by_id(
            self, api_key_id: int, decrypt: bool = False
    ) -> Optional[Dict[str, Any]]:
        """API 키 ID로 API 키 정보를 조회합니다."""
        if not self._check_db_connection():
            return None

        try:
            query = """
            SELECT api_key_id, user_id, vendor, api_key, is_active, create_at, update_at
            FROM api_key
            WHERE api_key_id = %s
            """
            await self.db.execute(query, (api_key_id,))
            result = await self.db.fetchone()

            if result and decrypt and result["api_key"]:
                # API 키 복호화
                result["api_key"] = crypto_manager.decrypt(result["api_key"])

            return result

        except Exception as e:
            logger.error(f"API 키 조회 실패: {e}")
            return None

    async def get_user_api_keys(
            self, user_id: int, decrypt: bool = False
    ) -> List[Dict[str, Any]]:
        """사용자의 API 키 목록을 조회합니다."""
        if not self._check_db_connection():
            return []

        try:
            query = """
            SELECT api_key_id, user_id, vendor, api_key, is_active, create_at, update_at
            FROM api_key
            WHERE user_id = %s
            ORDER BY update_at DESC
            """
            await self.db.execute(query, (user_id,))
            results = await self.db.fetchall()

            # API 키 마스킹 또는 복호화
            for result in results:
                if result["api_key"]:
                    # 원본 API 키 저장 (복호화 필요 시)
                    if decrypt:
                        result["api_key"] = crypto_manager.decrypt(result["api_key"])

                    # 마스킹된 키 추가
                    encrypted_key = result["api_key"]
                    if decrypt:
                        # 이미 복호화된 경우 마스킹 처리
                        masked_key = result["api_key"][:4] + "*" * 8
                    else:
                        # 암호화된 키를 복호화한 후 마스킹 처리
                        decrypted_key = crypto_manager.decrypt(encrypted_key)
                        masked_key = decrypted_key[:4] + "*" * 8 if decrypted_key else ""

                    result["masked_key"] = masked_key

                    # 복호화가 필요없는 경우 암호화된 키는 제거
                    if not decrypt:
                        result["api_key"] = None

            return results

        except Exception as e:
            logger.error(f"사용자 API 키 목록 조회 실패: {e}")
            return []

    async def update_api_key(
            self, api_key_id: int,
            vendor: Optional[str] = None,
            api_key: Optional[str] = None,
            is_active: Optional[bool] = None
    ) -> Tuple[bool, Optional[str]]:
        """API 키 정보를 업데이트합니다."""
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            # 업데이트할 필드 동적 구성
            fields = []
            params = []

            if vendor is not None:
                fields.append("vendor = %s")
                params.append(vendor)

            if api_key is not None:
                # API 키 암호화
                encrypted_key = crypto_manager.encrypt(api_key)
                fields.append("api_key = %s")
                params.append(encrypted_key)

            if is_active is not None:
                fields.append("is_active = %s")
                params.append(1 if is_active else 0)

            if not fields:
                return True, None  # 업데이트할 내용이 없음

            # 쿼리 구성
            query = f"""
            UPDATE api_key 
            SET {', '.join(fields)}
            WHERE api_key_id = %s
            """
            params.append(api_key_id)

            await self.db.execute(query, tuple(params))
            return True, None

        except Exception as e:
            logger.error(f"API 키 업데이트 실패: {e}")
            return False, f"API 키 업데이트 중 오류가 발생했습니다: {str(e)}"

    async def delete_api_key(self, api_key_id: int) -> Tuple[bool, Optional[str]]:
        """API 키를 삭제합니다."""
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            query = """
            DELETE FROM api_key
            WHERE api_key_id = %s
            """
            await self.db.execute(query, (api_key_id,))

            return True, None

        except Exception as e:
            logger.error(f"API 키 삭제 실패: {e}")
            return False, f"API 키 삭제 중 오류가 발생했습니다: {str(e)}"

    async def check_api_key_owner(
            self, api_key_id: int, user_id: int
    ) -> Tuple[bool, Optional[str]]:
        """API 키의 소유자가 맞는지 확인합니다."""
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            query = """
            SELECT user_id
            FROM api_key
            WHERE api_key_id = %s
            """
            await self.db.execute(query, (api_key_id,))
            result = await self.db.fetchone()

            if not result:
                return False, "API 키를 찾을 수 없습니다."

            if result["user_id"] != user_id:
                return False, "이 API 키의 소유자가 아닙니다."

            return True, None

        except Exception as e:
            logger.error(f"API 키 소유자 확인 실패: {e}")
            return False, f"API 키 소유자 확인 중 오류가 발생했습니다: {str(e)}"

    async def check_service_availability(
            self, api_key: str, vendor: str
    ) -> Tuple[bool, Optional[str]]:
        """API 키의 유효성을 실제 서비스에 확인합니다."""
        try:
            # TODO: 실제 AI 서비스 연동하여 API 키 유효성 확인
            # 지금은 간단히 길이 체크 정도만 수행 (실제로 API 호출 필요)

            if vendor == "openai":
                if api_key.startswith("sk-") and len(api_key) > 20:
                    return True, None
                return False, "잘못된 OpenAI API 키 형식입니다."

            elif vendor == "anthropic":
                if len(api_key) > 20:
                    return True, None
                return False, "잘못된 Anthropic API 키 형식입니다."

            elif vendor == "google":
                if len(api_key) > 20:
                    return True, None
                return False, "잘못된 Google AI API 키 형식입니다."

            elif vendor == "azure":
                if len(api_key) > 20:
                    return True, None
                return False, "잘못된 Azure API 키 형식입니다."

            return False, "지원하지 않는 AI 제공사입니다."

        except Exception as e:
            logger.error(f"API 키 유효성 확인 실패: {e}")
            return False, f"API 키 유효성 확인 중 오류가 발생했습니다."