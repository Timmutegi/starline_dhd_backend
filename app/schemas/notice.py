"""
Notice Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.notice import NoticePriority, NoticeCategory


# Notice Schemas
class NoticeBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    summary: Optional[str] = Field(None, max_length=500)
    priority: NoticePriority = NoticePriority.MEDIUM
    category: NoticeCategory = NoticeCategory.GENERAL
    target_roles: Optional[List[str]] = None
    target_users: Optional[List[str]] = None
    publish_date: Optional[datetime] = None
    expire_date: Optional[datetime] = None
    requires_acknowledgment: bool = False
    attachment_urls: Optional[List[str]] = None


class NoticeCreate(NoticeBase):
    pass


class NoticeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = Field(None, max_length=500)
    priority: Optional[NoticePriority] = None
    category: Optional[NoticeCategory] = None
    target_roles: Optional[List[str]] = None
    target_users: Optional[List[str]] = None
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
