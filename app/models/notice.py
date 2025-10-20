"""
Notice/Announcement Models
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.core.database import Base


class NoticePriority(str, enum.Enum):
    """Notice priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NoticeCategory(str, enum.Enum):
    """Notice categories"""
    GENERAL = "general"
    POLICY = "policy"
    SAFETY = "safety"
    TRAINING = "training"
    SYSTEM = "system"
    EMERGENCY = "emergency"


class Notice(Base):
    """Notice/Announcement model"""
    __tablename__ = "notices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(String(500), nullable=True, comment="Short summary for list views")

    # Classification
    priority = Column(SQLEnum(NoticePriority), nullable=False, default=NoticePriority.MEDIUM)
    category = Column(SQLEnum(NoticeCategory), nullable=False, default=NoticeCategory.GENERAL)

    # Targeting
    target_roles = Column(JSON, nullable=True, comment="List of role IDs, null means all roles")
    target_users = Column(JSON, nullable=True, comment="List of specific user IDs, null means all users")

    # Display control
    is_active = Column(Boolean, default=True)
    publish_date = Column(DateTime, nullable=True, comment="When to start showing the notice")
    expire_date = Column(DateTime, nullable=True, comment="When to stop showing the notice")

    # Acknowledgment
    requires_acknowledgment = Column(Boolean, default=False)

    # Attachments
    attachment_urls = Column(JSON, nullable=True, comment="List of attachment URLs")

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    organization = relationship("Organization")
    creator = relationship("User", foreign_keys=[created_by])
    read_receipts = relationship("NoticeReadReceipt", back_populates="notice", cascade="all, delete-orphan")


class NoticeReadReceipt(Base):
    """Track which users have read which notices"""
    __tablename__ = "notice_read_receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notice_id = Column(UUID(as_uuid=True), ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Tracking
    read_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)

    # Relationships
    notice = relationship("Notice", back_populates="read_receipts")
    user = relationship("User")
