from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Enum, Integer, DECIMAL, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime, date
import uuid
import enum

class EmploymentStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"

class PayType(enum.Enum):
    HOURLY = "hourly"
    SALARY = "salary"
    CONTRACT = "contract"

class Staff(Base):
    __tablename__ = "staff"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # Staff-specific information
    employee_id = Column(String(50), unique=True, nullable=False)
    middle_name = Column(String(100), nullable=True)
    preferred_name = Column(String(100), nullable=True)
    mobile_phone = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    ssn_encrypted = Column(String(255), nullable=True)  # Encrypted SSN

    # Address information
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)

    # Employment details
    hire_date = Column(Date, nullable=False, default=date.today)
    termination_date = Column(Date, nullable=True)
    employment_status = Column(Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE, nullable=False)
    department = Column(String(100), nullable=True)
    job_title = Column(String(100), nullable=True)
    supervisor_id = Column(UUID(as_uuid=True), ForeignKey("staff.id"), nullable=True)

    # Compensation
    hourly_rate = Column(DECIMAL(10,2), nullable=True)
    salary = Column(DECIMAL(12,2), nullable=True)
    pay_type = Column(Enum(PayType), default=PayType.HOURLY, nullable=False)
    fte_percentage = Column(DECIMAL(5,2), default=100.00)  # Full-time equivalent percentage

    # Additional information
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="staff_profile")
    organization = relationship("Organization")
    supervisor = relationship("Staff", remote_side=[id], backref="supervised_staff")
    creator = relationship("User", foreign_keys=[created_by])

    # Related staff management entities
    emergency_contacts = relationship("StaffEmergencyContact", back_populates="staff", cascade="all, delete-orphan")
    background_checks = relationship("BackgroundCheck", back_populates="staff", cascade="all, delete-orphan")
    certifications = relationship("StaffCertification", back_populates="staff", cascade="all, delete-orphan")
    training_records = relationship("TrainingRecord", back_populates="staff", cascade="all, delete-orphan")
    skills = relationship("StaffSkill", back_populates="staff", cascade="all, delete-orphan")
    performance_reviews = relationship("PerformanceReview", back_populates="staff", cascade="all, delete-orphan")
    disciplinary_actions = relationship("DisciplinaryAction", back_populates="staff", cascade="all, delete-orphan")
    assignments = relationship("StaffAssignment", back_populates="staff", cascade="all, delete-orphan")
    time_off_requests = relationship("TimeOffRequest", back_populates="staff", cascade="all, delete-orphan")
    payroll_info = relationship("StaffPayroll", back_populates="staff", uselist=False, cascade="all, delete-orphan")

    @property
    def full_name(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}"
        return ""

    @property
    def display_name(self):
        if self.preferred_name:
            return f"{self.preferred_name} {self.user.last_name}"
        return self.full_name

class StaffEmergencyContact(Base):
    __tablename__ = "staff_emergency_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    contact_name = Column(String(255), nullable=False)
    contact_relationship = Column(String(100), nullable=False)
    phone_primary = Column(String(20), nullable=False)
    phone_secondary = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="emergency_contacts")

class BackgroundCheckType(enum.Enum):
    CRIMINAL = "criminal"
    REFERENCE = "reference"
    EDUCATION = "education"
    EMPLOYMENT = "employment"
    DRUG_SCREEN = "drug_screen"
    PHYSICAL = "physical"

class BackgroundCheckStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

class BackgroundCheckResult(enum.Enum):
    CLEAR = "clear"
    FLAG = "flag"
    FAIL = "fail"

class BackgroundCheck(Base):
    __tablename__ = "background_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    check_type = Column(Enum(BackgroundCheckType), nullable=False)
    provider = Column(String(255), nullable=True)
    requested_date = Column(Date, nullable=False, default=date.today)
    completed_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    status = Column(Enum(BackgroundCheckStatus), default=BackgroundCheckStatus.PENDING, nullable=False)
    result = Column(Enum(BackgroundCheckResult), nullable=True)
    notes = Column(Text, nullable=True)
    document_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="background_checks")

class CertificationStatus(enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING_RENEWAL = "pending_renewal"
    SUSPENDED = "suspended"

class StaffCertification(Base):
    __tablename__ = "staff_certifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    certification_type = Column(String(255), nullable=False)
    certification_name = Column(String(255), nullable=False)
    issuing_organization = Column(String(255), nullable=False)
    certification_number = Column(String(100), nullable=True)
    issue_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    renewal_required = Column(Boolean, default=True)
    renewal_period_months = Column(Integer, nullable=True)
    status = Column(Enum(CertificationStatus), default=CertificationStatus.ACTIVE, nullable=False)
    document_url = Column(Text, nullable=True)
    verification_url = Column(Text, nullable=True)
    reminder_days_before = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="certifications")

class TrainingProgram(Base):
    __tablename__ = "training_programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    program_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    is_mandatory = Column(Boolean, default=False)
    frequency_months = Column(Integer, nullable=True)
    duration_hours = Column(DECIMAL(5,2), nullable=True)
    delivery_method = Column(String(50), default="online")  # online, classroom, on_job, blended
    prerequisites = Column(Text, nullable=True)  # JSON string
    materials_url = Column(Text, nullable=True)
    test_required = Column(Boolean, default=False)
    passing_score = Column(DECIMAL(5,2), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    training_records = relationship("TrainingRecord", back_populates="training_program", cascade="all, delete-orphan")

class TrainingStatus(enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    EXEMPTED = "exempted"

class TrainingRecord(Base):
    __tablename__ = "training_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    training_program_id = Column(UUID(as_uuid=True), ForeignKey("training_programs.id", ondelete="CASCADE"), nullable=False)
    enrollment_date = Column(Date, nullable=False, default=date.today)
    start_date = Column(Date, nullable=True)
    completion_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(Enum(TrainingStatus), default=TrainingStatus.NOT_STARTED, nullable=False)
    score = Column(DECIMAL(5,2), nullable=True)
    attempts = Column(Integer, default=0)
    instructor = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    certificate_url = Column(Text, nullable=True)
    next_due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="training_records")
    training_program = relationship("TrainingProgram", back_populates="training_records")

class ProficiencyLevel(enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class StaffSkill(Base):
    __tablename__ = "staff_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    skill_name = Column(String(255), nullable=False)
    skill_category = Column(String(100), nullable=True)
    proficiency_level = Column(Enum(ProficiencyLevel), nullable=False)
    validated = Column(Boolean, default=False)
    validated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    validated_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="skills")
    validator = relationship("User", foreign_keys=[validated_by])

class ReviewType(enum.Enum):
    ANNUAL = "annual"
    PROBATIONARY = "probationary"
    NINETY_DAY = "90_day"
    SPECIAL = "special"

class ReviewStatus(enum.Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    ACKNOWLEDGED = "acknowledged"

class PerformanceReview(Base):
    __tablename__ = "performance_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    review_period_start = Column(Date, nullable=False)
    review_period_end = Column(Date, nullable=False)
    review_type = Column(Enum(ReviewType), nullable=False)
    overall_rating = Column(DECIMAL(3,2), nullable=True)
    goals_met = Column(Boolean, nullable=True)
    strengths = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    goals_next_period = Column(Text, nullable=True)
    development_plan = Column(Text, nullable=True)
    employee_comments = Column(Text, nullable=True)
    status = Column(Enum(ReviewStatus), default=ReviewStatus.DRAFT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    acknowledged_date = Column(DateTime, nullable=True)

    staff = relationship("Staff", back_populates="performance_reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])

class DisciplinaryActionType(enum.Enum):
    VERBAL_WARNING = "verbal_warning"
    WRITTEN_WARNING = "written_warning"
    SUSPENSION = "suspension"
    TERMINATION = "termination"
    COACHING = "coaching"

class DisciplinaryAction(Base):
    __tablename__ = "disciplinary_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(Enum(DisciplinaryActionType), nullable=False)
    reason = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    action_date = Column(Date, nullable=False, default=date.today)
    issued_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    hr_reviewed = Column(Boolean, default=False)
    hr_reviewer = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    hr_review_date = Column(Date, nullable=True)
    employee_acknowledged = Column(Boolean, default=False)
    employee_ack_date = Column(Date, nullable=True)
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(Date, nullable=True)
    document_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="disciplinary_actions")
    issuer = relationship("User", foreign_keys=[issued_by])
    hr_reviewer_user = relationship("User", foreign_keys=[hr_reviewer])

class AssignmentType(enum.Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    BACKUP = "backup"
    RELIEF = "relief"

class StaffAssignment(Base):
    __tablename__ = "staff_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    location_id = Column(UUID(as_uuid=True), nullable=True)  # Future location table
    assignment_type = Column(Enum(AssignmentType), default=AssignmentType.PRIMARY, nullable=False)
    start_date = Column(Date, nullable=False, default=date.today)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="assignments")
    # client = relationship("Client")  # Uncomment when Client model is available

class TimeOffType(enum.Enum):
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    FMLA = "fmla"

class TimeOffStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"

class TimeOffRequest(Base):
    __tablename__ = "time_off_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    request_type = Column(Enum(TimeOffType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_hours = Column(DECIMAL(5,2), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(TimeOffStatus), default=TimeOffStatus.PENDING, nullable=False)
    requested_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_date = Column(DateTime, nullable=True)
    denial_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="time_off_requests")
    approver = relationship("User", foreign_keys=[approved_by])

class StaffPayroll(Base):
    __tablename__ = "staff_payroll"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    tax_id = Column(String(20), nullable=True)
    bank_account_encrypted = Column(String(255), nullable=True)
    routing_number_encrypted = Column(String(255), nullable=True)
    direct_deposit = Column(Boolean, default=False)
    tax_withholdings = Column(Text, nullable=True)  # JSON string
    deductions = Column(Text, nullable=True)  # JSON string
    benefits = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff", back_populates="payroll_info")