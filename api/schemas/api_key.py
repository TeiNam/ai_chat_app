from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class ApiKeyBase(BaseModel):
    vendor: str = Field(..., min_length=1, max_length=10)
    is_active: bool = True


class ApiKeyCreate(ApiKeyBase):
    api_key: str = Field(..., min_length=5)

    @validator('vendor')
    @classmethod
    def validate_vendor(cls, v: str) -> str:
        allowed_vendors = ['openai', 'anthropic', 'google', 'azure']
        if v.lower() not in allowed_vendors:
            raise ValueError(f"지원하지 않는 AI 제공사입니다. 지원 제공사: {', '.join(allowed_vendors)}")
        return v.lower()


class ApiKeyUpdate(BaseModel):
    vendor: Optional[str] = Field(None, min_length=1, max_length=10)
    is_active: Optional[bool] = None
    api_key: Optional[str] = None

    @validator('vendor')
    @classmethod
    def validate_vendor(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v

        allowed_vendors = ['openai', 'anthropic', 'google', 'azure']
        if v.lower() not in allowed_vendors:
            raise ValueError(f"지원하지 않는 AI 제공사입니다. 지원 제공사: {', '.join(allowed_vendors)}")
        return v.lower()


class ApiKeyResponse(ApiKeyBase):
    api_key_id: int
    user_id: int
    create_at: datetime
    update_at: datetime
    # API 키의 마스킹된 버전을 반환
    masked_key: Optional[str] = None


class ApiKeyDetailResponse(ApiKeyResponse):
    # 실제 API 키 값 (복호화된 API 키)
    api_key: Optional[str] = None


class VerifyApiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=5)
    vendor: str = Field(..., min_length=1, max_length=10)


class VerifyApiKeyResponse(BaseModel):
    is_valid: bool
    message: Optional[str] = None