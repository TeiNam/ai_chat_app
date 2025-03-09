import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from asyncmy.cursors import DictCursor

logger = logging.getLogger(__name__)


class InvitationRepository:
    """그룹 초대 관리 리포지토리"""

    def __init__(self, db: Optional[DictCursor]):
        self.db = db

    def _check_db_connection(self) -> bool:
        """DB 연결이 존재하는지 확인하고 없으면 로그를 남깁니다."""
        if self.db is None:
            logger.error("데이터베이스 연결이 없어 작업을 수행할 수 없습니다.")
            return False
        return True

    async def create_invitation(
            self, group_id: int, user_id: int, invited_by: int, note: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        사용자를 그룹에 초대합니다.

        Args:
            group_id: 그룹 ID
            user_id: 초대할 사용자 ID
            invited_by: 초대한 사용자 ID
            note: 초대 메시지

        Returns:
            Tuple[Optional[int], Optional[str]]: (초대 ID, 오류 메시지)
        """
        if not self._check_db_connection():
            return None, "데이터베이스 연결이 없습니다."

        try:
            # 이미 초대된 상태인지 확인
            check_query = """
            SELECT invitation_id, status 
            FROM group_invitation
            WHERE group_id = %s AND user_id = %s AND status IN ('pending', 'accepted')
            """
            await self.db.execute(check_query, (group_id, user_id))
            existing = await self.db.fetchone()

            if existing:
                if existing["status"] == "accepted":
                    return None, "이미 그룹에 가입된 사용자입니다."
                return existing["invitation_id"], "이미 초대된 사용자입니다."

            # 새 초대 생성
            query = """
            INSERT INTO group_invitation 
            (group_id, user_id, invited_by, note, status, create_at)
            VALUES (%s, %s, %s, %s, 'pending', %s)
            """
            await self.db.execute(
                query,
                (group_id, user_id, invited_by, note, datetime.now())
            )
            invitation_id = self.db.lastrowid

            return invitation_id, None

        except Exception as e:
            logger.error(f"그룹 초대 생성 실패: {e}")
            return None, f"그룹 초대 생성 중 오류가 발생했습니다: {str(e)}"

    async def get_user_invitations(
            self, user_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        사용자의 초대 목록을 조회합니다.

        Args:
            user_id: 사용자 ID
            status: 초대 상태 필터 (pending, accepted, declined, canceled)

        Returns:
            List[Dict[str, Any]]: 초대 목록
        """
        if not self._check_db_connection():
            return []

        try:
            # 상태 필터 추가
            status_filter = ""
            params = [user_id]

            if status:
                status_filter = "AND gi.status = %s"
                params.append(status)

            query = f"""
            SELECT 
                gi.invitation_id, gi.group_id, gi.user_id, gi.invited_by, 
                gi.note, gi.status, gi.create_at, gi.update_at,
                g.name as group_name,
                u.username as inviter_username,
                u.email as inviter_email
            FROM group_invitation gi
            JOIN `group` g ON gi.group_id = g.group_id
            JOIN user u ON gi.invited_by = u.user_id
            WHERE gi.user_id = %s {status_filter}
            ORDER BY gi.create_at DESC
            """

            await self.db.execute(query, tuple(params))
            results = await self.db.fetchall()

            return results

        except Exception as e:
            logger.error(f"사용자 초대 목록 조회 실패: {e}")
            return []

    async def get_group_invitations(
            self, group_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        그룹의 초대 목록을 조회합니다.

        Args:
            group_id: 그룹 ID
            status: 초대 상태 필터 (pending, accepted, declined, canceled)

        Returns:
            List[Dict[str, Any]]: 초대 목록
        """
        if not self._check_db_connection():
            return []

        try:
            # 상태 필터 추가
            status_filter = ""
            params = [group_id]

            if status:
                status_filter = "AND gi.status = %s"
                params.append(status)

            query = f"""
            SELECT 
                gi.invitation_id, gi.group_id, gi.user_id, gi.invited_by, 
                gi.note, gi.status, gi.create_at, gi.update_at,
                u.username as username, 
                u.email as email,
                u.profile_url as profile_url,
                inv.username as inviter_username
            FROM group_invitation gi
            JOIN user u ON gi.user_id = u.user_id
            JOIN user inv ON gi.invited_by = inv.user_id
            WHERE gi.group_id = %s {status_filter}
            ORDER BY gi.create_at DESC
            """

            await self.db.execute(query, tuple(params))
            results = await self.db.fetchall()

            return results

        except Exception as e:
            logger.error(f"그룹 초대 목록 조회 실패: {e}")
            return []

    async def get_invitation_by_id(self, invitation_id: int) -> Optional[Dict[str, Any]]:
        """
        초대 ID로 초대 정보를 조회합니다.

        Args:
            invitation_id: 초대 ID

        Returns:
            Optional[Dict[str, Any]]: 초대 정보
        """
        if not self._check_db_connection():
            return None

        try:
            query = """
            SELECT 
                gi.invitation_id, gi.group_id, gi.user_id, gi.invited_by, 
                gi.note, gi.status, gi.create_at, gi.update_at,
                g.name as group_name,
                u.username as username,
                u.email as email,
                inv.username as inviter_username,
                inv.email as inviter_email
            FROM group_invitation gi
            JOIN `group` g ON gi.group_id = g.group_id
            JOIN user u ON gi.user_id = u.user_id
            JOIN user inv ON gi.invited_by = inv.user_id
            WHERE gi.invitation_id = %s
            """

            await self.db.execute(query, (invitation_id,))
            result = await self.db.fetchone()

            return result

        except Exception as e:
            logger.error(f"초대 정보 조회 실패: {e}")
            return None

    async def update_invitation_status(
            self, invitation_id: int, status: str
    ) -> Tuple[bool, Optional[str]]:
        """
        초대 상태를 업데이트합니다.

        Args:
            invitation_id: 초대 ID
            status: 새 상태 (pending, accepted, declined, canceled)

        Returns:
            Tuple[bool, Optional[str]]: (성공 여부, 오류 메시지)
        """
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            query = """
            UPDATE group_invitation
            SET status = %s, update_at = %s
            WHERE invitation_id = %s
            """

            await self.db.execute(query, (status, datetime.now(), invitation_id))
            return True, None

        except Exception as e:
            logger.error(f"초대 상태 업데이트 실패: {e}")
            return False, f"초대 상태 업데이트 중 오류가 발생했습니다: {str(e)}"