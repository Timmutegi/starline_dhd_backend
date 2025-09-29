from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.audit_mixins import PHIAuditMixin
import uuid

class VitalsLog(PHIAuditMixin, Base):
    __tablename__ = "vitals_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Vital signs
    temperature = Column(Float, nullable=True, comment="Temperature in Fahrenheit")
    blood_pressure_systolic = Column(Integer, nullable=True, comment="Systolic blood pressure")
    blood_pressure_diastolic = Column(Integer, nullable=True, comment="Diastolic blood pressure")
    blood_sugar = Column(Float, nullable=True, comment="Blood sugar level")
    weight = Column(Float, nullable=True, comment="Weight in pounds")
    heart_rate = Column(Integer, nullable=True, comment="Heart rate in BPM")
    oxygen_saturation = Column(Float, nullable=True, comment="Oxygen saturation percentage")

    # Additional information
    notes = Column(Text, nullable=True, comment="Additional notes about vitals")
    additional_data = Column(JSONB, nullable=True, comment="Additional metadata")

    # Timestamps
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="vitals_logs")
    staff = relationship("User", foreign_keys=[staff_id])
    organization = relationship("Organization")

    def __repr__(self):
        return f"<VitalsLog(id={self.id}, client_id={self.client_id}, recorded_at={self.recorded_at})>"

    # Audit configuration
    __audit_resource_type__ = "vitals"
    __audit_phi_fields__ = [
        "temperature", "blood_pressure_systolic", "blood_pressure_diastolic",
        "blood_sugar", "weight", "heart_rate", "oxygen_saturation", "notes"
    ]
    __audit_exclude_fields__ = ["created_at", "updated_at"]