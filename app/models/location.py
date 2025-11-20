from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base
import uuid

class Location(Base):
    """
    Location model for managing physical locations where services are provided
    """
    __tablename__ = "locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Location details
    name = Column(String(255), nullable=False, comment="Location name")
    address = Column(Text, nullable=True, comment="Street address")
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    country = Column(String(100), default="USA", nullable=False)

    # Contact information
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)

    # Additional details
    location_type = Column(String(50), nullable=True, comment="Type of location (e.g., residential, office, clinic)")
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Geographic coordinates
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    organization = relationship("Organization")

    def __repr__(self):
        return f"<Location(id={self.id}, name={self.name})>"

    @property
    def full_address(self):
        """Return full formatted address"""
        parts = []
        if self.address:
            parts.append(self.address)
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.zip_code:
            parts.append(self.zip_code)
        return ", ".join(parts) if parts else "No address"
