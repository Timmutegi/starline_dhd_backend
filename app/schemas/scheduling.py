from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from uuid import UUID
from app.models.scheduling import (
    ScheduleType, ScheduleStatus, ShiftStatus, ShiftType, AssignmentType,
    AvailabilityType, TimeOffType, RequestType, RequestStatus, SwapStatus,
    AppointmentType, AppointmentStatus, RecurrencePattern, TimeEntryType,
    ConflictType, ConflictSeverity, EventType, EventVisibility
)


# Shift Template Schemas
class ShiftTemplateBase(BaseModel):
    template_name: str = Field(..., max_length=255)
    start_time: time
    end_time: time
    duration_minutes: int = Field(..., gt=0)
    break_duration_minutes: int = Field(0, ge=0)
    meal_break_minutes: int = Field(0, ge=0)
    days_of_week: List[int] = Field(..., min_items=1, max_items=7)
    is_active: bool = True

    @validator('days_of_week')
    def validate_days_of_week(cls, v):
        if not all(1 <= day <= 7 for day in v):
            raise ValueError('Days of week must be between 1 and 7')
        return v

    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v

class ShiftTemplateCreate(ShiftTemplateBase):
    organization_id: UUID

class ShiftTemplateUpdate(BaseModel):
    template_name: Optional[str] = Field(None, max_length=255)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    break_duration_minutes: Optional[int] = Field(None, ge=0)
    meal_break_minutes: Optional[int] = Field(None, ge=0)
    days_of_week: Optional[List[int]] = Field(None, min_items=1, max_items=7)
    is_active: Optional[bool] = None

class ShiftTemplateResponse(ShiftTemplateBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schedule Schemas
class ScheduleBase(BaseModel):
    schedule_name: str = Field(..., max_length=255)
    schedule_type: ScheduleType
    start_date: date
    end_date: date
    notes: Optional[str] = None

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v

class ScheduleCreate(ScheduleBase):
    organization_id: UUID

class ScheduleUpdate(BaseModel):
    schedule_name: Optional[str] = Field(None, max_length=255)
    schedule_type: Optional[ScheduleType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[ScheduleStatus] = None

class ScheduleResponse(ScheduleBase):
    id: UUID
    organization_id: UUID
    status: ScheduleStatus
    created_by: UUID
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Shift Schemas
class ShiftBase(BaseModel):
    shift_date: date
    start_time: time
    end_time: time
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    meal_start: Optional[time] = None
    meal_end: Optional[time] = None
    shift_type: ShiftType = ShiftType.REGULAR
    is_mandatory: bool = False
    notes: Optional[str] = None

    @validator('end_time')
    def validate_shift_times(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v

class ShiftCreate(ShiftBase):
    schedule_id: UUID
    staff_id: UUID
    client_id: Optional[UUID] = None  # Primary client for this shift
    location_id: Optional[UUID] = None

class ShiftUpdate(BaseModel):
    shift_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    meal_start: Optional[time] = None
    meal_end: Optional[time] = None
    status: Optional[ShiftStatus] = None
    shift_type: Optional[ShiftType] = None
    is_mandatory: Optional[bool] = None
    notes: Optional[str] = None

class ShiftResponse(ShiftBase):
    id: UUID
    schedule_id: UUID
    staff_id: UUID
    location_id: Optional[UUID] = None
    status: ShiftStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ShiftBulkCreate(BaseModel):
    schedule_id: UUID
    shifts: List[ShiftCreate]


# Shift Assignment Schemas
class ShiftAssignmentBase(BaseModel):
    assignment_type: AssignmentType = AssignmentType.PRIMARY
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    services_provided: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

class ShiftAssignmentCreate(ShiftAssignmentBase):
    shift_id: UUID
    client_id: UUID

class ShiftAssignmentResponse(ShiftAssignmentBase):
    id: UUID
    shift_id: UUID
    client_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Staff Availability Schemas
class StaffAvailabilityBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    availability_type: AvailabilityType = AvailabilityType.AVAILABLE
    effective_date: date
    expiry_date: Optional[date] = None
    notes: Optional[str] = None

    @validator('end_time')
    def validate_availability_times(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v

class StaffAvailabilityCreate(StaffAvailabilityBase):
    staff_id: UUID

class StaffAvailabilityUpdate(BaseModel):
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    availability_type: Optional[AvailabilityType] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None

class StaffAvailabilityResponse(StaffAvailabilityBase):
    id: UUID
    staff_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StaffAvailabilityBulkUpdate(BaseModel):
    staff_id: UUID
    availability_slots: List[StaffAvailabilityBase]


# Time Off Scheduling Schemas
class TimeOffSchedulingBase(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    time_off_type: TimeOffType
    affects_scheduling: bool = True
    replacement_required: bool = True
    notes: Optional[str] = None

    @validator('end_datetime')
    def validate_time_off_range(cls, v, values):
        if 'start_datetime' in values and v <= values['start_datetime']:
            raise ValueError('End datetime must be after start datetime')
        return v

class TimeOffSchedulingCreate(TimeOffSchedulingBase):
    staff_id: UUID

class TimeOffSchedulingResponse(TimeOffSchedulingBase):
    id: UUID
    staff_id: UUID
    status: RequestStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Coverage Request Schemas
class CoverageRequestBase(BaseModel):
    reason: str
    request_type: RequestType
    notes: Optional[str] = None

class CoverageRequestCreate(CoverageRequestBase):
    original_shift_id: UUID
    requesting_staff_id: UUID

class CoverageRequestUpdate(BaseModel):
    status: RequestStatus
    notes: Optional[str] = None

class CoverageRequestResponse(CoverageRequestBase):
    id: UUID
    original_shift_id: UUID
    requesting_staff_id: UUID
    status: RequestStatus
    requested_at: datetime
    responded_at: Optional[datetime] = None
    responded_by: Optional[UUID] = None

    class Config:
        from_attributes = True


# Shift Swap Schemas
class ShiftSwapBase(BaseModel):
    swap_date: date

class ShiftSwapCreate(ShiftSwapBase):
    coverage_request_id: UUID
    shift_a_id: UUID
    shift_b_id: UUID
    staff_a_id: UUID
    staff_b_id: UUID

class ShiftSwapResponse(ShiftSwapBase):
    id: UUID
    coverage_request_id: UUID
    shift_a_id: UUID
    shift_b_id: UUID
    staff_a_id: UUID
    staff_b_id: UUID
    status: SwapStatus
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Appointment Schemas
class AppointmentBase(BaseModel):
    appointment_type: AppointmentType
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    requires_transport: bool = False
    notes: Optional[str] = None

    @validator('end_datetime')
    def validate_appointment_times(cls, v, values):
        if 'start_datetime' in values and v <= values['start_datetime']:
            raise ValueError('End datetime must be after start datetime')
        return v

class AppointmentCreate(AppointmentBase):
    organization_id: UUID
    client_id: UUID
    staff_id: UUID
    transport_staff_id: Optional[UUID] = None

class AppointmentUpdate(BaseModel):
    appointment_type: Optional[AppointmentType] = None
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    requires_transport: Optional[bool] = None
    transport_staff_id: Optional[UUID] = None
    notes: Optional[str] = None

class AppointmentResponse(AppointmentBase):
    id: UUID
    organization_id: UUID
    client_id: UUID
    staff_id: UUID
    transport_staff_id: Optional[UUID] = None
    status: AppointmentStatus
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Recurring Appointment Schemas
class RecurringAppointmentBase(BaseModel):
    appointment_type: str = Field(..., max_length=100)
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: time
    duration_minutes: int = Field(..., gt=0)
    recurrence_pattern: RecurrencePattern
    recurrence_days: Optional[List[int]] = None
    start_date: date
    end_date: Optional[date] = None
    max_occurrences: Optional[int] = Field(None, gt=0)

class RecurringAppointmentCreate(RecurringAppointmentBase):
    organization_id: UUID
    client_id: UUID
    staff_id: UUID

class RecurringAppointmentUpdate(BaseModel):
    appointment_type: Optional[str] = Field(None, max_length=100)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[time] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    recurrence_pattern: Optional[RecurrencePattern] = None
    recurrence_days: Optional[List[int]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    max_occurrences: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None

class RecurringAppointmentResponse(RecurringAppointmentBase):
    id: UUID
    organization_id: UUID
    client_id: UUID
    staff_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Time Clock Schemas
class TimeClockEntryBase(BaseModel):
    entry_type: TimeEntryType
    entry_datetime: datetime
    location_verified: bool = False
    geolocation: Optional[str] = None
    ip_address: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None

class TimeClockEntryCreate(TimeClockEntryBase):
    staff_id: UUID
    shift_id: Optional[UUID] = None

class TimeClockEntryResponse(TimeClockEntryBase):
    id: UUID
    staff_id: UUID
    shift_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ClockInRequest(BaseModel):
    staff_id: Optional[UUID] = None  # Optional - will use current user's staff record if not provided
    shift_id: Optional[UUID] = None
    geolocation: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None

class ClockOutRequest(BaseModel):
    staff_id: Optional[UUID] = None  # Optional - will use current user's staff record if not provided
    shift_id: Optional[UUID] = None
    geolocation: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None


# Calendar Event Schemas
class CalendarEventBase(BaseModel):
    event_type: EventType
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    location: Optional[str] = None
    all_day: bool = False
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    attendees: Optional[List[UUID]] = None
    color: str = Field("#4F46E5", pattern=r"^#[0-9A-Fa-f]{6}$")
    visibility: EventVisibility = EventVisibility.PUBLIC

    @validator('end_datetime')
    def validate_event_times(cls, v, values):
        if 'start_datetime' in values and v <= values['start_datetime']:
            raise ValueError('End datetime must be after start datetime')
        return v

class CalendarEventCreate(CalendarEventBase):
    organization_id: UUID

class CalendarEventUpdate(BaseModel):
    event_type: Optional[EventType] = None
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    location: Optional[str] = None
    all_day: Optional[bool] = None
    is_recurring: Optional[bool] = None
    recurrence_rule: Optional[str] = None
    attendees: Optional[List[UUID]] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    visibility: Optional[EventVisibility] = None

class CalendarEventResponse(CalendarEventBase):
    id: UUID
    organization_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schedule Conflict Schemas
class ScheduleConflictResponse(BaseModel):
    id: UUID
    conflict_type: ConflictType
    shift_id: Optional[UUID] = None
    staff_id: UUID
    conflict_description: str
    severity: ConflictSeverity
    resolved: bool
    resolved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Calendar View Schemas
class CalendarViewRequest(BaseModel):
    start_date: date
    end_date: date
    staff_ids: Optional[List[UUID]] = None
    include_shifts: bool = True
    include_appointments: bool = True
    include_events: bool = True
    include_time_off: bool = True


# Overtime Tracking Schemas
class OvertimeTrackingResponse(BaseModel):
    id: UUID
    staff_id: UUID
    shift_id: Optional[UUID] = None
    week_start_date: date
    regular_hours: float
    overtime_hours: float
    double_time_hours: float
    holiday_hours: float
    total_hours: float
    approved: bool
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Reporting Schemas
class ScheduleUtilizationReport(BaseModel):
    total_shifts: int
    completed_shifts: int
    cancelled_shifts: int
    no_show_shifts: int
    total_hours: float
    overtime_hours: float
    coverage_rate: float
    staff_utilization: Dict[str, float]


class AttendanceReport(BaseModel):
    staff_id: UUID
    period_start: date
    period_end: date
    scheduled_hours: float
    worked_hours: float
    overtime_hours: float
    attendance_rate: float
    punctuality_score: float


# Pagination
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int