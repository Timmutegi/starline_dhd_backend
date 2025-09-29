from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from app.models.staff import (
    EmploymentStatus,
    PayType,
    BackgroundCheckType,
    BackgroundCheckStatus,
    BackgroundCheckResult,
    CertificationStatus,
    TrainingStatus,
    ProficiencyLevel,
    ReviewType,
    ReviewStatus,
    DisciplinaryActionType,
    AssignmentType,
    TimeOffType,
    TimeOffStatus
)

# Base schemas
class StaffBase(BaseModel):
    employee_id: str
    middle_name: Optional[str] = None
    preferred_name: Optional[str] = None
    mobile_phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    hire_date: date
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE
    department: Optional[str] = None
    job_title: Optional[str] = None
    supervisor_id: Optional[UUID] = None
    hourly_rate: Optional[Decimal] = None
    salary: Optional[Decimal] = None
    pay_type: PayType = PayType.HOURLY
    fte_percentage: Decimal = Decimal('100.00')
    notes: Optional[str] = None

class StaffCreate(StaffBase):
    # User information for account creation
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    role_id: UUID

    @validator('employee_id')
    def validate_employee_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Employee ID is required')
        return v.strip()

class StaffUpdate(BaseModel):
    middle_name: Optional[str] = None
    preferred_name: Optional[str] = None
    mobile_phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    employment_status: Optional[EmploymentStatus] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    supervisor_id: Optional[UUID] = None
    hourly_rate: Optional[Decimal] = None
    salary: Optional[Decimal] = None
    pay_type: Optional[PayType] = None
    fte_percentage: Optional[Decimal] = None
    notes: Optional[str] = None

class UserInfo(BaseModel):
    id: UUID
    email: str
    username: Optional[str]
    first_name: str
    last_name: str
    phone: Optional[str]
    profile_picture_url: Optional[str]
    status: str
    last_login: Optional[datetime]
    email_verified: bool
    must_change_password: bool

    class Config:
        from_attributes = True

class StaffResponse(StaffBase):
    id: UUID
    user_id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime
    user: UserInfo
    full_name: str
    display_name: str

    class Config:
        from_attributes = True

class StaffCreateResponse(BaseModel):
    staff: StaffResponse
    temporary_password: str
    message: str
    success: bool

# Emergency Contact schemas
class EmergencyContactBase(BaseModel):
    contact_name: str
    contact_relationship: str
    phone_primary: str
    phone_secondary: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_primary: bool = False

class EmergencyContactCreate(EmergencyContactBase):
    pass

class EmergencyContactUpdate(BaseModel):
    contact_name: Optional[str] = None
    contact_relationship: Optional[str] = None
    phone_primary: Optional[str] = None
    phone_secondary: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_primary: Optional[bool] = None

class EmergencyContactResponse(EmergencyContactBase):
    id: UUID
    staff_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Background Check schemas
class BackgroundCheckBase(BaseModel):
    check_type: BackgroundCheckType
    provider: Optional[str] = None
    requested_date: date
    completed_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: BackgroundCheckStatus = BackgroundCheckStatus.PENDING
    result: Optional[BackgroundCheckResult] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None

class BackgroundCheckCreate(BaseModel):
    check_type: BackgroundCheckType
    provider: Optional[str] = None
    notes: Optional[str] = None

class BackgroundCheckUpdate(BaseModel):
    provider: Optional[str] = None
    completed_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: Optional[BackgroundCheckStatus] = None
    result: Optional[BackgroundCheckResult] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None

class BackgroundCheckResponse(BackgroundCheckBase):
    id: UUID
    staff_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Certification schemas
class CertificationBase(BaseModel):
    certification_type: str
    certification_name: str
    issuing_organization: str
    certification_number: Optional[str] = None
    issue_date: date
    expiry_date: Optional[date] = None
    renewal_required: bool = True
    renewal_period_months: Optional[int] = None
    status: CertificationStatus = CertificationStatus.ACTIVE
    document_url: Optional[str] = None
    verification_url: Optional[str] = None
    reminder_days_before: int = 30

class CertificationCreate(CertificationBase):
    pass

class CertificationUpdate(BaseModel):
    certification_type: Optional[str] = None
    certification_name: Optional[str] = None
    issuing_organization: Optional[str] = None
    certification_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    renewal_required: Optional[bool] = None
    renewal_period_months: Optional[int] = None
    status: Optional[CertificationStatus] = None
    document_url: Optional[str] = None
    verification_url: Optional[str] = None
    reminder_days_before: Optional[int] = None

class CertificationResponse(CertificationBase):
    id: UUID
    staff_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Training Program schemas
class TrainingProgramBase(BaseModel):
    program_name: str
    description: Optional[str] = None
    category: Optional[str] = None
    is_mandatory: bool = False
    frequency_months: Optional[int] = None
    duration_hours: Optional[Decimal] = None
    delivery_method: str = "online"
    prerequisites: Optional[str] = None
    materials_url: Optional[str] = None
    test_required: bool = False
    passing_score: Optional[Decimal] = None
    is_active: bool = True

class TrainingProgramCreate(TrainingProgramBase):
    pass

class TrainingProgramUpdate(BaseModel):
    program_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_mandatory: Optional[bool] = None
    frequency_months: Optional[int] = None
    duration_hours: Optional[Decimal] = None
    delivery_method: Optional[str] = None
    prerequisites: Optional[str] = None
    materials_url: Optional[str] = None
    test_required: Optional[bool] = None
    passing_score: Optional[Decimal] = None
    is_active: Optional[bool] = None

class TrainingProgramResponse(TrainingProgramBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Training Record schemas
class TrainingRecordBase(BaseModel):
    enrollment_date: date
    start_date: Optional[date] = None
    completion_date: Optional[date] = None
    due_date: Optional[date] = None
    status: TrainingStatus = TrainingStatus.NOT_STARTED
    score: Optional[Decimal] = None
    attempts: int = 0
    instructor: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    certificate_url: Optional[str] = None
    next_due_date: Optional[date] = None

class TrainingRecordCreate(BaseModel):
    training_program_id: UUID
    due_date: Optional[date] = None

class TrainingRecordUpdate(BaseModel):
    start_date: Optional[date] = None
    completion_date: Optional[date] = None
    due_date: Optional[date] = None
    status: Optional[TrainingStatus] = None
    score: Optional[Decimal] = None
    attempts: Optional[int] = None
    instructor: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    certificate_url: Optional[str] = None
    next_due_date: Optional[date] = None

class TrainingRecordResponse(TrainingRecordBase):
    id: UUID
    staff_id: UUID
    training_program_id: UUID
    training_program: TrainingProgramResponse
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Skill schemas
class SkillBase(BaseModel):
    skill_name: str
    skill_category: Optional[str] = None
    proficiency_level: ProficiencyLevel
    validated: bool = False
    validated_date: Optional[date] = None
    expiry_date: Optional[date] = None

class SkillCreate(SkillBase):
    pass

class SkillUpdate(BaseModel):
    skill_name: Optional[str] = None
    skill_category: Optional[str] = None
    proficiency_level: Optional[ProficiencyLevel] = None
    expiry_date: Optional[date] = None

class SkillValidate(BaseModel):
    validated: bool = True

class SkillResponse(SkillBase):
    id: UUID
    staff_id: UUID
    validated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Performance Review schemas
class PerformanceReviewBase(BaseModel):
    review_period_start: date
    review_period_end: date
    review_type: ReviewType
    overall_rating: Optional[Decimal] = None
    goals_met: Optional[bool] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    goals_next_period: Optional[str] = None
    development_plan: Optional[str] = None
    employee_comments: Optional[str] = None
    status: ReviewStatus = ReviewStatus.DRAFT

class PerformanceReviewCreate(PerformanceReviewBase):
    pass

class PerformanceReviewUpdate(BaseModel):
    review_period_start: Optional[date] = None
    review_period_end: Optional[date] = None
    review_type: Optional[ReviewType] = None
    overall_rating: Optional[Decimal] = None
    goals_met: Optional[bool] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    goals_next_period: Optional[str] = None
    development_plan: Optional[str] = None
    employee_comments: Optional[str] = None
    status: Optional[ReviewStatus] = None

class PerformanceReviewResponse(PerformanceReviewBase):
    id: UUID
    staff_id: UUID
    reviewer_id: UUID
    acknowledged_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Time Off Request schemas
class TimeOffRequestBase(BaseModel):
    request_type: TimeOffType
    start_date: date
    end_date: date
    total_hours: Decimal
    reason: Optional[str] = None
    status: TimeOffStatus = TimeOffStatus.PENDING

class TimeOffRequestCreate(BaseModel):
    request_type: TimeOffType
    start_date: date
    end_date: date
    total_hours: Decimal
    reason: Optional[str] = None

class TimeOffRequestUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_hours: Optional[Decimal] = None
    reason: Optional[str] = None

class TimeOffApproval(BaseModel):
    status: TimeOffStatus
    denial_reason: Optional[str] = None

class TimeOffRequestResponse(TimeOffRequestBase):
    id: UUID
    staff_id: UUID
    requested_date: datetime
    approved_by: Optional[UUID] = None
    approved_date: Optional[datetime] = None
    denial_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Assignment schemas
class AssignmentBase(BaseModel):
    client_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    assignment_type: AssignmentType = AssignmentType.PRIMARY
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True
    notes: Optional[str] = None

class AssignmentCreate(AssignmentBase):
    pass

class AssignmentUpdate(BaseModel):
    client_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    assignment_type: Optional[AssignmentType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class AssignmentResponse(AssignmentBase):
    id: UUID
    staff_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Summary schemas for dashboard/overview
class StaffSummary(BaseModel):
    id: UUID
    employee_id: str
    full_name: str
    display_name: str
    email: str
    job_title: Optional[str]
    department: Optional[str]
    employment_status: EmploymentStatus
    hire_date: date
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

class StaffListResponse(BaseModel):
    staff: List[StaffSummary]
    total: int
    page: int
    size: int
    pages: int