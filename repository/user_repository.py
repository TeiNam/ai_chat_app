import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from asyncmy.cursors import DictCursor

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, db: DictCursor):
        self.db = db

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """사용자 ID로 사용자 정보를 조회합니다."""
        query = """
        SELECT user_id, email, is_active, is_admin, is_group_owner, username, 
               description, profile_url, create_at, update_at
        FROM user
        WHERE user_id = %s
        """
        await self.db.execute(query, (user_id,))
        result = await self.db.fetchone()
        return result

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """이메일로 사용자 정보를 조회합니다."""
        query = """
        SELECT user_id, email, is_active, is_admin, is_group_owner, username, 
               description, profile_url, create_at, update_at
        FROM user
        WHERE email = %s
        """
        await self.db.execute(query, (email,))
        result = await self.db.fetchone()
        return result

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