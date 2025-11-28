from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Date, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.audit_mixins import PHIAuditMixin
import uuid

class SleepLog(PHIAuditMixin, Base):
    __tablename__ = "sleep_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Sleep Data
    shift_date = Column(Date, nullable=False, index=True, comment="Date of the shift")
    sleep_periods = Column(JSON, nullable=False, comment="Array of sleep blocks with start_time and end_time")
    total_sleep_minutes = Column(Integer, nullable=False, comment="Total minutes of sleep")
    notes = Column(Text, nullable=True, comment="Additional observations")

    # Timestamps
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="sleep_logs")
    staff = relationship("User", foreign_keys=[staff_id])
    organization = relationship("Organization")

    def __repr__(self):
        return f"<SleepLog(id={self.id}, client_id={self.client_id}, shift_date={self.shift_date}, total_sleep_minutes={self.total_sleep_minutes})>"

    # Audit configuration
    __audit_resource_type__ = "sleep_log"
    __audit_phi_fields__ = ["sleep_periods", "notes"]
    __audit_exclude_fields__ = ["created_at", "updated_at"]
