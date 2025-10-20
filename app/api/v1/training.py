"""
Training Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.training import TrainingCourse, TrainingProgress, ProgressStatus, CourseStatus
from app.schemas.training import (
    TrainingCourseCreate,
    TrainingCourseUpdate,
    TrainingCourseResponse,
    TrainingProgressCreate,
    TrainingProgressUpdate,
    TrainingProgressResponse,
    CourseWithProgress,
    MarkCourseComplete,
    CoursesList
)

router = APIRouter()


def _serialize_course(course: TrainingCourse) -> TrainingCourseResponse:
    """Helper to serialize TrainingCourse to response"""
    return TrainingCourseResponse(
        id=str(course.id),
        organization_id=str(course.organization_id),
        title=course.title,
        description=course.description,
        course_type=course.course_type,
        duration_minutes=course.duration_minutes,
        content_url=course.content_url,
        content_text=course.content_text,
        quiz_questions=course.quiz_questions,
        is_required=course.is_required,
        required_for_roles=course.required_for_roles,
        passing_score=course.passing_score,
        provides_certification=course.provides_certification,
        certification_valid_days=course.certification_valid_days,
        status=course.status,
        created_at=course.created_at,
        updated_at=course.updated_at,
        created_by=str(course.created_by)
    )


def _serialize_progress(progress: TrainingProgress) -> TrainingProgressResponse:
    """Helper to serialize TrainingProgress to response"""
    return TrainingProgressResponse(
        id=str(progress.id),
        course_id=str(progress.course_id),
        user_id=str(progress.user_id),
        organization_id=str(progress.organization_id),
        status=progress.status.value,
        progress_percentage=progress.progress_percentage,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        last_accessed_at=progress.last_accessed_at,
        quiz_score=progress.quiz_score,
        quiz_attempts=progress.quiz_attempts,
        passed=progress.passed,
        certification_issued_at=progress.certification_issued_at,
        certification_expires_at=progress.certification_expires_at,
        created_at=progress.created_at,
        updated_at=progress.updated_at
    )


@router.get("/courses", response_model=CoursesList)
def get_training_courses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    required_only: bool = Query(False),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all training courses with user's progress"""

    # Build query
    query = db.query(TrainingCourse).filter(
        TrainingCourse.organization_id == current_user.organization_id
    )

    # Filter by status
    if status:
        query = query.filter(TrainingCourse.status == status)
    else:
        query = query.filter(TrainingCourse.status == CourseStatus.ACTIVE)

    # Filter by required courses only
    if required_only:
        query = query.filter(TrainingCourse.is_required == True)

    # Get total count
    total = query.count()

    # Pagination
    courses = query.offset((page - 1) * page_size).limit(page_size).all()

    # Get user's progress for these courses
    course_ids = [course.id for course in courses]
    progress_records = db.query(TrainingProgress).filter(
        TrainingProgress.user_id == str(current_user.id),
        TrainingProgress.course_id.in_(course_ids)
    ).all()

    # Create a map of course_id -> progress
    progress_map = {prog.course_id: prog for prog in progress_records}

    # Build response with course and progress
    courses_with_progress = []
    for course in courses:
        progress = progress_map.get(course.id)
        courses_with_progress.append(
            CourseWithProgress(
                course=_serialize_course(course),
                progress=_serialize_progress(progress) if progress else None
            )
        )

    return CoursesList(
        courses=courses_with_progress,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/progress", response_model=List[TrainingProgressResponse])
def get_my_training_progress(
    status: Optional[ProgressStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's training progress"""

    query = db.query(TrainingProgress).filter(
        TrainingProgress.user_id == str(current_user.id),
        TrainingProgress.organization_id == current_user.organization_id
    )

    if status:
        query = query.filter(TrainingProgress.status == status)

    progress_records = query.all()
    return [_serialize_progress(prog) for prog in progress_records]


@router.get("/required", response_model=CoursesList)
def get_required_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get required courses for current user"""

    # Get all required courses or courses required for user's role
    query = db.query(TrainingCourse).filter(
        TrainingCourse.organization_id == current_user.organization_id,
        TrainingCourse.status == CourseStatus.ACTIVE
    )

    # Filter to required courses
    query = query.filter(
        (TrainingCourse.is_required == True) |
        (TrainingCourse.required_for_roles.contains([str(current_user.role_id)]))
    )

    courses = query.all()

    # Get user's progress
    course_ids = [course.id for course in courses]
    progress_records = db.query(TrainingProgress).filter(
        TrainingProgress.user_id == str(current_user.id),
        TrainingProgress.course_id.in_(course_ids)
    ).all()

    progress_map = {prog.course_id: prog for prog in progress_records}

    # Build response
    courses_with_progress = []
    for course in courses:
        progress = progress_map.get(course.id)
        courses_with_progress.append(
            CourseWithProgress(
                course=_serialize_course(course),
                progress=_serialize_progress(progress) if progress else None
            )
        )

    return CoursesList(
        courses=courses_with_progress,
        total=len(courses),
        page=1,
        page_size=len(courses)
    )


@router.post("/courses", response_model=TrainingCourseResponse)
def create_training_course(
    course_data: TrainingCourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new training course"""
    # Create course
    course = TrainingCourse(
        organization_id=current_user.organization_id,
        title=course_data.title,
        description=course_data.description,
        course_type=course_data.course_type,
        content_url=course_data.content_url,
        content_text=course_data.content_text,
        quiz_questions=course_data.quiz_questions,
        duration_minutes=course_data.duration_minutes,
        passing_score=course_data.passing_score,
        is_required=course_data.is_required,
        required_for_roles=course_data.required_for_roles,
        provides_certification=course_data.provides_certification,
        certification_valid_days=course_data.certification_valid_days,
        status=CourseStatus.ACTIVE,
        created_by=current_user.id
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    return TrainingCourseResponse(
        id=str(course.id),
        organization_id=str(course.organization_id),
        title=course.title,
        description=course.description,
        course_type=course.course_type,
        duration_minutes=course.duration_minutes,
        content_url=course.content_url,
        content_text=course.content_text,
        quiz_questions=course.quiz_questions,
        is_required=course.is_required,
        required_for_roles=course.required_for_roles,
        passing_score=course.passing_score,
        provides_certification=course.provides_certification,
        certification_valid_days=course.certification_valid_days,
        status=course.status,
        created_at=course.created_at,
        updated_at=course.updated_at,
        created_by=str(course.created_by)
    )


@router.post("/courses/{course_id}/start", response_model=TrainingProgressResponse)
def start_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a training course"""

    # Verify course exists
    course = db.query(TrainingCourse).filter(
        TrainingCourse.id == course_id,
        TrainingCourse.organization_id == current_user.organization_id
    ).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check if progress already exists
    progress = db.query(TrainingProgress).filter(
        TrainingProgress.course_id == course_id,
        TrainingProgress.user_id == str(current_user.id)
    ).first()

    if progress:
        # Update existing progress
        if progress.status == ProgressStatus.NOT_STARTED:
            progress.status = ProgressStatus.IN_PROGRESS
            progress.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
            progress.last_accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(progress)
    else:
        # Create new progress
        progress = TrainingProgress(
            course_id=course_id,
            user_id=str(current_user.id),
            organization_id=current_user.organization_id,
            status=ProgressStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            last_accessed_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    return TrainingProgressResponse(
        id=str(progress.id),
        course_id=str(progress.course_id),
        user_id=str(progress.user_id),
        organization_id=str(progress.organization_id),
        status=progress.status.value,
        progress_percentage=progress.progress_percentage,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        last_accessed_at=progress.last_accessed_at,
        quiz_score=progress.quiz_score,
        quiz_attempts=progress.quiz_attempts,
        passed=progress.passed,
        certification_issued_at=progress.certification_issued_at,
        certification_expires_at=progress.certification_expires_at,
        created_at=progress.created_at,
        updated_at=progress.updated_at
    )


@router.post("/courses/{course_id}/complete", response_model=TrainingProgressResponse)
def complete_course(
    course_id: str,
    data: MarkCourseComplete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a course as complete"""

    # Verify course exists
    course = db.query(TrainingCourse).filter(
        TrainingCourse.id == course_id,
        TrainingCourse.organization_id == current_user.organization_id
    ).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get or create progress
    progress = db.query(TrainingProgress).filter(
        TrainingProgress.course_id == course_id,
        TrainingProgress.user_id == str(current_user.id)
    ).first()

    if not progress:
        progress = TrainingProgress(
            course_id=course_id,
            user_id=str(current_user.id),
            organization_id=current_user.organization_id,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(progress)

    # Update progress to completed
    progress.status = ProgressStatus.COMPLETED
    progress.progress_percentage = 100
    progress.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    progress.last_accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Handle quiz score if provided
    if data.quiz_score is not None:
        progress.quiz_score = data.quiz_score
        progress.quiz_attempts += 1

        # Check if passed
        if course.passing_score:
            progress.passed = data.quiz_score >= course.passing_score
        else:
            progress.passed = True
    else:
        progress.passed = True

    # Handle certification if applicable
    if course.provides_certification and progress.passed:
        progress.certification_issued_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if course.certification_valid_days:
            from datetime import timedelta
            progress.certification_expires_at = (datetime.now(timezone.utc) + timedelta(days=course.certification_valid_days)).replace(tzinfo=None)

    db.commit()
    db.refresh(progress)

    return _serialize_progress(progress)


@router.put("/progress/{progress_id}", response_model=TrainingProgressResponse)
def update_training_progress(
    progress_id: str,
    data: TrainingProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update training progress"""

    progress = db.query(TrainingProgress).filter(
        TrainingProgress.id == progress_id,
        TrainingProgress.user_id == str(current_user.id)
    ).first()

    if not progress:
        raise HTTPException(status_code=404, detail="Progress record not found")

    # Update fields
    if data.progress_percentage is not None:
        progress.progress_percentage = data.progress_percentage

    if data.status:
        progress.status = data.status
        if data.status == ProgressStatus.IN_PROGRESS and not progress.started_at:
            progress.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        elif data.status == ProgressStatus.COMPLETED and not progress.completed_at:
            progress.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    if data.quiz_score is not None:
        progress.quiz_score = data.quiz_score
        progress.quiz_attempts += 1

    progress.last_accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(progress)

    return _serialize_progress(progress)
