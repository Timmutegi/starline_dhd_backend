from sqlalchemy import Column, String, Date, DateTime, Text, ForeignKey, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum

class IncidentSeverityEnum(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentStatusEnum(enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REQUIRES_FOLLOW_UP = "requires_follow_up"

class IncidentTypeEnum(enum.Enum):
    FALL = "fall"
    MEDICATION_ERROR = "medication_error"
    INJURY = "injury"
    BEHAVIORAL = "behavioral"
    EMERGENCY = "emergency"
    PROPERTY_DAMAGE = "property_damage"
    OTHER = "other"

class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Incident details
    incident_type = Column(Enum(IncidentTypeEnum), nullable=False, index=True)
    description = Column(Text, nullable=False, comment="Detailed incident description")
    action_taken = Column(Text, nullable=False, comment="Action taken in response to incident")
    severity = Column(Enum(IncidentSeverityEnum), nullable=False, index=True)
    status = Column(Enum(IncidentStatusEnum), nullable=False, default=IncidentStatusEnum.PENDING, index=True)

    # Incident timing and location
    incident_date = Column(Date, nullable=False, index=True)
    incident_time = Column(String(20), nullable=False, comment="Time when incident occurred")
    location = Column(String(200), nullable=True, comment="Location where incident occurred")

    # Additional information
    witnesses = Column(Text, nullable=True, comment="Witnesses present during incident")
    follow_up_required = Column(Boolean, nullable=False, default=False)
    follow_up_notes = Column(Text, nullable=True, comment="Follow-up actions and notes")

    # File attachments
    attached_files = Column(JSONB, nullable=True, comment="Attached files metadata")

    # Additional metadata
    additional_data = Column(JSONB, nullable=True, comment="Additional metadata")

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    client = relationship("Client", back_populates="incident_reports")
    staff = relationship("User", foreign_keys=[staff_id])
    organization = relationship("Organization")

    def __repr__(self):
        return f"<IncidentReport(id={self.id}, type={self.incident_type}, severity={self.severity})>"