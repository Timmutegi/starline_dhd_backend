"""
Training Course Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.training import CourseType, CourseStatus, ProgressStatus


# Training Course Schemas
class TrainingCourseBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    course_type: CourseType
    duration_minutes: Optional[int] = Field(None, ge=0)
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    quiz_questions: Optional[List[Dict[str, Any]]] = None
    is_required: bool = False
    required_for_roles: Optional[List[str]] = None
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    provides_certification: bool = False
    certification_valid_days: Optional[int] = Field(None, ge=0)


class TrainingCourseCreate(TrainingCourseBase):
    pass


class TrainingCourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    course_type: Optional[CourseType] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    quiz_questions: Optional[List[Dict[str, Any]]] = None
    is_required: Optional[bool] = None
    required_for_roles: Optional[List[str]] = None
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    provides_certification: Optional[bool] = None
    certification_valid_days: Optional[int] = Field(None, ge=0)
    status: Optional[CourseStatus] = None


class TrainingCourseResponse(TrainingCourseBase):
    id: str
    organization_id: str
    status: CourseStatus
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


# Training Progress Schemas
class TrainingProgressBase(BaseModel):
    course_id: str
    progress_percentage: Optional[int] = Field(0, ge=0, le=100)


class TrainingProgressCreate(TrainingProgressBase):
    pass


class TrainingProgressUpdate(BaseModel):
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    status: Optional[ProgressStatus] = None
    quiz_score: Optional[int] = Field(None, ge=0, le=100)


class TrainingProgressResponse(BaseModel):
    id: str
    course_id: str
    user_id: str
    organization_id: str
    status: ProgressStatus
    progress_percentage: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_accessed_at: Optional[datetime]
    quiz_score: Optional[int]
    quiz_attempts: int
    passed: bool
    certification_issued_at: Optional[datetime]
    certification_expires_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourseWithProgress(BaseModel):
    """Course with user's progress"""
    course: TrainingCourseResponse
    progress: Optional[TrainingProgressResponse] = None


class MarkCourseComplete(BaseModel):
    """Mark a course as complete"""
    quiz_score: Optional[int] = Field(None, ge=0, le=100)


class CoursesList(BaseModel):
    """List of courses with pagination"""
    courses: List[CourseWithProgress]
    total: int
    page: int
    page_size: int
