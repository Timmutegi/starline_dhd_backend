from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.audit_mixins import PHIAuditMixin
import uuid

class BowelMovementLog(PHIAuditMixin, Base):
    __tablename__ = "bowel_movement_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Bowel Movement Data
    stool_type = Column(String, nullable=False, comment="Stool type (Type 1 - Type 7)")
    stool_color = Column(String, nullable=True, comment="Color of the stool")
    additional_information = Column(Text, nullable=True, comment="Additional observations")

    # Timestamps
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="bowel_movement_logs")
    staff = relationship("User", foreign_keys=[staff_id])
    organization = relationship("Organization")

    def __repr__(self):
        return f"<BowelMovementLog(id={self.id}, client_id={self.client_id}, recorded_at={self.recorded_at})>"

    # Audit configuration
    __audit_resource_type__ = "bowel_movement"
    __audit_phi_fields__ = ["stool_type", "stool_color", "additional_information"]
    __audit_exclude_fields__ = ["created_at", "updated_at"]
