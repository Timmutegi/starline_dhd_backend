from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    # Support uppercase values from frontend
    APPROVED_UPPER = "APPROVED"
    DENIED = "DENIED"

class TimeOffType(str, Enum):
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    FMLA = "fmla"
    OTHER = "other"

class TeamStats(BaseModel):
    total_staff: int = Field(..., description="Total staff under supervision")
    active_staff: int = Field(..., description="Currently active staff")
    on_leave_staff: int = Field(..., description="Staff currently on leave")
    total_clients: int = Field(..., description="Total clients assigned")
    active_clients: int = Field(..., description="Currently active clients")

class DocumentationMetrics(BaseModel):
    total_required: int = Field(..., description="Total documentation items required")
    completed: int = Field(..., description="Completed documentation")
    pending: int = Field(..., description="Pending documentation")
    completion_rate: float = Field(..., description="Completion rate percentage")

class IncidentMetrics(BaseModel):
    total_incidents: int = Field(..., description="Total incidents in period")
    resolved: int = Field(..., description="Resolved incidents")
    pending_review: int = Field(..., description="Incidents pending review")
    critical: int = Field(..., description="Critical incidents")

class StaffMemberSummary(BaseModel):
    staff_id: str = Field(..., description="Staff ID")
    user_id: str = Field(..., description="User ID")
    full_name: str = Field(..., description="Staff full name")
    employee_id: str = Field(..., description="Employee ID")
    job_title: Optional[str] = Field(None, description="Job title")
    department: Optional[str] = Field(None, description="Department")
    employment_status: str = Field(..., description="Employment status")
    clients_assigned: int = Field(..., description="Number of assigned clients")
    certifications_expiring: int = Field(default=0, description="Certifications expiring soon")
    training_completion: float = Field(default=0.0, description="Training completion percentage")
    last_active: Optional[datetime] = Field(None, description="Last activity timestamp")

class ClientOversightSummary(BaseModel):
    id: str = Field(..., description="Client UUID")
    client_id: str = Field(..., description="Client code (human readable)")
    user_id: Optional[str] = Field(None, description="User ID if client has account")
    full_name: str = Field(..., description="Client full name")
    status: str = Field(..., description="Client status")
    location_id: Optional[str] = Field(None, description="Client location UUID")
    location_name: Optional[str] = Field(None, description="Client location name")
    assigned_staff_count: int = Field(..., description="Number of assigned staff")
    documentation_completion: float = Field(..., description="Documentation completion %")
    risk_level: Optional[str] = Field(None, description="Client risk level")
    recent_incidents: int = Field(default=0, description="Number of recent incidents")
    last_service_date: Optional[datetime] = Field(None, description="Last service date")
    next_appointment: Optional[datetime] = Field(None, description="Next scheduled appointment")
    care_plan_status: Optional[str] = Field(None, description="Care plan status")
    required_documentation: Optional[List[str]] = Field(default=None, description="Required documentation types for this client")

class PendingApproval(BaseModel):
    id: str = Field(..., description="Approval item ID")
    type: str = Field(..., description="Type of approval (time_off, shift_note, incident)")
    staff_id: str = Field(..., description="Staff requesting approval")
    staff_name: str = Field(..., description="Staff name")
    title: str = Field(..., description="Approval item title")
    description: Optional[str] = Field(None, description="Description")
    submitted_at: datetime = Field(..., description="When submitted")
    priority: str = Field(default="normal", description="Priority level")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class ManagerDashboardOverview(BaseModel):
    team_stats: TeamStats = Field(..., description="Team statistics")
    documentation_metrics: DocumentationMetrics = Field(..., description="Documentation metrics")
    incident_metrics: IncidentMetrics = Field(..., description="Incident metrics")
    pending_approvals: List[PendingApproval] = Field(..., description="Items pending approval")
    staff_on_shift: int = Field(..., description="Staff currently on shift")
    appointments_today: int = Field(..., description="Appointments scheduled today")
    tasks_overdue: int = Field(..., description="Overdue tasks")
    last_updated: datetime = Field(..., description="When dashboard was last updated")

class TimeOffRequestCreate(BaseModel):
    type: TimeOffType = Field(..., description="Type of time off")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for request")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")

class TimeOffRequestResponse(BaseModel):
    id: str = Field(..., description="Request ID")
    staff_id: str = Field(..., description="Staff ID")
    staff_name: str = Field(..., description="Staff name")
    type: str = Field(..., description="Type of time off")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    days_requested: int = Field(..., description="Number of days requested")
    total_hours: float = Field(..., description="Total hours requested")
    status: str = Field(..., description="Approval status")
    reason: Optional[str] = Field(None, description="Reason for request")
    notes: Optional[str] = Field(None, description="Additional notes")
    reviewed_by: Optional[str] = Field(None, description="Manager who reviewed")
    reviewed_at: Optional[datetime] = Field(None, description="When reviewed")
    review_notes: Optional[str] = Field(None, description="Manager review notes")
    created_at: datetime = Field(..., description="When request was created")

class ApprovalActionRequest(BaseModel):
    action: ApprovalStatus = Field(..., description="Approve or reject")
    notes: Optional[str] = Field(None, max_length=1000, description="Manager notes")

class StaffAssignmentCreate(BaseModel):
    staff_id: str = Field(..., description="Staff ID to assign")
    client_id: str = Field(..., description="Client ID to assign to")
    assignment_type: str = Field(default="PRIMARY", description="Assignment type (PRIMARY, SECONDARY, BACKUP, RELIEF)")
    start_date: date = Field(..., description="Assignment start date")
    end_date: Optional[date] = Field(None, description="Assignment end date")
    notes: Optional[str] = Field(None, max_length=1000, description="Assignment notes")

class StaffAssignmentResponse(BaseModel):
    id: str = Field(..., description="Assignment ID")
    staff_id: str = Field(..., description="Staff ID")
    staff_name: str = Field(..., description="Staff name")
    client_id: str = Field(..., description="Client ID")
    client_name: str = Field(..., description="Client name")
    assignment_type: str = Field(..., description="Assignment type")
    start_date: date = Field(..., description="Start date")
    end_date: Optional[date] = Field(None, description="End date")
    is_active: bool = Field(..., description="Whether assignment is active")
    notes: Optional[str] = Field(None, description="Notes")
    created_at: datetime = Field(..., description="When created")

class ScheduleConflict(BaseModel):
    staff_id: str = Field(..., description="Staff ID with conflict")
    staff_name: str = Field(..., description="Staff name")
    conflict_type: str = Field(..., description="Type of conflict")
    shift_date: date = Field(..., description="Date of conflict")
    details: str = Field(..., description="Conflict details")

class ScheduleCreateRequest(BaseModel):
    staff_id: str = Field(..., description="Staff ID for schedule")
    client_id: Optional[str] = Field(None, description="Client ID if client-specific")
    start_time: datetime = Field(..., description="Shift start time")
    end_time: datetime = Field(..., description="Shift end time")
    shift_type: str = Field(default="REGULAR", description="Shift type")
    location: Optional[str] = Field(None, description="Shift location")
    notes: Optional[str] = Field(None, max_length=500, description="Shift notes")

class TrainingAssignmentRequest(BaseModel):
    course_id: str = Field(..., description="Training course ID")
    staff_ids: List[str] = Field(..., min_items=1, description="Staff to assign training")
    due_date: Optional[date] = Field(None, description="Training completion due date")
    notes: Optional[str] = Field(None, max_length=500, description="Assignment notes")

class TrainingAssignmentSummary(BaseModel):
    id: str = Field(..., description="Training record ID")
    course_title: str = Field(..., description="Training course title")
    staff_name: str = Field(..., description="Assigned staff member name")
    staff_id: str = Field(..., description="Staff member ID")
    assigned_date: date = Field(..., description="Date assigned")
    due_date: Optional[date] = Field(None, description="Due date")
    completion_status: str = Field(..., description="Status (not_started, in_progress, completed)")
    completed_date: Optional[date] = Field(None, description="Completion date")
    progress_percentage: float = Field(0.0, description="Progress percentage")
    priority: str = Field("medium", description="Priority (low, medium, high)")

    class Config:
        from_attributes = True

class TrainingActivityItem(BaseModel):
    type: str = Field(..., description="Activity type: completion, in_progress, or due_soon")
    staff_name: str = Field(..., description="Staff member name")
    course_title: str = Field(..., description="Training course title")
    progress_percentage: Optional[float] = Field(None, description="Progress percentage for in_progress")
    timestamp: datetime = Field(..., description="Activity timestamp")
    staff_count: Optional[int] = Field(None, description="Number of staff for due_soon type")
    days_until_due: Optional[int] = Field(None, description="Days until due for due_soon type")

    class Config:
        from_attributes = True

class ShiftSummary(BaseModel):
    id: str
    staff_name: str
    staff_id: str
    client_name: Optional[str] = None
    client_id: Optional[str] = None
    location_name: Optional[str] = None
    location_id: Optional[str] = None
    start_time: datetime
    end_time: datetime
    status: str
    shift_type: str

    class Config:
        from_attributes = True

class AppointmentSummary(BaseModel):
    id: str
    client_name: str
    client_id: str
    staff_name: Optional[str] = None
    staff_id: Optional[str] = None
    appointment_type: str
    start_time: datetime
    end_time: datetime
    status: str
    location: Optional[str] = None

    class Config:
        from_attributes = True

class NoticeCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Notice title")
    content: str = Field(..., min_length=1, max_length=5000, description="Notice content")
    priority: str = Field(default="normal", description="Priority (low, normal, high, urgent)")
    category: str = Field(default="general", description="Notice category")
    target_roles: Optional[List[str]] = Field(None, description="Target specific roles")
    expires_at: Optional[datetime] = Field(None, description="When notice expires")
    requires_acknowledgment: bool = Field(default=False, description="Requires staff acknowledgment")

class StaffPerformanceMetrics(BaseModel):
    staff_id: str = Field(..., description="Staff ID")
    staff_name: str = Field(..., description="Staff name")
    period_start: date = Field(..., description="Metrics period start")
    period_end: date = Field(..., description="Metrics period end")
    shifts_scheduled: int = Field(..., description="Shifts scheduled")
    shifts_completed: int = Field(..., description="Shifts completed")
    attendance_rate: float = Field(..., description="Attendance rate %")
    documentation_compliance: float = Field(..., description="Documentation compliance %")
    incidents_reported: int = Field(..., description="Incidents reported")
    training_completed: int = Field(..., description="Training courses completed")
    client_feedback_score: Optional[float] = Field(None, description="Average client feedback score")

class ComplianceReport(BaseModel):
    report_type: str = Field(..., description="Type of compliance report")
    period_start: date = Field(..., description="Report period start")
    period_end: date = Field(..., description="Report period end")
    total_items: int = Field(..., description="Total items reviewed")
    compliant_items: int = Field(..., description="Compliant items")
    non_compliant_items: int = Field(..., description="Non-compliant items")
    compliance_rate: float = Field(..., description="Compliance rate %")
    issues: List[Dict[str, Any]] = Field(..., description="List of compliance issues")
    recommendations: List[str] = Field(..., description="Recommendations")
    generated_at: datetime = Field(..., description="When report was generated")

class CertificationAlert(BaseModel):
    staff_id: str = Field(..., description="Staff ID")
    staff_name: str = Field(..., description="Staff name")
    certification_name: str = Field(..., description="Certification name")
    expiry_date: date = Field(..., description="Expiration date")
    days_until_expiry: int = Field(..., description="Days until expiration")
    status: str = Field(..., description="Status (active, expiring_soon, expired)")
