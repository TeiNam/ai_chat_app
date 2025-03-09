import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from asyncmy.cursors import DictCursor

logger = logging.getLogger(__name__)


class GroupRepository:
    def __init__(self, db: Optional[DictCursor]):
        self.db = db

    def _check_db_connection(self) -> bool:
        """DB 연결이 존재하는지 확인하고 없으면 로그를 남깁니다."""
        if self.db is None:
            logger.error("데이터베이스 연결이 없어 작업을 수행할 수 없습니다.")
            return False
        return True

    async def create_group(
            self, owner_user_id: int, api_key_id: int, name: str
    ) -> Tuple[Optional[int], Optional[str]]:
        """새 그룹을 생성합니다."""
        if not self._check_db_connection():
            return None, "데이터베이스 연결이 없습니다."

        try:
            # 트랜잭션 시작
            await self.db.execute("START TRANSACTION")

            # 사용자가 그룹 소유자가 아니라면 상태 업데이트
            update_user_query = """
            UPDATE user 
            SET is_group_owner = 1
            WHERE user_id = %s AND is_group_owner = 0
            """
            await self.db.execute(update_user_query, (owner_user_id,))

            # 그룹 생성
            query = """
            INSERT INTO `group` (owner_user_id, api_key_id, name)
            VALUES (%s, %s, %s)
            """
            await self.db.execute(query, (owner_user_id, api_key_id, name))
            group_id = self.db.lastrowid

            # 소유자를 그룹 멤버로 자동 추가 (항상 승인 및 활성화 상태)
            member_query = """
            INSERT INTO group_member (group_id, user_id, is_accpet, is_active)
            VALUES (%s, %s, 1, 1)
            """
            await self.db.execute(member_query, (group_id, owner_user_id))

            logger.info(f"그룹 생성 완료: group_id={group_id}, owner_id={owner_user_id}, 멤버 자동 추가됨")

            # 트랜잭션 커밋
            await self.db.execute("COMMIT")

            return group_id, None

        except Exception as e:
            # 트랜잭션 롤백
            await self.db.execute("ROLLBACK")
            logger.error(f"그룹 생성 실패: {e}")
            return None, f"그룹 생성 중 오류가 발생했습니다: {str(e)}"

    async def get_group_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        """그룹 ID로 그룹 정보를 조회합니다."""
        if not self._check_db_connection():
            return None

        try:
            query = """
            SELECT g.*, COUNT(gm.member_id) as members_count
            FROM `group` g
            LEFT JOIN group_member gm ON g.group_id = gm.group_id
            WHERE g.group_id = %s
            GROUP BY g.group_id
            """
            await self.db.execute(query, (group_id,))
            result = await self.db.fetchone()
            return result

        except Exception as e:
            logger.error(f"그룹 조회 실패: {e}")
            return None

    async def get_group_with_api_key_info(self, group_id: int) -> Optional[Dict[str, Any]]:
        """그룹 및 API 키 정보를 함께 조회합니다."""
        if not self._check_db_connection():
            return None

        try:
            query = """
            SELECT g.*, ak.vendor, ak.is_active as api_key_active, 
                   u.username as owner_username, u.email as owner_email,
                   COUNT(gm.member_id) as members_count
            FROM `group` g
            JOIN api_key ak ON g.api_key_id = ak.api_key_id
            JOIN user u ON g.owner_user_id = u.user_id
            LEFT JOIN group_member gm ON g.group_id = gm.group_id
            WHERE g.group_id = %s
            GROUP BY g.group_id
            """
            await self.db.execute(query, (group_id,))
            result = await self.db.fetchone()

            if result:
                # API 키 정보 구성
                result["api_key_info"] = {
                    "api_key_id": result["api_key_id"],
                    "vendor": result["vendor"],
                    "is_active": bool(result["api_key_active"])
                }

                # 소유자 정보 구성
                result["owner_info"] = {
                    "user_id": result["owner_user_id"],
                    "username": result["owner_username"],
                    "email": result["owner_email"]
                }

                # 중복 필드 제거
                for field in ["vendor", "api_key_active", "owner_username", "owner_email"]:
                    if field in result:
                        del result[field]

            return result

        except Exception as e:
            logger.error(f"그룹 및 API 키 정보 조회 실패: {e}")
            return None

    async def get_group_members(self, group_id: int) -> List[Dict[str, Any]]:
        """그룹 멤버 목록을 조회합니다."""
        if not self._check_db_connection():
            return []

        try:
            query = """
            SELECT gm.*, u.username, u.email, u.profile_url
            FROM group_member gm
            JOIN user u ON gm.user_id = u.user_id
            WHERE gm.group_id = %s
            ORDER BY gm.create_at ASC
            """
            await self.db.execute(query, (group_id,))
            results = await self.db.fetchall()

            members = []
            for row in results:
                # 사용자 정보 구성
                row["user_info"] = {
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "email": row["email"],
                    "profile_url": row["profile_url"]
                }

                # 중복 필드 제거
                for field in ["username", "email", "profile_url"]:
                    if field in row:
                        del row[field]

                members.append(row)

            return members

        except Exception as e:
            logger.error(f"그룹 멤버 조회 실패: {e}")
            return []

    async def get_user_groups(self, user_id: int, include_pending: bool = False) -> List[Dict[str, Any]]:
        """사용자가 속한 그룹 목록을 조회합니다. (소유자이거나 멤버인 그룹)"""
        if not self._check_db_connection():
            return []

        try:
            # is_accpet 조건 설정
            accept_condition = ""
            if not include_pending:
                accept_condition = "AND gm.is_accpet = 1"

            # 쿼리 수정: 소유자이거나 멤버인 그룹 모두 조회
            query = f"""
            SELECT g.*, 
                   COUNT(other_gm.member_id) as members_count,
                   u.username as owner_username, 
                   u.email as owner_email,
                   ak.vendor, 
                   ak.is_active as api_key_active,
                   IFNULL(gm.is_accpet, 1) as is_accpet, 
                   IFNULL(gm.is_active, 1) as member_active
            FROM `group` g
            JOIN user u ON g.owner_user_id = u.user_id
            JOIN api_key ak ON g.api_key_id = ak.api_key_id
            LEFT JOIN group_member other_gm ON g.group_id = other_gm.group_id
            LEFT JOIN group_member gm ON g.group_id = gm.group_id AND gm.user_id = %s
            WHERE g.owner_user_id = %s OR (gm.user_id = %s {accept_condition})
            GROUP BY g.group_id
            ORDER BY g.create_at DESC
            """

            # 디버깅용 로그 추가
            logger.info(f"사용자 그룹 조회 쿼리 실행: user_id={user_id}")

            await self.db.execute(query, (user_id, user_id, user_id))
            results = await self.db.fetchall()

            logger.info(f"조회된 그룹 수: {len(results)}")

            groups = []
            for row in results:
                # API 키 정보 구성
                row["api_key_info"] = {
                    "api_key_id": row["api_key_id"],
                    "vendor": row["vendor"],
                    "is_active": bool(row["api_key_active"])
                }

                # 소유자 정보 구성
                row["owner_info"] = {
                    "user_id": row["owner_user_id"],
                    "username": row["owner_username"],
                    "email": row["owner_email"]
                }

                # 멤버십 정보 구성
                is_owner = row["owner_user_id"] == user_id
                row["membership"] = {
                    "is_accpet": bool(row["is_accpet"]),
                    "is_active": bool(row["member_active"]),
                    "is_owner": is_owner
                }

                # 중복 필드 제거
                for field in ["vendor", "api_key_active", "owner_username", "owner_email",
                              "is_accpet", "member_active"]:
                    if field in row:
                        del row[field]

                groups.append(row)

            return groups

        except Exception as e:
            logger.error(f"사용자 그룹 조회 실패: {e}")
            return []

    async def update_group(
            self, group_id: int, name: Optional[str] = None,
            is_active: Optional[bool] = None, api_key_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """그룹 정보를 업데이트합니다."""
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            # 업데이트할 필드 동적 구성
            fields = []
            params = []

            if name is not None:
                fields.append("name = %s")
                params.append(name)

            if is_active is not None:
                fields.append("is_active = %s")
                params.append(1 if is_active else 0)

            if api_key_id is not None:
                fields.append("api_key_id = %s")
                params.append(api_key_id)

            if not fields:
                return True, None  # 업데이트할 내용이 없음

            # 쿼리 구성
            query = f"""
            UPDATE `group` 
            SET {', '.join(fields)}
            WHERE group_id = %s
            """
            params.append(group_id)

            await self.db.execute(query, tuple(params))
            return True, None

        except Exception as e:
            logger.error(f"그룹 업데이트 실패: {e}")
            return False, f"그룹 업데이트 중 오류가 발생했습니다: {str(e)}"

    async def delete_group(self, group_id: int) -> Tuple[bool, Optional[str]]:
        """그룹을 삭제합니다 (비활성화)."""
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            # 트랜잭션 시작
            await self.db.execute("START TRANSACTION")

            # 그룹 비활성화
            group_query = """
            UPDATE `group` 
            SET is_active = 0
            WHERE group_id = %s
            """
            await self.db.execute(group_query, (group_id,))

            # 모든 그룹 멤버 비활성화
            member_query = """
            UPDATE group_member 
            SET is_active = 0
            WHERE group_id = %s
            """
            await self.db.execute(member_query, (group_id,))

            # 트랜잭션 커밋
            await self.db.execute("COMMIT")

            return True, None

        except Exception as e:
            # 트랜잭션 롤백
            await self.db.execute("ROLLBACK")
            logger.error(f"그룹 삭제 실패: {e}")
            return False, f"그룹 삭제 중 오류가 발생했습니다: {str(e)}"

    async def add_group_member(
            self, group_id: int, user_id: int,
            is_accpet: bool = False, note: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[str]]:
        """그룹에 멤버를 추가합니다."""
        if not self._check_db_connection():
            return None, "데이터베이스 연결이 없습니다."

        try:
            # 이미 멤버인지 확인
            check_query = """
            SELECT member_id, is_accpet, is_active 
            FROM group_member
            WHERE group_id = %s AND user_id = %s
            """
            await self.db.execute(check_query, (group_id, user_id))
            existing = await self.db.fetchone()

            if existing:
                if existing["is_accpet"] and existing["is_active"]:
                    return None, "이미 활성화된 그룹 멤버입니다."

                # 이미 존재하는 멤버 정보 업데이트
                update_query = """
                UPDATE group_member
                SET is_accpet = %s, is_active = 1, note = %s
                WHERE member_id = %s
                """
                await self.db.execute(
                    update_query,
                    (1 if is_accpet else 0, note, existing["member_id"])
                )
                return existing["member_id"], None

            # 새 멤버 추가
            insert_query = """
            INSERT INTO group_member (group_id, user_id, is_accpet, note)
            VALUES (%s, %s, %s, %s)
            """
            await self.db.execute(
                insert_query,
                (group_id, user_id, 1 if is_accpet else 0, note)
            )
            member_id = self.db.lastrowid
            return member_id, None

        except Exception as e:
            logger.error(f"그룹 멤버 추가 실패: {e}")
            return None, f"그룹 멤버 추가 중 오류가 발생했습니다: {str(e)}"

    async def update_group_member(
            self, member_id: int, is_accpet: Optional[bool] = None,
            is_active: Optional[bool] = None, note: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """그룹 멤버 정보를 업데이트합니다."""
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            # 업데이트할 필드 동적 구성
            fields = []
            params = []

            if is_accpet is not None:
                fields.append("is_accpet = %s")
                params.append(1 if is_accpet else 0)

            if is_active is not None:
                fields.append("is_active = %s")
                params.append(1 if is_active else 0)

            if note is not None:
                fields.append("note = %s")
                params.append(note)

            if not fields:
                return True, None  # 업데이트할 내용이 없음

            # 쿼리 구성
            query = f"""
            UPDATE group_member 
            SET {', '.join(fields)}
            WHERE member_id = %s
            """
            params.append(member_id)

            await self.db.execute(query, tuple(params))
            return True, None

        except Exception as e:
            logger.error(f"그룹 멤버 업데이트 실패: {e}")
            return False, f"그룹 멤버 업데이트 중 오류가 발생했습니다: {str(e)}"

    async def remove_group_member(self, member_id: int) -> Tuple[bool, Optional[str]]:
        """그룹에서 멤버를 제거합니다 (비활성화)."""
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            query = """
            UPDATE group_member 
            SET is_active = 0
            WHERE member_id = %s
            """
            await self.db.execute(query, (member_id,))
            return True, None

        except Exception as e:
            logger.error(f"그룹 멤버 제거 실패: {e}")
            return False, f"그룹 멤버 제거 중 오류가 발생했습니다: {str(e)}"

    async def get_member_info(self, member_id: int) -> Optional[Dict[str, Any]]:
        """멤버 ID로 그룹 멤버 정보를 조회합니다."""
        if not self._check_db_connection():
            return None

        try:
            query = """
            SELECT gm.*, u.username, u.email, u.profile_url
            FROM group_member gm
            JOIN user u ON gm.user_id = u.user_id
            WHERE gm.member_id = %s
            """
            await self.db.execute(query, (member_id,))
            result = await self.db.fetchone()

            if result:
                # 사용자 정보 구성
                result["user_info"] = {
                    "user_id": result["user_id"],
                    "username": result["username"],
                    "email": result["email"],
                    "profile_url": result["profile_url"]
                }

                # 중복 필드 제거
                for field in ["username", "email", "profile_url"]:
                    if field in result:
                        del result[field]

            return result

        except Exception as e:
            logger.error(f"그룹 멤버 정보 조회 실패: {e}")
            return None

    async def get_member_by_user_and_group(
            self, user_id: int, group_id: int
    ) -> Optional[Dict[str, Any]]:
        """사용자 ID와 그룹 ID로 멤버 정보를 조회합니다."""
        if not self._check_db_connection():
            return None

        try:
            query = """
            SELECT gm.*
            FROM group_member gm
            WHERE gm.user_id = %s AND gm.group_id = %s
            """
            await self.db.execute(query, (user_id, group_id))
            result = await self.db.fetchone()
            return result

        except Exception as e:
            logger.error(f"사용자-그룹 멤버 정보 조회 실패: {e}")
            return None

    async def store_invitation(
            self, group_id: int, email: str, invited_by: int,
            token: str, expires_at: datetime
    ) -> Tuple[bool, Optional[str]]:
        """그룹 초대 정보를 저장합니다."""
        if not self._check_db_connection():
            return False, "데이터베이스 연결이 없습니다."

        try:
            # 이미 존재하는 초대 삭제
            delete_query = """
            DELETE FROM verification_token 
            WHERE token_type = 'group_invitation' AND extra_data LIKE %s
            """
            await self.db.execute(delete_query, (f"%\"group_id\":{group_id},\"email\":\"{email}\"%",))

            # 초대 정보 JSON 생성
            extra_data = f'{{"group_id":{group_id},"email":"{email}","invited_by":{invited_by}}}'

            # 새 초대 저장
            insert_query = """
            INSERT INTO verification_token (token, token_type, expires_at, extra_data)
            VALUES (%s, 'group_invitation', %s, %s)
            """
            await self.db.execute(insert_query, (token, expires_at, extra_data))
            return True, None

        except Exception as e:
            logger.error(f"그룹 초대 저장 실패: {e}")
            return False, f"그룹 초대 저장 중 오류가 발생했습니다: {str(e)}"

    async def verify_invitation(self, token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """초대 토큰을 검증하고 그룹 및 이메일 정보를 반환합니다."""
        if not self._check_db_connection():
            return None, "데이터베이스 연결이 없습니다."

        try:
            query = """
            SELECT token, token_type, expires_at, extra_data 
            FROM verification_token
            WHERE token = %s AND token_type = 'group_invitation'
            """
            await self.db.execute(query, (token,))
            result = await self.db.fetchone()

            if not result:
                return None, "유효하지 않은 초대 토큰입니다."

            # 토큰 만료 확인
            if result["expires_at"] < datetime.now():
                # 만료된 토큰 삭제
                delete_query = """
                DELETE FROM verification_token 
                WHERE token = %s
                """
                await self.db.execute(delete_query, (token,))
                return None, "초대 토큰이 만료되었습니다."

            # extra_data에서 정보 추출
            import json
            try:
                extra_data = json.loads(result["extra_data"])
                return extra_data, None
            except json.JSONDecodeError:
                return None, "초대 정보를 처리할 수 없습니다."

        except Exception as e:
            logger.error(f"초대 토큰 검증 실패: {e}")
            return None, f"초대 토큰 검증 중 오류가 발생했습니다: {str(e)}"

    async def get_user_owned_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """사용자가 소유한 API 키 목록을 조회합니다."""
        if not self._check_db_connection():
            return []

        try:
            query = """
            SELECT api_key_id, vendor, is_active, create_at, update_at
            FROM api_key
            WHERE user_id = %s
            ORDER BY update_at DESC
            """
            await self.db.execute(query, (user_id,))
            results = await self.db.fetchall()
            return results

        except Exception as e:
            logger.error(f"사용자 API 키 조회 실패: {e}")
            return []

    async def get_pending_members(self, group_id: int) -> List[Dict[str, Any]]:
        """그룹의 대기 중인(승인 대기) 멤버 목록을 조회합니다."""
        if not self._check_db_connection():
            return []

        try:
            query = """
            SELECT gm.*, u.username, u.email, u.profile_url
            FROM group_member gm
            JOIN user u ON gm.user_id = u.user_id
            WHERE gm.group_id = %s AND gm.is_accpet = 0
            ORDER BY gm.create_at ASC
            """
            await self.db.execute(query, (group_id,))
            results = await self.db.fetchall()

            members = []
            for row in results:
                # 사용자 정보 구성
                row["user_info"] = {
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "email": row["email"],
                    "profile_url": row["profile_url"]
                }

                # 중복 필드 제거
                for field in ["username", "email", "profile_url"]:
                    if field in row:
                        del row[field]

                members.append(row)

            return members

        except Exception as e:
            logger.error(f"대기 중인 멤버 목록 조회 실패: {e}")
            return []