import logging
from typing import Dict

from fastapi import APIRouter, Depends, Request

from core.database import check_db_connection
from core.email import email_manager

router = APIRouter(tags=["system"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=Dict[str, Dict[str, bool]])
async def health_check(request: Request):
    """서버 상태와 필수 서비스 연결 상태를 확인합니다."""
    # 데이터베이스 연결 확인
    db_pool = getattr(request.app.state, "db_pool", None)
    db_connected = await check_db_connection(db_pool)

    # 이메일 서버 연결 확인 (이미 애플리케이션 시작 시 확인했으므로 status만 반환)
    email_server_connected = email_manager.is_available

    return {
        "status": {
            "server": True,  # 서버가 실행 중이므로 항상 True
            "database": db_connected,
            "email_server": email_server_connected
        }
    }