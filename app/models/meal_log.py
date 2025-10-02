from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Float, Integer, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class MealTypeEnum(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class IntakeAmountEnum(str, enum.Enum):
    NONE = "none"
    MINIMAL = "minimal"
    PARTIAL = "partial"
    MOST = "most"
    ALL = "all"


class MealLog(Base):
    __tablename__ = "meal_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Meal details
    meal_type = Column(SQLEnum(MealTypeEnum), nullable=False)
    meal_date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    meal_time = Column(String(10), nullable=True)  # e.g., "08:30 AM"

    # Food items and intake
    food_items = Column(JSONB, nullable=True)  # Array of food items served
    intake_amount = Column(SQLEnum(IntakeAmountEnum), nullable=True)  # Overall intake
    percentage_consumed = Column(Integer, nullable=True)  # 0-100

    # Nutritional information (if tracked)
    calories = Column(Float, nullable=True)
    protein_grams = Column(Float, nullable=True)
    carbs_grams = Column(Float, nullable=True)
    fat_grams = Column(Float, nullable=True)

    # Hydration
    water_intake_ml = Column(Integer, nullable=True)
    other_fluids = Column(Text, nullable=True)

    # Observations
    appetite_level = Column(String(50), nullable=True)  # good, fair, poor
    dietary_preferences_followed = Column(Boolean, default=True)
    dietary_restrictions_followed = Column(Boolean, default=True)
    assistance_required = Column(Boolean, default=False)
    assistance_type = Column(Text, nullable=True)  # feeding, cutting, reminders, etc.

    # Issues and notes
    refusals = Column(Text, nullable=True)
    allergic_reactions = Column(Text, nullable=True)
    choking_incidents = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)

    # Photos
    photo_urls = Column(JSONB, nullable=True)  # Array of photo URLs

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = relationship("Client")
    staff = relationship("User")
    organization = relationship("Organization")
