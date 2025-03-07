from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=20)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=20)
    confirm_password: str

    @field_validator('password')
    @classmethod
    def password_requirements(cls, v: str) -> str:
        from core.utils import validate_password
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v

    @model_validator(mode='after')
    def passwords_match(self) -> 'UserCreate':
        if self.password != self.confirm_password:
            raise ValueError('비밀번호가 일치하지 않습니다')
        return self


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=20)
    description: Optional[str] = Field(None, max_length=50)
    profile_url: Optional[str] = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=20)
    confirm_password: str

    @field_validator('new_password')
    @classmethod
    def password_requirements(cls, v: str) -> str:
        from core.utils import validate_password
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v

    @model_validator(mode='after')
    def passwords_match(self) -> 'UserPasswordUpdate':
        if self.new_password != self.confirm_password:
            raise ValueError('새 비밀번호가 일치하지 않습니다')
        return self


class UserResponse(UserBase):
    user_id: int
    is_active: bool
    is_admin: bool
    is_group_owner: bool
    description: Optional[str] = None
    profile_url: Optional[str] = None
    create_at: datetime
    update_at: datetime


class VerifyEmailRequest(BaseModel):
    token: str


class RequestPasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=20)
    confirm_password: str

    @field_validator('new_password')
    @classmethod
    def password_requirements(cls, v: str) -> str:
        from core.utils import validate_password
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v

    @model_validator(mode='after')
    def passwords_match(self) -> 'ResetPasswordRequest':
        if self.new_password != self.confirm_password:
            raise ValueError('새 비밀번호가 일치하지 않습니다')
        return self


class PasswordAgeInfo(BaseModel):
    days: int
    change_required: bool