from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    email: EmailStr


class UserLogin(UserBase):
    password: str = Field(..., min_length=6)


class UserOut(BaseModel):
    user_id: int
    email: EmailStr
    username: str
    is_admin: bool
    is_group_owner: bool
    profile_url: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[EmailStr] = None