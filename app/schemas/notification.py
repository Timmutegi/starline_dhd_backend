from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

class NotificationType(str, Enum):
    CRITICAL = "critical"
    REMINDER = "reminder"
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"

class NotificationCategory(str, Enum):
    MEDICATION = "medication"
    APPOINTMENT = "appointment"
    TASK = "task"
    INCIDENT = "incident"
    SCHEDULE = "schedule"
    SYSTEM = "system"
    GENERAL = "general"

class NotificationCreate(BaseModel):
    user_id: str = Field(..., description="Target user ID")
    title: str = Field(..., min_length=1, max_length=200, description="Notification title")
    message: str = Field(..., min_length=1, max_length=1000, description="Notification message")
    type: NotificationType = Field(default=NotificationType.INFO, description="Notification type")
    category: NotificationCategory = Field(default=NotificationCategory.GENERAL, description="Notification category")
    action_url: Optional[str] = Field(None, max_length=500, description="URL for notification action")
    action_text: Optional[str] = Field(None, max_length=100, description="Text for action button")
    related_entity_type: Optional[str] = Field(None, max_length=50, description="Type of related entity")
    related_entity_id: Optional[str] = Field(None, description="ID of related entity")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    expires_at: Optional[datetime] = Field(None, description="When notification expires")

class NotificationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    message: Optional[str] = Field(None, min_length=1, max_length=1000)
    type: Optional[NotificationType] = None
    category: Optional[NotificationCategory] = None
    action_url: Optional[str] = Field(None, max_length=500)
    action_text: Optional[str] = Field(None, max_length=100)
    expires_at: Optional[datetime] = None

class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    type: str
    category: str
    is_read: bool
    read_at: Optional[datetime]
    action_url: Optional[str]
    action_text: Optional[str]
    related_entity_type: Optional[str]
    related_entity_id: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True

class NotificationStats(BaseModel):
    total_count: int = Field(..., description="Total number of notifications")
    unread_count: int = Field(..., description="Number of unread notifications")
    critical_count: int = Field(..., description="Number of unread critical notifications")
    reminder_count: int = Field(..., description="Number of unread reminder notifications")
    info_count: int = Field(..., description="Number of unread info notifications")

class BulkNotificationAction(BaseModel):
    notification_ids: List[str] = Field(..., description="List of notification IDs")
    action: str = Field(..., description="Action to perform (mark_read, delete)")

class NotificationPreferences(BaseModel):
    email_enabled: bool = Field(default=True, description="Enable email notifications")
    push_enabled: bool = Field(default=True, description="Enable push notifications")
    critical_email: bool = Field(default=True, description="Send critical notifications via email")
    reminder_email: bool = Field(default=True, description="Send reminder notifications via email")
    quiet_hours_start: Optional[str] = Field(None, description="Start of quiet hours (HH:MM)")
    quiet_hours_end: Optional[str] = Field(None, description="End of quiet hours (HH:MM)")
    categories: Dict[str, bool] = Field(default={}, description="Category-specific preferences")

    @validator('quiet_hours_start')
    def validate_start_time_format(cls, v):
        if v is not None:
            try:
                hours, minutes = v.split(':')
                if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                    raise ValueError('Invalid time format')
            except (ValueError, AttributeError):
                raise ValueError('Time must be in HH:MM format')
        return v

    @validator('quiet_hours_end')
    def validate_end_time_format(cls, v):
        if v is not None:
            try:
                hours, minutes = v.split(':')
                if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                    raise ValueError('Invalid time format')
            except (ValueError, AttributeError):
                raise ValueError('Time must be in HH:MM format')
        return v