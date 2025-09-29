from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Enum, Integer, DECIMAL, Date, Time, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime, date, time
import uuid
import enum

class ScheduleType(enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class ScheduleStatus(enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    LOCKED = "locked"
    ARCHIVED = "archived"

class ShiftStatus(enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class ShiftType(enum.Enum):
    REGULAR = "regular"
    OVERTIME = "overtime"
    HOLIDAY = "holiday"
    ON_CALL = "on_call"
    SPLIT = "split"

class AssignmentType(enum.Enum):
    PRIMARY = "primary"
    BACKUP = "backup"
    RELIEF = "relief"

class AvailabilityType(enum.Enum):
    AVAILABLE = "available"
    PREFERRED = "preferred"
    UNAVAILABLE = "unavailable"

class TimeOffType(enum.Enum):
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    FMLA = "fmla"

class RequestType(enum.Enum):
    SWAP = "swap"
    PICKUP = "pickup"
    DROP = "drop"

class RequestStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"

class SwapStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class AppointmentType(enum.Enum):
    MEDICAL = "medical"
    THERAPY = "therapy"
    SOCIAL = "social"
    LEGAL = "legal"
    FAMILY_VISIT = "family_visit"
    OUTING = "outing"

class AppointmentStatus(enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class RecurrencePattern(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class TimeEntryType(enum.Enum):
    CLOCK_IN = "clock_in"
    CLOCK_OUT = "clock_out"
    BREAK_START = "break_start"
    BREAK_END = "break_end"
    MEAL_START = "meal_start"
    MEAL_END = "meal_end"

class ConflictType(enum.Enum):
    DOUBLE_BOOKING = "double_booking"
    OVERTIME_VIOLATION = "overtime_violation"
    AVAILABILITY_CONFLICT = "availability_conflict"
    SKILL_MISMATCH = "skill_mismatch"

class ConflictSeverity(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class EventType(enum.Enum):
    MEETING = "meeting"
    TRAINING = "training"
    HOLIDAY = "holiday"
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    OTHER = "other"

class EventVisibility(enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"


class ShiftTemplate(Base):
    __tablename__ = "shift_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    template_name = Column(String(255), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    break_duration_minutes = Column(Integer, default=0)
    meal_break_minutes = Column(Integer, default=0)
    days_of_week = Column(ARRAY(Integer), nullable=False)  # [1,2,3,4,5] for Mon-Fri
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    schedule_name = Column(String(255), nullable=False)
    schedule_type = Column(Enum(ScheduleType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(Enum(ScheduleStatus), default=ScheduleStatus.DRAFT, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])
    shifts = relationship("Shift", back_populates="schedule", cascade="all, delete-orphan")


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(UUID(as_uuid=True), nullable=True)  # Future location table
    shift_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    break_start = Column(Time, nullable=True)
    break_end = Column(Time, nullable=True)
    meal_start = Column(Time, nullable=True)
    meal_end = Column(Time, nullable=True)
    status = Column(Enum(ShiftStatus), default=ShiftStatus.SCHEDULED, nullable=False)
    shift_type = Column(Enum(ShiftType), default=ShiftType.REGULAR, nullable=False)
    is_mandatory = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schedule = relationship("Schedule", back_populates="shifts")
    staff = relationship("Staff")
    assignments = relationship("ShiftAssignment", back_populates="shift", cascade="all, delete-orphan")
    time_entries = relationship("TimeClockEntry", back_populates="shift", cascade="all, delete-orphan")


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    assignment_type = Column(Enum(AssignmentType), default=AssignmentType.PRIMARY, nullable=False)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    services_provided = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shift = relationship("Shift", back_populates="assignments")
    client = relationship("Client")


class StaffAvailability(Base):
    __tablename__ = "staff_availability"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Sunday, 6=Saturday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    availability_type = Column(Enum(AvailabilityType), default=AvailabilityType.AVAILABLE, nullable=False)
    effective_date = Column(Date, nullable=False, default=date.today)
    expiry_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff")


class TimeOffScheduling(Base):
    __tablename__ = "time_off_scheduling"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    time_off_type = Column(Enum(TimeOffType), nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    affects_scheduling = Column(Boolean, default=True)
    replacement_required = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    staff = relationship("Staff")


class CoverageRequest(Base):
    __tablename__ = "coverage_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False)
    requesting_staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=False)
    request_type = Column(Enum(RequestType), nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at = Column(DateTime, nullable=True)
    responded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    original_shift = relationship("Shift", foreign_keys=[original_shift_id])
    requesting_staff = relationship("Staff", foreign_keys=[requesting_staff_id])
    responder = relationship("User", foreign_keys=[responded_by])


class ShiftSwap(Base):
    __tablename__ = "shift_swaps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coverage_request_id = Column(UUID(as_uuid=True), ForeignKey("coverage_requests.id", ondelete="CASCADE"), nullable=False)
    shift_a_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False)
    shift_b_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False)
    staff_a_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    staff_b_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    swap_date = Column(Date, nullable=False)
    status = Column(Enum(SwapStatus), default=SwapStatus.PENDING, nullable=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    coverage_request = relationship("CoverageRequest")
    shift_a = relationship("Shift", foreign_keys=[shift_a_id])
    shift_b = relationship("Shift", foreign_keys=[shift_b_id])
    staff_a = relationship("Staff", foreign_keys=[staff_a_id])
    staff_b = relationship("Staff", foreign_keys=[staff_b_id])
    approver = relationship("User", foreign_keys=[approved_by])


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    appointment_type = Column(Enum(AppointmentType), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED, nullable=False)
    requires_transport = Column(Boolean, default=False)
    transport_staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id"), nullable=True)
    reminder_sent = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    client = relationship("Client")
    staff = relationship("Staff", foreign_keys=[staff_id])
    transport_staff = relationship("Staff", foreign_keys=[transport_staff_id])


class RecurringAppointment(Base):
    __tablename__ = "recurring_appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    appointment_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    start_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    recurrence_pattern = Column(Enum(RecurrencePattern), nullable=False)
    recurrence_days = Column(ARRAY(Integer), nullable=True)  # for weekly: [1,3,5]
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    max_occurrences = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    client = relationship("Client")
    staff = relationship("Staff")


class TimeClockEntry(Base):
    __tablename__ = "time_clock_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=True)
    entry_type = Column(Enum(TimeEntryType), nullable=False)
    entry_datetime = Column(DateTime, nullable=False)
    location_verified = Column(Boolean, default=False)
    geolocation = Column(String(100), nullable=True)  # Storing as string for simplicity
    ip_address = Column(String(45), nullable=True)
    device_info = Column(JSONB, nullable=True)
    photo_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    staff = relationship("Staff")
    shift = relationship("Shift", back_populates="time_entries")


class OvertimeTracking(Base):
    __tablename__ = "overtime_tracking"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=True)
    week_start_date = Column(Date, nullable=False)
    regular_hours = Column(DECIMAL(5,2), nullable=False, default=0.00)
    overtime_hours = Column(DECIMAL(5,2), nullable=False, default=0.00)
    double_time_hours = Column(DECIMAL(5,2), nullable=False, default=0.00)
    holiday_hours = Column(DECIMAL(5,2), nullable=False, default=0.00)
    total_hours = Column(DECIMAL(5,2), nullable=False, default=0.00)
    approved = Column(Boolean, default=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    staff = relationship("Staff")
    shift = relationship("Shift")
    approver = relationship("User", foreign_keys=[approved_by])


class ScheduleConflict(Base):
    __tablename__ = "schedule_conflicts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conflict_type = Column(Enum(ConflictType), nullable=False)
    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=True)
    staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    conflict_description = Column(Text, nullable=False)
    severity = Column(Enum(ConflictSeverity), nullable=False)
    resolved = Column(Boolean, default=False)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shift = relationship("Shift")
    staff = relationship("Staff")
    resolver = relationship("User", foreign_keys=[resolved_by])


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Enum(EventType), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    location = Column(Text, nullable=True)
    all_day = Column(Boolean, default=False)
    is_recurring = Column(Boolean, default=False)
    recurrence_rule = Column(Text, nullable=True)
    attendees = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # staff IDs
    color = Column(String(7), default="#4F46E5")
    visibility = Column(Enum(EventVisibility), default=EventVisibility.PUBLIC, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    creator = relationship("User", foreign_keys=[created_by])