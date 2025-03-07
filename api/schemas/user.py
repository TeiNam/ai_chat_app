from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=20)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    confirm_password: str

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('비밀번호가 일치하지 않습니다')
        return v


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=20)
    description: Optional[str] = Field(None, max_length=50)
    profile_url: Optional[str] = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)
    confirm_password: str

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('새 비밀번호가 일치하지 않습니다')
        return v


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
    new_password: str = Field(..., min_length=6)
    confirm_password: str

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('새 비밀번호가 일치하지 않습니다')
        return v