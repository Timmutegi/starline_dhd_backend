"""
Notice Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
from app.models.notice import NoticePriority, NoticeCategory, NoticeTargetType


# Notice Schemas
class NoticeBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    summary: Optional[str] = Field(None, max_length=500)
    priority: NoticePriority = NoticePriority.MEDIUM
    category: NoticeCategory = NoticeCategory.GENERAL
    # New targeting fields
    target_type: NoticeTargetType = NoticeTargetType.ALL_USERS
    target_roles: Optional[List[str]] = None
    target_users: Optional[List[str]] = None
    target_client_id: Optional[str] = None
    target_location_id: Optional[str] = None
    publish_date: Optional[datetime] = None
    expire_date: Optional[datetime] = None
    requires_acknowledgment: bool = False
    attachment_urls: Optional[List[str]] = None


class NoticeCreate(NoticeBase):
    """Schema for creating a new notice"""
    pass


class NoticeUpdate(BaseModel):
    """Schema for updating an existing notice"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = Field(None, max_length=500)
    priority: Optional[NoticePriority] = None
    category: Optional[NoticeCategory] = None
    # New targeting fields
    target_type: Optional[NoticeTargetType] = None
    target_roles: Optional[List[str]] = None
    target_users: Optional[List[str]] = None
    target_client_id: Optional[str] = None
    target_location_id: Optional[str] = None
    is_active: Optional[bool] = None
    publish_date: Optional[datetime] = None
    expire_date: Optional[datetime] = None
    requires_acknowledgment: Optional[bool] = None
    attachment_urls: Optional[List[str]] = None


class NoticeResponse(NoticeBase):
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    created_by_name: Optional[str] = None  # Name of the user who created the notice
    read: bool = False  # Will be populated based on user's read status
    acknowledged: bool = False  # Will be populated based on user's acknowledgment

    class Config:
        from_attributes = True


class NoticeReadReceiptCreate(BaseModel):
    notice_id: str


class NoticeAcknowledgment(BaseModel):
    notice_id: str


class NoticesList(BaseModel):
    """List of notices with pagination"""
    notices: List[NoticeResponse]
    total: int
    page: int
    page_size: int
    unread_count: int


# Statistics and Acknowledgment Schemas
class NoticeStatistics(BaseModel):
    """Statistics for a notice"""
    notice_id: str
    total_recipients: int
    read_count: int
    acknowledged_count: int
    unread_count: int
    pending_acknowledgment_count: int
    read_percentage: float
    acknowledged_percentage: float


class NoticeAcknowledgmentDetail(BaseModel):
    """Detailed acknowledgment info for a user"""
    user_id: str
    user_name: str
    user_email: str
    role_name: Optional[str] = None
    read_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    status: str  # "read", "acknowledged", "pending"

    class Config:
        from_attributes = True


# Targeting Helper Schemas
class TargetableUser(BaseModel):
    """User available for targeting"""
    id: str
    name: str
    email: str
    role_name: Optional[str] = None


class TargetableClient(BaseModel):
    """Client available for targeting"""
    id: str
    name: str
    client_id: str


class TargetableLocation(BaseModel):
    """Location available for targeting"""
    id: str
    name: str
    address: Optional[str] = None
