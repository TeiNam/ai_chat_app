import logging
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query

from api.deps.auth import get_current_user
from api.schemas.api_key import (
    ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse, ApiKeyDetailResponse,
    VerifyApiKeyRequest, VerifyApiKeyResponse
)
from core.database import get_db
from repository.api_key_repository import ApiKeyRepository

router = APIRouter(tags=["api-keys"])
logger = logging.getLogger(__name__)


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
        api_key_data: ApiKeyCreate,
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """새 API 키를 등록합니다."""
    api_key_repo = ApiKeyRepository(db)

    # API 키 유효성 확인 (실제 서비스 호출)
    is_valid, error = await api_key_repo.check_service_availability(
        api_key=api_key_data.api_key,
        vendor=api_key_data.vendor
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "유효하지 않은 API 키입니다."
        )

    # API 키 등록
    api_key_id, error = await api_key_repo.create_api_key(
        user_id=current_user["user_id"],
        vendor=api_key_data.vendor,
        api_key=api_key_data.api_key,
        is_active=api_key_data.is_active
    )

    if not api_key_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error or "API 키 등록에 실패했습니다."
        )

    # 등록된 API 키 정보 조회
    api_key = await api_key_repo.get_api_key_by_id(api_key_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API 키가 등록되었지만 정보를 불러올 수 없습니다."
        )

    # 마스킹된 API 키 준비
    original_key = api_key_data.api_key
    masked_key = original_key[:4] + "*" * 8 if original_key else ""
    api_key["masked_key"] = masked_key
    api_key["api_key"] = None  # 응답에서 실제 키 제거

    return api_key


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def get_user_api_keys(
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """사용자의 API 키 목록을 조회합니다."""
    api_key_repo = ApiKeyRepository(db)

    # API 키 목록 조회
    api_keys = await api_key_repo.get_user_api_keys(
        user_id=current_user["user_id"],
        decrypt=False  # 복호화하지 않음
    )

    return api_keys


@router.get("/api-keys/{api_key_id}", response_model=ApiKeyDetailResponse)
async def get_api_key_detail(
        api_key_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """API 키 상세 정보를 조회합니다 (복호화된 값 포함)."""
    api_key_repo = ApiKeyRepository(db)

    # 소유권 확인
    is_owner, error = await api_key_repo.check_api_key_owner(
        api_key_id=api_key_id,
        user_id=current_user["user_id"]
    )

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error or "이 API 키에 접근할 권한이 없습니다."
        )

    # API 키 조회 (복호화)
    api_key = await api_key_repo.get_api_key_by_id(
        api_key_id=api_key_id,
        decrypt=True
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API 키를 찾을 수 없습니다."
        )

    # 마스킹된 버전 준비
    original_key = api_key["api_key"]
    api_key["masked_key"] = original_key[:4] + "*" * 8 if original_key else ""

    return api_key


@router.put("/api-keys/{api_key_id}", response_model=ApiKeyResponse)
async def update_api_key(
        api_key_data: ApiKeyUpdate,
        api_key_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """API 키 정보를 업데이트합니다."""
    api_key_repo = ApiKeyRepository(db)

    # 소유권 확인
    is_owner, error = await api_key_repo.check_api_key_owner(
        api_key_id=api_key_id,
        user_id=current_user["user_id"]
    )

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error or "이 API 키를 수정할 권한이 없습니다."
        )

    # 새 API 키 값이 있으면 유효성 확인
    if api_key_data.api_key:
        vendor = api_key_data.vendor

        # vendor가 지정되지 않았으면 기존 vendor 가져오기
        if not vendor:
            existing_key = await api_key_repo.get_api_key_by_id(api_key_id)
            if existing_key:
                vendor = existing_key["vendor"]
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="API 키를 찾을 수 없습니다."
                )

        # API 키 유효성 확인
        is_valid, error = await api_key_repo.check_service_availability(
            api_key=api_key_data.api_key,
            vendor=vendor
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error or "유효하지 않은 API 키입니다."
            )

    # API 키 업데이트
    success, error = await api_key_repo.update_api_key(
        api_key_id=api_key_id,
        vendor=api_key_data.vendor,
        api_key=api_key_data.api_key,
        is_active=api_key_data.is_active
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error or "API 키 업데이트에 실패했습니다."
        )

    # 업데이트된 API 키 정보 조회
    api_key = await api_key_repo.get_api_key_by_id(api_key_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API 키를 찾을 수 없습니다."
        )

    # 마스킹된 버전 준비 (업데이트된 값이 있으면 사용)
    if api_key_data.api_key:
        masked_key = api_key_data.api_key[:4] + "*" * 8
    else:
        # 기존 키를 복호화하여 마스킹
        decrypted_key = await api_key_repo.get_api_key_by_id(
            api_key_id=api_key_id,
            decrypt=True
        )
        original_key = decrypted_key["api_key"] if decrypted_key else ""
        masked_key = original_key[:4] + "*" * 8 if original_key else ""

    api_key["masked_key"] = masked_key
    api_key["api_key"] = None  # 응답에서 실제 키 제거

    return api_key


@router.delete("/api-keys/{api_key_id}", response_model=Dict[str, str])
async def delete_api_key(
        api_key_id: int = Path(..., gt=0),
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """API 키를 삭제합니다."""
    api_key_repo = ApiKeyRepository(db)

    # 소유권 확인
    is_owner, error = await api_key_repo.check_api_key_owner(
        api_key_id=api_key_id,
        user_id=current_user["user_id"]
    )

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error or "이 API 키를 삭제할 권한이 없습니다."
        )

    # 그룹에서 사용 중인지 확인 (선택적)
    # TODO: 그룹에서 사용 중인 API 키 확인 로직 추가

    # API 키 삭제
    success, error = await api_key_repo.delete_api_key(api_key_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error or "API 키 삭제에 실패했습니다."
        )

    return {"message": "API 키가 성공적으로 삭제되었습니다."}


@router.post("/api-keys/verify", response_model=VerifyApiKeyResponse)
async def verify_api_key(
        verify_data: VerifyApiKeyRequest,
        current_user: Dict[str, Any] = Depends(get_current_user),
        db=Depends(get_db)
):
    """API 키의 유효성을 검증합니다."""
    api_key_repo = ApiKeyRepository(db)

    # API 키 유효성 확인
    is_valid, error = await api_key_repo.check_service_availability(
        api_key=verify_data.api_key,
        vendor=verify_data.vendor
    )

    return {
        "is_valid": is_valid,
        "message": "API 키가 유효합니다." if is_valid else (error or "유효하지 않은 API 키입니다.")
    }