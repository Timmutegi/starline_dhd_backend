from sqlalchemy import Column, String, Date, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class ShiftNote(Base):
    __tablename__ = "shift_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Shift information
    shift_date = Column(Date, nullable=False, index=True)
    shift_time = Column(String(50), nullable=False, comment="Shift time range")

    # Note content
    narrative = Column(Text, nullable=False, comment="Main narrative/observations")
    challenges_faced = Column(Text, nullable=True, comment="Challenges faced during shift")
    support_required = Column(Text, nullable=True, comment="Support required")
    observations = Column(Text, nullable=True, comment="Additional observations")

    # Additional metadata
    additional_data = Column(JSONB, nullable=True, comment="Additional metadata")

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="shift_notes")
    staff = relationship("User", foreign_keys=[staff_id])
    organization = relationship("Organization")

    def __repr__(self):
        return f"<ShiftNote(id={self.id}, client_id={self.client_id}, shift_date={self.shift_date})>"