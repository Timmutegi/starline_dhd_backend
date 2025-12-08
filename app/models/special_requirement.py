from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Date, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit_mixins import AuditMixin
from datetime import datetime, timezone
import uuid
import enum


class PriorityLevel(enum.Enum):
    """Priority level for special requirements"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequirementStatus(enum.Enum):
    """Status of special requirement"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    DRAFT = "draft"


class SpecialRequirement(AuditMixin, Base):
    """
    Manager-created special requirement for a specific client.
    Contains instructions and action plan items that DSPs must acknowledge during their shifts.

    A special requirement is time-bounded (start_date to end_date) and can have
    multiple action plan items that DSPs must check off.
    """
    __tablename__ = "special_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Requirement details
    title = Column(String(255), nullable=False)
    instructions = Column(Text, nullable=False)  # Detailed text instructions for DSP
    action_plan_items = Column(JSON, nullable=False, default=list)  # List of items: [{"id": "uuid", "text": "Action item text", "order": 1}, ...]

    # Time bounds - requirement is only active within this date range
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Priority and status
    priority = Column(SQLEnum(PriorityLevel), default=PriorityLevel.MEDIUM, nullable=False)
    status = Column(SQLEnum(RequirementStatus), default=RequirementStatus.ACTIVE, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id])
    client = relationship("Client", foreign_keys=[client_id], back_populates="special_requirements")
    creator = relationship("User", foreign_keys=[created_by])
    responses = relationship("SpecialRequirementResponse", back_populates="special_requirement", cascade="all, delete-orphan")

    # Audit configuration
    __audit_resource_type__ = "special_requirement"
    __audit_phi_fields__ = ["instructions", "action_plan_items"]
    __audit_exclude_fields__ = ["created_at", "updated_at"]

    def __repr__(self):
        return f"<SpecialRequirement(id={self.id}, title='{self.title}', client_id={self.client_id})>"


class SpecialRequirementResponse(AuditMixin, Base):
    """
    DSP's response/certification for a special requirement during a specific shift.

    Each shift requires fresh documentation - DSPs cannot reuse previous responses.
    The response includes acknowledgment of instructions, completion of action items,
    documentation of intervention, and legal certification.
    """
    __tablename__ = "special_requirement_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    special_requirement_id = Column(UUID(as_uuid=True), ForeignKey("special_requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True, index=True)

    # DSP's response - acknowledgment and action items
    instructions_acknowledged = Column(Boolean, default=False, nullable=False)  # DSP read and acknowledged instructions
    acknowledged_items = Column(JSON, nullable=False, default=list)  # List of acknowledged action item IDs: ["uuid1", "uuid2", ...]
    intervention_notes = Column(Text, nullable=True)  # What the DSP actually did in response

    # Legal certification for compliance
    is_certified = Column(Boolean, default=False, nullable=False)
    certification_statement = Column(Text, nullable=True)  # Auto-generated certification text
    certified_at = Column(DateTime, nullable=True)

    # Shift context for documentation
    shift_date = Column(Date, nullable=False)
    shift_start_time = Column(String(10), nullable=True)
    shift_end_time = Column(String(10), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id])
    special_requirement = relationship("SpecialRequirement", back_populates="responses")
    client = relationship("Client", foreign_keys=[client_id])
    staff = relationship("User", foreign_keys=[staff_id])
    shift = relationship("Shift", foreign_keys=[shift_id])

    # Audit configuration
    __audit_resource_type__ = "special_requirement_response"
    __audit_phi_fields__ = ["intervention_notes", "certification_statement"]
    __audit_exclude_fields__ = ["created_at", "updated_at"]

    def __repr__(self):
        return f"<SpecialRequirementResponse(id={self.id}, requirement_id={self.special_requirement_id}, staff_id={self.staff_id})>"
