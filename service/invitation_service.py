import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any

from core.config import settings
from core.redis import redis_manager

logger = logging.getLogger(__name__)


class InvitationService:
    """그룹 초대 관리 서비스"""

    @staticmethod
    async def store_invitation(
            group_id: int,
            email: str,
            invited_by: int,
            token: str,
            expires_at: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Redis에 그룹 초대 정보를 저장합니다.

        Args:
            group_id: 그룹 ID
            email: 초대할 이메일 주소
            invited_by: 초대한 사용자 ID
            token: 초대 토큰
            expires_at: 만료 시간

        Returns:
            Tuple[bool, Optional[str]]: (성공 여부, 오류 메시지)
        """
        try:
            # 만료 시간까지의 초 계산
            now = datetime.now()
            expires_in_seconds = int((expires_at - now).total_seconds())

            # 토큰이 이미 있는 경우 삭제
            token_key = f"invitation:{token}"
            email_key = f"invitation:email:{email}:{group_id}"

            # 같은 이메일로 같은 그룹에 보낸 초대가 있으면 삭제
            existing_token = await redis_manager.get(email_key)
            if existing_token:
                await redis_manager.delete(f"invitation:{existing_token}")

            # 초대 정보 저장
            invitation_data = {
                "group_id": group_id,
                "email": email,
                "invited_by": invited_by,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat()
            }

            # 토큰으로 초대 정보 저장
            await redis_manager.set(
                token_key,
                invitation_data,
                expire=expires_in_seconds
            )

            # 이메일과 그룹 ID로 토큰 참조 저장
            await redis_manager.set(
                email_key,
                token,
                expire=expires_in_seconds
            )

            logger.info(f"초대 정보 저장 성공: token={token[:10]}..., email={email}, group_id={group_id}")
            return True, None

        except Exception as e:
            logger.error(f"초대 정보 저장 실패: {e}")
            return False, f"초대 정보 저장 중 오류가 발생했습니다: {type(e).__name__}"

    @staticmethod
    async def verify_invitation(token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        초대 토큰을 검증하고 초대 정보를 반환합니다.

        Args:
            token: 초대 토큰

        Returns:
            Tuple[Optional[Dict[str, Any]], Optional[str]]: (초대 정보, 오류 메시지)
        """
        try:
            # 토큰으로 초대 정보 조회
            token_key = f"invitation:{token}"
            invitation_data = await redis_manager.get(token_key)

            if not invitation_data:
                return None, "유효하지 않은 초대 토큰입니다."

            # 만료 시간 확인
            expires_at = datetime.fromisoformat(invitation_data["expires_at"])
            if expires_at < datetime.now():
                # 만료된 토큰 삭제
                await redis_manager.delete(token_key)
                email_key = f"invitation:email:{invitation_data['email']}:{invitation_data['group_id']}"
                await redis_manager.delete(email_key)
                return None, "초대 토큰이 만료되었습니다."

            return invitation_data, None

        except Exception as e:
            logger.error(f"초대 토큰 검증 실패: {e}")
            return None, f"초대 토큰 검증 중 오류가 발생했습니다: {type(e).__name__}"

    @staticmethod
    async def delete_invitation(token: str) -> bool:
        """
        초대 토큰을 삭제합니다 (초대 수락 후).

        Args:
            token: 초대 토큰

        Returns:
            bool: 삭제 성공 여부
        """
        try:
            # 토큰으로 초대 정보 조회
            token_key = f"invitation:{token}"
            invitation_data = await redis_manager.get(token_key)

            if invitation_data:
                # 이메일 키 삭제
                email_key = f"invitation:email:{invitation_data['email']}:{invitation_data['group_id']}"
                await redis_manager.delete(email_key)

                # 토큰 키 삭제
                await redis_manager.delete(token_key)

            return True

        except Exception as e:
            logger.error(f"초대 토큰 삭제 실패: {e}")
            return False


# 서비스 인스턴스 생성
invitation_service = InvitationService()