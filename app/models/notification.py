from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum

class NotificationTypeEnum(enum.Enum):
    CRITICAL = "critical"
    REMINDER = "reminder"
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"

class NotificationCategoryEnum(enum.Enum):
    MEDICATION = "medication"
    APPOINTMENT = "appointment"
    TASK = "task"
    INCIDENT = "incident"
    SCHEDULE = "schedule"
    SYSTEM = "system"
    GENERAL = "general"

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Notification content
    title = Column(String(200), nullable=False, comment="Notification title")
    message = Column(Text, nullable=False, comment="Notification message")
    type = Column(Enum(NotificationTypeEnum), nullable=False, default=NotificationTypeEnum.INFO, index=True)
    category = Column(Enum(NotificationCategoryEnum), nullable=False, default=NotificationCategoryEnum.GENERAL, index=True)

    # Status and interaction
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Optional action/link
    action_url = Column(String(500), nullable=True, comment="URL for notification action")
    action_text = Column(String(100), nullable=True, comment="Text for action button")

    # Related entities
    related_entity_type = Column(String(50), nullable=True, comment="Type of related entity (client, appointment, etc.)")
    related_entity_id = Column(UUID(as_uuid=True), nullable=True, comment="ID of related entity")

    # Additional metadata
    additional_data = Column(JSONB, nullable=True, comment="Additional notification metadata")

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, comment="When notification expires")

    # Relationships
    user = relationship("User", back_populates="notifications")
    organization = relationship("Organization")

    def __repr__(self):
        return f"<Notification(id={self.id}, type={self.type}, is_read={self.is_read})>"