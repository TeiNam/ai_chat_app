import logging
from datetime import datetime
from typing import Dict, Optional, Any, Tuple

from asyncmy.cursors import DictCursor

from core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, db: Optional[DictCursor]):
        self.db = db

    def _check_db_connection(self) -> bool:
        """DB 연결이 존재하는지 확인하고 없으면 로그를 남깁니다."""
        if self.db is None:
            logger.error("데이터베이스 연결이 없어 작업을 수행할 수 없습니다.")
            return False
        return True

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """사용자 ID로 사용자 정보를 조회합니다."""
        if not self._check_db_connection():
            return None

        try:
            query = """
            SELECT user_id, email, is_active, is_admin, is_group_owner, username, 
                description, profile_url, create_at, update_at
            FROM user
            WHERE user_id = %s
            """
            await self.db.execute(query, (user_id,))
            result = await self.db.fetchone()
            return result
        except Exception as e:
            logger.error(f"사용자 조회 중 오류 발생: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """이메일로 사용자 정보를 조회합니다."""
        if not self._check_db_connection():
            return None

        try:
            query = """
            SELECT user_id, email, is_active, is_admin, is_group_owner, username, 
                description, profile_url, create_at, update_at
            FROM user
            WHERE email = %s
            """
            await self.db.execute(query, (email,))
            result = await self.db.fetchone()
            return result
        except Exception as e:
            logger.error(f"이메일로 사용자 조회 중 오류 발생: {e}")
            return None

    async def get_user_password(self, user_id: int) -> Optional[Dict[str, Any]]:
        """사용자 ID로 비밀번호 정보를 조회합니다."""
        query = """
        SELECT user_id, password, previous_password, update_at
        FROM user_password
        WHERE user_id = %s
        """
        await self.db.execute(query, (user_id,))
        result = await self.db.fetchone()
        return result

    async def create_login_history(self, user_id: int) -> int:
        """로그인 기록을 생성합니다."""
        query = """
        INSERT INTO login_hist (user_id, last_login_at)
        VALUES (%s, %s)
        """
        current_time = datetime.now()
        await self.db.execute(query, (user_id, current_time))
        return self.db.lastrowid

    async def create_user(
            self, email: str, username: str, password: str, is_active: bool = False
    ) -> Optional[int]:
        """새로운 사용자를 생성합니다."""
        try:
            # 트랜잭션 시작
            await self.db.execute("START TRANSACTION")

            # 사용자 생성
            user_query = """
            INSERT INTO user (email, is_active, is_admin, is_group_owner, username)
            VALUES (%s, %s, %s, %s, %s)
            """
            await self.db.execute(
                user_query, (email, is_active, False, False, username)
            )
            user_id = self.db.lastrowid

            # 비밀번호 저장
            password_query = """
            INSERT INTO user_password (user_id, password)
            VALUES (%s, %s)
            """
            hashed_password = get_password_hash(password)
            await self.db.execute(password_query, (user_id, hashed_password))

            # 기본 채팅 설정 생성
            settings_query = """
            INSERT INTO user_chat_setting (user_id)
            VALUES (%s)
            """
            await self.db.execute(settings_query, (user_id,))

            # 트랜잭션 커밋
            await self.db.execute("COMMIT")

            return user_id

        except Exception as e:
            # 트랜잭션 롤백
            await self.db.execute("ROLLBACK")
            logger.error(f"사용자 생성 실패: {e}")
            return None

    async def update_user(
            self, user_id: int, username: Optional[str] = None,
            description: Optional[str] = None, profile_url: Optional[str] = None
    ) -> bool:
        """사용자 정보를 업데이트합니다."""
        try:
            # 업데이트할 필드 동적 구성
            fields = []
            params = []

            if username is not None:
                fields.append("username = %s")
                params.append(username)

            if description is not None:
                fields.append("description = %s")
                params.append(description)

            if profile_url is not None:
                fields.append("profile_url = %s")
                params.append(profile_url)

            if not fields:
                return True  # 업데이트할 내용이 없음

            # 쿼리 구성
            query = f"""
            UPDATE user 
            SET {', '.join(fields)}
            WHERE user_id = %s
            """
            params.append(user_id)

            await self.db.execute(query, tuple(params))
            return True

        except Exception as e:
            logger.error(f"사용자 업데이트 실패: {e}")
            return False

    async def delete_user(self, user_id: int) -> bool:
        """사용자를 삭제합니다 (비활성화)."""
        try:
            query = """
            UPDATE user 
            SET is_active = 0
            WHERE user_id = %s
            """
            await self.db.execute(query, (user_id,))
            return True

        except Exception as e:
            logger.error(f"사용자 삭제 실패: {e}")
            return False

    async def update_password(self, user_id: int, new_password: str, current_password: Optional[str] = None) -> Tuple[
        bool, Optional[str]]:
        """
        사용자 비밀번호를 업데이트합니다.

        Args:
            user_id: 사용자 ID
            new_password: 새 비밀번호
            current_password: 현재 비밀번호 (패스워드 재설정 시에는 None)

        Returns:
            Tuple[bool, Optional[str]]: (성공 여부, 오류 메시지)
        """
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            # 현재 비밀번호 조회
            current_password_query = """
            SELECT password, previous_password FROM user_password
            WHERE user_id = %s
            """
            await self.db.execute(current_password_query, (user_id,))
            result = await self.db.fetchone()

            if not result:
                return False, "사용자 비밀번호 정보를 찾을 수 없습니다."

            # 새 비밀번호 해시
            hashed_new_password = get_password_hash(new_password)

            # 새 비밀번호가 현재 비밀번호와 같은지 확인
            if verify_password(new_password, result["password"]):
                return False, "새 비밀번호는 현재 비밀번호와 달라야 합니다."

            # 새 비밀번호가 이전 비밀번호와 같은지 확인 (previous_password가 있는 경우)
            if result["previous_password"] and verify_password(new_password, result["previous_password"]):
                return False, "새 비밀번호는 최근에 사용한 비밀번호와 달라야 합니다."

            # 비밀번호 업데이트 (현재 비밀번호를 previous_password로 이동)
            update_query = """
            UPDATE user_password 
            SET password = %s, previous_password = %s, update_at = %s
            WHERE user_id = %s
            """
            current_time = datetime.now()
            await self.db.execute(
                update_query, (hashed_new_password, result["password"], current_time, user_id)
            )
            return True, None

        except Exception as e:
            logger.error(f"비밀번호 업데이트 실패: {e}")
            return False, "비밀번호 업데이트 중 오류가 발생했습니다."

    async def activate_user(self, user_id: int) -> bool:
        """사용자 계정을 활성화합니다."""
        try:
            query = """
            UPDATE user 
            SET is_active = 1
            WHERE user_id = %s
            """
            await self.db.execute(query, (user_id,))
            return True

        except Exception as e:
            logger.error(f"사용자 활성화 실패: {e}")
            return False

    async def store_verification_token(self, user_id: int, token: str, token_type: str, expires_at: datetime) -> bool:
        """인증 토큰을 저장합니다."""
        try:
            # 먼저 기존 토큰 제거
            delete_query = """
            DELETE FROM verification_token 
            WHERE user_id = %s AND token_type = %s
            """
            await self.db.execute(delete_query, (user_id, token_type))

            # 새 토큰 저장
            insert_query = """
            INSERT INTO verification_token (user_id, token, token_type, expires_at)
            VALUES (%s, %s, %s, %s)
            """
            await self.db.execute(
                insert_query, (user_id, token, token_type, expires_at)
            )
            return True

        except Exception as e:
            logger.error(f"인증 토큰 저장 실패: {e}")
            return False

    async def verify_token(self, token: str, token_type: str) -> Optional[int]:
        """인증 토큰을 검증하고 사용자 ID를 반환합니다."""
        try:
            query = """
            SELECT user_id, expires_at 
            FROM verification_token
            WHERE token = %s AND token_type = %s
            """
            await self.db.execute(query, (token, token_type))
            result = await self.db.fetchone()

            if not result:
                return None

            # 토큰 만료 확인
            if result["expires_at"] < datetime.now():
                # 만료된 토큰 삭제
                delete_query = """
                DELETE FROM verification_token 
                WHERE token = %s
                """
                await self.db.execute(delete_query, (token,))
                return None

            # 토큰 사용 후 삭제
            delete_query = """
            DELETE FROM verification_token 
            WHERE token = %s
            """
            await self.db.execute(delete_query, (token,))

            return result["user_id"]

        except Exception as e:
            logger.error(f"토큰 검증 실패: {e}")
            return None
