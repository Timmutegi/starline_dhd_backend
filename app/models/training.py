"""
Training Course Models
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.core.database import Base


class CourseStatus(str, enum.Enum):
    """Training course status"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class CourseType(str, enum.Enum):
    """Training course type"""
    VIDEO = "video"
    DOCUMENT = "document"
    INTERACTIVE = "interactive"
    QUIZ = "quiz"


class ProgressStatus(str, enum.Enum):
    """Training progress status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TrainingCourse(Base):
    """Training Course model"""
    __tablename__ = "training_courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    course_type = Column(SQLEnum(CourseType), nullable=False, default=CourseType.VIDEO)
    duration_minutes = Column(Integer, nullable=True, comment="Estimated duration in minutes")

    # Content
    content_url = Column(String(500), nullable=True, comment="URL to video, document, or interactive content")
    content_text = Column(Text, nullable=True, comment="Text content for document courses")
    quiz_questions = Column(JSON, nullable=True, comment="Quiz questions if course_type is quiz")

    # Requirements
    is_required = Column(Boolean, default=False, comment="Is this course required for all staff")
    required_for_roles = Column(JSON, nullable=True, comment="List of role IDs that require this course")
    passing_score = Column(Integer, nullable=True, comment="Passing score percentage for quizzes")

    # Certification
    provides_certification = Column(Boolean, default=False)
    certification_valid_days = Column(Integer, nullable=True, comment="Days before certification expires")

    # Status
    status = Column(SQLEnum(CourseStatus), nullable=False, default=CourseStatus.ACTIVE)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    organization = relationship("Organization")
    progress_records = relationship("TrainingProgress", back_populates="course", cascade="all, delete-orphan")


class TrainingProgress(Base):
    """Training Progress tracking"""
    __tablename__ = "training_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Progress tracking
    status = Column(SQLEnum(ProgressStatus), nullable=False, default=ProgressStatus.NOT_STARTED)
    progress_percentage = Column(Integer, default=0, comment="Completion percentage 0-100")

    # Time tracking
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)

    # Quiz results (if applicable)
    quiz_score = Column(Integer, nullable=True, comment="Quiz score percentage")
    quiz_attempts = Column(Integer, default=0)
    passed = Column(Boolean, default=False)

    # Certification
    certification_issued_at = Column(DateTime, nullable=True)
    certification_expires_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)

    # Relationships
    course = relationship("TrainingCourse", back_populates="progress_records")
    user = relationship("User")
    organization = relationship("Organization")
