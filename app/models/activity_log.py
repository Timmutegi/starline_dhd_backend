from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class ActivityTypeEnum(str, enum.Enum):
    RECREATION = "recreation"
    EXERCISE = "exercise"
    SOCIAL = "social"
    EDUCATIONAL = "educational"
    VOCATIONAL = "vocational"
    THERAPEUTIC = "therapeutic"
    COMMUNITY = "community"
    PERSONAL_CARE = "personal_care"
    OTHER = "other"


class ParticipationLevelEnum(str, enum.Enum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    REFUSED = "refused"
    UNABLE = "unable"


class MoodEnum(str, enum.Enum):
    HAPPY = "happy"
    CONTENT = "content"
    NEUTRAL = "neutral"
    ANXIOUS = "anxious"
    IRRITABLE = "irritable"
    SAD = "sad"
    ANGRY = "angry"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Activity details
    activity_type = Column(SQLEnum(ActivityTypeEnum), nullable=False)
    activity_name = Column(String(200), nullable=False)
    activity_description = Column(Text, nullable=True)

    # Schedule
    activity_date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    start_time = Column(String(10), nullable=True)  # e.g., "10:00 AM"
    end_time = Column(String(10), nullable=True)  # e.g., "11:30 AM"
    duration_minutes = Column(Integer, nullable=True)

    # Location
    location = Column(String(200), nullable=True)
    location_type = Column(String(50), nullable=True)  # indoor, outdoor, community, facility

    # Participation
    participation_level = Column(SQLEnum(ParticipationLevelEnum), nullable=True)
    independence_level = Column(String(50), nullable=True)  # independent, supervised, assisted, dependent
    assistance_required = Column(Boolean, default=False)
    assistance_details = Column(Text, nullable=True)

    # Social interaction
    participants = Column(JSONB, nullable=True)  # Array of other participants
    peer_interaction = Column(Boolean, default=False)
    peer_interaction_quality = Column(String(50), nullable=True)  # positive, neutral, negative

    # Behavior and mood
    mood_before = Column(SQLEnum(MoodEnum), nullable=True)
    mood_during = Column(SQLEnum(MoodEnum), nullable=True)
    mood_after = Column(SQLEnum(MoodEnum), nullable=True)
    behavior_observations = Column(Text, nullable=True)
    challenging_behaviors = Column(Text, nullable=True)

    # Skills development
    skills_practiced = Column(JSONB, nullable=True)  # Array of skills
    skills_progress = Column(Text, nullable=True)
    goals_addressed = Column(JSONB, nullable=True)  # Related care plan goals

    # Engagement
    engagement_level = Column(String(50), nullable=True)  # high, moderate, low
    enjoyment_level = Column(String(50), nullable=True)  # enjoyed, tolerated, disliked
    focus_attention = Column(String(50), nullable=True)  # focused, distracted, unable

    # Physical health observations
    physical_complaints = Column(Text, nullable=True)
    fatigue_level = Column(String(50), nullable=True)  # energetic, normal, tired, exhausted
    injuries_incidents = Column(Text, nullable=True)

    # Outcomes and notes
    activity_completed = Column(Boolean, default=True)
    completion_percentage = Column(Integer, nullable=True)  # 0-100
    achievements = Column(Text, nullable=True)
    challenges_faced = Column(Text, nullable=True)
    staff_notes = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    follow_up_needed = Column(Boolean, default=False)

    # Media
    photo_urls = Column(JSONB, nullable=True)  # Array of photo URLs
    video_urls = Column(JSONB, nullable=True)  # Array of video URLs

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = relationship("Client")
    staff = relationship("User")
    organization = relationship("Organization")
