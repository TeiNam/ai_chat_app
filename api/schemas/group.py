from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class GroupBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=20)


class GroupCreate(GroupBase):
    api_key_id: int = Field(..., gt=0)


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=20)
    is_active: Optional[bool] = None
    api_key_id: Optional[int] = Field(None, gt=0)


class GroupMemberBase(BaseModel):
    note: Optional[str] = Field(None, max_length=100)


class GroupMemberCreate(GroupMemberBase):
    user_id: int = Field(..., gt=0)


class GroupMemberUpdate(BaseModel):
    is_accpet: Optional[bool] = None
    is_active: Optional[bool] = None
    note: Optional[str] = Field(None, max_length=100)


class GroupMemberResponse(GroupMemberBase):
    member_id: int
    group_id: int
    user_id: int
    is_accpet: bool
    is_active: bool
    create_at: datetime
    update_at: datetime
    user_info: Optional[Dict[str, Any]] = None


class GroupResponse(GroupBase):
    group_id: int
    owner_user_id: int
    api_key_id: int
    is_active: bool
    create_at: datetime
    update_at: datetime
    members_count: Optional[int] = None
    api_key_info: Optional[Dict[str, Any]] = None
    owner_info: Optional[Dict[str, Any]] = None


class GroupDetailResponse(GroupResponse):
    members: List[GroupMemberResponse] = []


class GroupUserInviteRequest(BaseModel):
    """사용자 ID를 통한 그룹 초대 요청"""
    user_id: int = Field(..., gt=0)
    note: Optional[str] = Field(None, max_length=100)


class GroupUserInviteResponse(BaseModel):
    """사용자 ID를 통한 그룹 초대 응답"""
    success: bool
    message: str
    invitation_id: Optional[int] = None
    user_info: Optional[Dict[str, Any]] = None


class GroupInviteAcceptRequest(BaseModel):
    invitation_token: str