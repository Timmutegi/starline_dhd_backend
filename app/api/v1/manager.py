from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, timezone, date, timedelta
from typing import Optional, List
from app.core.database import get_db
from app.core.dependencies import get_manager_or_above
from app.models.user import User
from app.models.client import Client, CarePlan
from app.models.staff import (
    Staff, StaffAssignment, TimeOffRequest, TimeOffStatus,
    StaffCertification, TrainingRecord, TrainingProgram, CertificationStatus, TrainingStatus
)
from app.models.scheduling import Shift, Appointment
from app.models.incident_report import IncidentReport, IncidentStatusEnum, IncidentSeverityEnum
from app.models.shift_note import ShiftNote
from app.models.task import Task, TaskStatusEnum
from app.models.vitals_log import VitalsLog
from app.models.meal_log import MealLog
from app.models.activity_log import ActivityLog
from app.models.notice import Notice
from app.schemas.manager import (
    ManagerDashboardOverview,
    TeamStats,
    DocumentationMetrics,
    IncidentMetrics,
    PendingApproval,
    StaffMemberSummary,
    ClientOversightSummary,
    TimeOffRequestResponse,
    ApprovalActionRequest,
    StaffAssignmentCreate,
    StaffAssignmentResponse,
    ScheduleCreateRequest,
    ScheduleConflict,
    ShiftSummary,
    AppointmentSummary,
    TrainingAssignmentRequest,
    TrainingAssignmentSummary,
    TrainingActivityItem,
    NoticeCreateRequest,
    StaffPerformanceMetrics,
    ComplianceReport,
    CertificationAlert
)
from app.schemas.staff import TrainingProgramCreate, TrainingProgramResponse

router = APIRouter()

@router.get("/dashboard", response_model=ManagerDashboardOverview)
async def get_manager_dashboard(
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive manager dashboard overview
    Managers see data for their organization and supervised staff
    """
    try:
        org_id = current_user.organization_id

        # Get staff under supervision (all staff in organization for managers)
        # In a more complex system, you'd filter by supervisor_id
        staff_query = db.query(Staff).filter(Staff.organization_id == org_id)
        total_staff = staff_query.count()
        active_staff = staff_query.filter(Staff.employment_status == "ACTIVE").count()
        on_leave_staff = staff_query.filter(Staff.employment_status == "ON_LEAVE").count()

        # Get clients
        client_query = db.query(Client).filter(Client.organization_id == org_id)
        total_clients = client_query.count()
        active_clients = client_query.filter(Client.status == "active").count()

        team_stats = TeamStats(
            total_staff=total_staff,
            active_staff=active_staff,
            on_leave_staff=on_leave_staff,
            total_clients=total_clients,
            active_clients=active_clients
        )

        # Documentation metrics - count actual documentation records in last 7 days
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        # Count all documentation types created in the last 7 days
        shift_notes_count = db.query(ShiftNote).filter(
            ShiftNote.organization_id == org_id,
            ShiftNote.created_at >= seven_days_ago
        ).count()

        vitals_count = db.query(VitalsLog).filter(
            VitalsLog.organization_id == org_id,
            VitalsLog.recorded_at >= seven_days_ago
        ).count()

        meals_count = db.query(MealLog).filter(
            MealLog.organization_id == org_id,
            MealLog.meal_date >= seven_days_ago
        ).count()

        activities_count = db.query(ActivityLog).filter(
            ActivityLog.organization_id == org_id,
            ActivityLog.activity_date >= seven_days_ago
        ).count()

        incidents_count = db.query(IncidentReport).filter(
            IncidentReport.organization_id == org_id,
            IncidentReport.incident_date >= seven_days_ago.date()
        ).count()

        completed = shift_notes_count + vitals_count + meals_count + activities_count + incidents_count

        # Calculate pending tasks for documentation
        pending = db.query(Task).filter(
            Task.organization_id == org_id,
            Task.status == TaskStatusEnum.PENDING,
            Task.due_date >= seven_days_ago
        ).count()

        total_required = completed + pending
        completion_rate = (completed / total_required * 100) if total_required > 0 else 100.0

        documentation_metrics = DocumentationMetrics(
            total_required=total_required,
            completed=completed,
            pending=pending,
            completion_rate=completion_rate
        )

        # Incident metrics
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        incidents_query = db.query(IncidentReport).filter(
            IncidentReport.organization_id == org_id,
            IncidentReport.incident_date >= thirty_days_ago.date()
        )
        total_incidents = incidents_query.count()
        resolved = incidents_query.filter(IncidentReport.status == IncidentStatusEnum.RESOLVED).count()
        pending_review = incidents_query.filter(IncidentReport.status == IncidentStatusEnum.UNDER_REVIEW).count()
        critical = incidents_query.filter(IncidentReport.severity == IncidentSeverityEnum.CRITICAL).count()

        incident_metrics = IncidentMetrics(
            total_incidents=total_incidents,
            resolved=resolved,
            pending_review=pending_review,
            critical=critical
        )

        # Pending approvals
        pending_approvals = []

        # Time off requests pending approval
        time_off_requests = db.query(TimeOffRequest).join(Staff).filter(
            Staff.organization_id == org_id,
            TimeOffRequest.status == TimeOffStatus.PENDING
        ).order_by(TimeOffRequest.requested_date).limit(10).all()

        for request in time_off_requests:
            pending_approvals.append(PendingApproval(
                id=str(request.id),
                type="time_off",
                staff_id=str(request.staff_id),
                staff_name=request.staff.full_name if request.staff else "Unknown",
                title=f"{request.request_type.value.title()} Request",
                description=f"{request.start_date} to {request.end_date}",
                submitted_at=request.requested_date,
                priority="normal",
                metadata={
                    "start_date": str(request.start_date),
                    "end_date": str(request.end_date),
                    "type": request.request_type.value
                }
            ))

        # Recent shift notes (last 7 days) - for manager review
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_shift_notes = db.query(ShiftNote).filter(
            ShiftNote.organization_id == org_id,
            ShiftNote.created_at >= seven_days_ago
        ).order_by(ShiftNote.created_at.desc()).limit(5).all()

        for note in recent_shift_notes:
            staff_name = "Unknown"
            if note.staff:
                staff_name = f"{note.staff.first_name} {note.staff.last_name}"

            pending_approvals.append(PendingApproval(
                id=str(note.id),
                type="shift_note",
                staff_id=str(note.staff_id),
                staff_name=staff_name,
                title="Recent Shift Note",
                description=f"Client: {note.client.first_name} {note.client.last_name}" if note.client else "N/A",
                submitted_at=note.created_at,
                priority="normal"
            ))

        # Staff on shift currently (shifts in progress for today)
        from app.models.scheduling import ShiftStatus
        today = date.today()
        staff_on_shift = db.query(Shift).join(Staff).filter(
            Staff.organization_id == org_id,
            Shift.shift_date == today,
            Shift.status == ShiftStatus.IN_PROGRESS
        ).count()

        # Appointments today
        today = date.today()
        appointments_today = db.query(Appointment).filter(
            Appointment.organization_id == org_id,
            func.date(Appointment.start_datetime) == today
        ).count()

        # Overdue tasks
        tasks_overdue = db.query(Task).filter(
            Task.organization_id == org_id,
            Task.due_date < today,
            Task.status != TaskStatusEnum.COMPLETED
        ).count()

        return ManagerDashboardOverview(
            team_stats=team_stats,
            documentation_metrics=documentation_metrics,
            incident_metrics=incident_metrics,
            pending_approvals=pending_approvals,
            staff_on_shift=staff_on_shift,
            appointments_today=appointments_today,
            tasks_overdue=tasks_overdue,
            last_updated=datetime.utcnow()
        )

    except Exception as e:
        import traceback
        print(f"ERROR in manager dashboard: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve manager dashboard: {str(e)}"
        )

@router.get("/staff", response_model=List[StaffMemberSummary])
async def get_staff_list(
    status: Optional[str] = Query(None, description="Filter by employment status"),
    search: Optional[str] = Query(None, description="Search by name or employee ID"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get list of staff members under supervision with oversight metrics
    """
    try:
        org_id = current_user.organization_id

        query = db.query(Staff).join(User, Staff.user_id == User.id).filter(Staff.organization_id == org_id)

        if status:
            query = query.filter(Staff.employment_status == status.upper())

        if search:
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    Staff.employee_id.ilike(f"%{search}%")
                )
            )

        staff_list = query.order_by(User.last_name).offset(offset).limit(limit).all()

        results = []
        for staff in staff_list:
            # Count assigned clients
            clients_assigned = db.query(StaffAssignment).filter(
                StaffAssignment.staff_id == staff.id,
                StaffAssignment.is_active == True
            ).count()

            # Count certifications expiring in next 60 days
            sixty_days_from_now = date.today() + timedelta(days=60)
            certifications_expiring = db.query(StaffCertification).filter(
                StaffCertification.staff_id == staff.id,
                StaffCertification.expiry_date.isnot(None),
                StaffCertification.expiry_date <= sixty_days_from_now,
                StaffCertification.expiry_date >= date.today(),
                StaffCertification.status == CertificationStatus.ACTIVE
            ).count()

            # Calculate training completion rate
            total_training = db.query(TrainingRecord).filter(
                TrainingRecord.staff_id == staff.id
            ).count()
            completed_training = db.query(TrainingRecord).filter(
                TrainingRecord.staff_id == staff.id,
                TrainingRecord.status == TrainingStatus.COMPLETED
            ).count()
            training_completion = (completed_training / total_training * 100) if total_training > 0 else 0.0

            # Last activity (last shift date)
            last_shift = db.query(Shift).filter(
                Shift.staff_id == staff.id
            ).order_by(Shift.shift_date.desc()).first()
            # Combine shift_date and start_time into a datetime for last_active
            if last_shift:
                last_active = datetime.combine(last_shift.shift_date, last_shift.start_time)
            else:
                last_active = None

            results.append(StaffMemberSummary(
                staff_id=str(staff.id),
                user_id=str(staff.user_id),
                full_name=staff.full_name,
                employee_id=staff.employee_id,
                job_title=staff.job_title,
                department=staff.department,
                employment_status=staff.employment_status.value,
                clients_assigned=clients_assigned,
                certifications_expiring=certifications_expiring,
                training_completion=training_completion,
                last_active=last_active
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve staff list: {str(e)}"
        )

@router.get("/clients", response_model=List[ClientOversightSummary])
async def get_clients_oversight(
    status: Optional[str] = Query(None, description="Filter by client status"),
    location: Optional[str] = Query(None, description="Filter by location"),
    search: Optional[str] = Query(None, description="Search by name or client code"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get list of clients with oversight metrics
    """
    try:
        org_id = current_user.organization_id

        query = db.query(Client).filter(Client.organization_id == org_id)

        if status:
            query = query.filter(Client.status == status)

        if search:
            query = query.filter(
                or_(
                    Client.first_name.ilike(f"%{search}%"),
                    Client.last_name.ilike(f"%{search}%"),
                    Client.client_id.ilike(f"%{search}%")
                )
            )

        clients = query.order_by(Client.last_name).offset(offset).limit(limit).all()

        results = []
        for client in clients:
            # Count assigned staff
            assigned_staff_count = db.query(StaffAssignment).filter(
                StaffAssignment.client_id == client.id,
                StaffAssignment.is_active == True
            ).count()

            # Calculate documentation completion based on tasks
            client_tasks_total = db.query(Task).filter(
                Task.client_id == client.id
            ).count()

            client_tasks_completed = db.query(Task).filter(
                Task.client_id == client.id,
                Task.status == TaskStatusEnum.COMPLETED
            ).count()

            documentation_completion = (
                (client_tasks_completed / client_tasks_total * 100)
                if client_tasks_total > 0 else 100.0
            )

            # Count incidents in last 30 days
            thirty_days_ago = date.today() - timedelta(days=30)
            incidents_count = db.query(IncidentReport).filter(
                IncidentReport.client_id == client.id,
                IncidentReport.incident_date >= thirty_days_ago
            ).count()

            # Last shift note
            last_shift_note = db.query(ShiftNote).filter(
                ShiftNote.client_id == client.id
            ).order_by(ShiftNote.created_at.desc()).first()
            last_shift_note_time = last_shift_note.created_at if last_shift_note else None

            # Get actual care plan status
            latest_care_plan = db.query(CarePlan).filter(
                CarePlan.client_id == client.id
            ).order_by(CarePlan.created_at.desc()).first()
            care_plan_status = latest_care_plan.status if latest_care_plan else "none"

            # Get location - Priority order:
            # 1. Client's direct location_id field
            # 2. Client assignment (legacy)
            location_name = None
            if client.location_id:
                from app.models.location import Location
                location = db.query(Location).filter(
                    Location.id == client.location_id
                ).first()
                if location:
                    location_name = location.name

            # Fallback to client assignment if no direct location
            if not location_name:
                from app.models.client import ClientAssignment, ClientLocation
                current_assignment = db.query(ClientAssignment).filter(
                    ClientAssignment.client_id == client.id,
                    ClientAssignment.is_current == True
                ).first()
                if current_assignment and current_assignment.location_id:
                    location = db.query(ClientLocation).filter(
                        ClientLocation.id == current_assignment.location_id
                    ).first()
                    if location:
                        location_name = location.name

            results.append(ClientOversightSummary(
                client_id=str(client.id),
                user_id=str(client.user_id) if client.user_id else None,
                full_name=f"{client.first_name} {client.last_name}",
                client_code=client.client_id,
                status=client.status,
                location=location_name,
                assigned_staff_count=assigned_staff_count,
                documentation_completion=documentation_completion,
                incidents_count=incidents_count,
                last_shift_note=last_shift_note_time,
                care_plan_status=care_plan_status
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve clients: {str(e)}"
        )

@router.get("/time-off-requests", response_model=List[TimeOffRequestResponse])
async def get_time_off_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    staff_id: Optional[str] = Query(None, description="Filter by staff"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get time off requests for review
    """
    try:
        org_id = current_user.organization_id

        query = db.query(TimeOffRequest).join(Staff).filter(
            Staff.organization_id == org_id
        )

        if status:
            query = query.filter(TimeOffRequest.status == status.upper())

        if staff_id:
            query = query.filter(TimeOffRequest.staff_id == staff_id)

        requests = query.order_by(TimeOffRequest.requested_date.desc()).offset(offset).limit(limit).all()

        results = []
        for request in requests:
            days_requested = (request.end_date - request.start_date).days + 1

            results.append(TimeOffRequestResponse(
                id=str(request.id),
                staff_id=str(request.staff_id),
                staff_name=request.staff.full_name if request.staff else "Unknown",
                type=request.request_type.value,
                start_date=request.start_date,
                end_date=request.end_date,
                days_requested=days_requested,
                status=request.status.value,
                reason=request.reason,
                notes=None,
                reviewed_by=str(request.approved_by) if request.approved_by else None,
                reviewed_at=request.approved_date,
                review_notes=request.denial_reason,
                created_at=request.requested_date
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve time off requests: {str(e)}"
        )

@router.post("/time-off-requests/{request_id}/approve")
async def approve_time_off_request(
    request_id: str,
    action: ApprovalActionRequest,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Approve or reject time off request
    """
    try:
        org_id = current_user.organization_id

        time_off_request = db.query(TimeOffRequest).join(Staff).filter(
            TimeOffRequest.id == request_id,
            Staff.organization_id == org_id
        ).first()

        if not time_off_request:
            raise HTTPException(status_code=404, detail="Time off request not found")

        if time_off_request.status != TimeOffStatus.PENDING:
            raise HTTPException(status_code=400, detail="Request already reviewed")

        if action.action == "APPROVED":
            time_off_request.status = TimeOffStatus.APPROVED
        else:
            time_off_request.status = TimeOffStatus.DENIED
            time_off_request.denial_reason = action.notes

        time_off_request.approved_by = current_user.id
        time_off_request.approved_date = datetime.utcnow()

        db.commit()

        return {
            "message": f"Time off request {action.action.value}",
            "request_id": request_id,
            "status": time_off_request.status.value
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process time off request: {str(e)}"
        )

@router.post("/staff-assignments", response_model=StaffAssignmentResponse)
async def create_staff_assignment(
    assignment: StaffAssignmentCreate,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Assign staff to client
    """
    try:
        org_id = current_user.organization_id

        # Verify staff belongs to organization
        staff = db.query(Staff).filter(
            Staff.id == assignment.staff_id,
            Staff.organization_id == org_id
        ).first()

        if not staff:
            raise HTTPException(status_code=404, detail="Staff not found")

        # Verify client belongs to organization
        client = db.query(Client).filter(
            Client.id == assignment.client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Create assignment
        new_assignment = StaffAssignment(
            staff_id=assignment.staff_id,
            client_id=assignment.client_id,
            assignment_type=assignment.assignment_type.upper(),
            start_date=assignment.start_date,
            end_date=assignment.end_date,
            notes=assignment.notes,
            is_active=True
        )

        db.add(new_assignment)
        db.commit()
        db.refresh(new_assignment)

        return StaffAssignmentResponse(
            id=str(new_assignment.id),
            staff_id=str(new_assignment.staff_id),
            staff_name=staff.full_name,
            client_id=str(new_assignment.client_id),
            client_name=f"{client.first_name} {client.last_name}",
            assignment_type=assignment.assignment_type,
            start_date=new_assignment.start_date,
            end_date=new_assignment.end_date,
            is_active=new_assignment.is_active,
            notes=new_assignment.notes,
            created_at=new_assignment.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create staff assignment: {str(e)}"
        )

@router.get("/certification-alerts", response_model=List[CertificationAlert])
async def get_certification_alerts(
    days_ahead: int = Query(60, description="Days ahead to check for expiring certifications"),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get certifications expiring soon
    """
    try:
        org_id = current_user.organization_id
        today = date.today()
        future_date = today + timedelta(days=days_ahead)

        certifications = db.query(StaffCertification).join(Staff).filter(
            Staff.organization_id == org_id,
            StaffCertification.expiry_date.isnot(None),
            StaffCertification.expiry_date <= future_date,
            StaffCertification.status == CertificationStatus.ACTIVE
        ).order_by(StaffCertification.expiry_date).all()

        results = []
        for cert in certifications:
            days_until_expiry = (cert.expiry_date - today).days

            if days_until_expiry < 0:
                status = "expired"
            elif days_until_expiry <= 30:
                status = "expiring_soon"
            else:
                status = "active"

            results.append(CertificationAlert(
                staff_id=str(cert.staff_id),
                staff_name=cert.staff.full_name if cert.staff else "Unknown",
                certification_name=cert.certification_name,
                expiry_date=cert.expiry_date,
                days_until_expiry=days_until_expiry,
                status=status
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve certification alerts: {str(e)}"
        )

@router.get("/training/programs/", response_model=List[TrainingProgramResponse])
async def get_training_programs(
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_mandatory: Optional[bool] = Query(None, description="Filter by mandatory status"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """Get all training programs for the organization"""
    try:
        org_id = current_user.organization_id

        query = db.query(TrainingProgram).filter(
            TrainingProgram.organization_id == org_id
        )

        if is_active is not None:
            query = query.filter(TrainingProgram.is_active == is_active)

        if is_mandatory is not None:
            query = query.filter(TrainingProgram.is_mandatory == is_mandatory)

        if category:
            query = query.filter(TrainingProgram.category == category)

        programs = query.order_by(TrainingProgram.program_name).all()

        return [TrainingProgramResponse.model_validate(program) for program in programs]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve training programs: {str(e)}"
        )

@router.post("/training/programs/", response_model=TrainingProgramResponse)
async def create_training_program(
    program_data: TrainingProgramCreate,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Create a new training program"""
    try:
        org_id = current_user.organization_id

        # Check if program with same name already exists
        existing = db.query(TrainingProgram).filter(
            TrainingProgram.organization_id == org_id,
            TrainingProgram.program_name == program_data.program_name
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="A training program with this name already exists"
            )

        # Create new training program
        new_program = TrainingProgram(
            organization_id=org_id,
            **program_data.model_dump()
        )

        db.add(new_program)
        db.commit()
        db.refresh(new_program)

        return TrainingProgramResponse.model_validate(new_program)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create training program: {str(e)}"
        )

@router.get("/training/recent-activity/", response_model=List[TrainingActivityItem])
async def get_recent_training_activity(
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db),
    limit: int = Query(10, le=20, description="Number of recent activities to return")
):
    """Get recent training activity (completions, in-progress, and upcoming due dates)"""
    try:
        org_id = current_user.organization_id
        activities = []

        # Get recent completions (last 7 days)
        seven_days_ago = date.today() - timedelta(days=7)
        completed_records = db.query(TrainingRecord).join(
            Staff, TrainingRecord.staff_id == Staff.id
        ).join(
            TrainingProgram, TrainingRecord.training_program_id == TrainingProgram.id
        ).options(
            joinedload(TrainingRecord.staff).joinedload(Staff.user),
            joinedload(TrainingRecord.training_program)
        ).filter(
            Staff.organization_id == org_id,
            TrainingRecord.status == TrainingStatus.COMPLETED,
            TrainingRecord.completion_date >= seven_days_ago
        ).order_by(TrainingRecord.completion_date.desc()).limit(5).all()

        for record in completed_records:
            if record.staff.user and record.training_program:
                activities.append(TrainingActivityItem(
                    type="completion",
                    staff_name=f"{record.staff.user.first_name} {record.staff.user.last_name}",
                    course_title=record.training_program.program_name,
                    progress_percentage=100.0,
                    timestamp=datetime.combine(record.completion_date, datetime.min.time()) if record.completion_date else datetime.now(),
                    staff_count=None,
                    days_until_due=None
                ))

        # Get in-progress training with significant progress (>25%)
        in_progress_records = db.query(TrainingRecord).join(
            Staff, TrainingRecord.staff_id == Staff.id
        ).join(
            TrainingProgram, TrainingRecord.training_program_id == TrainingProgram.id
        ).options(
            joinedload(TrainingRecord.staff).joinedload(Staff.user),
            joinedload(TrainingRecord.training_program)
        ).filter(
            Staff.organization_id == org_id,
            TrainingRecord.status == TrainingStatus.IN_PROGRESS,
            TrainingRecord.start_date.isnot(None)
        ).order_by(TrainingRecord.start_date.desc()).limit(3).all()

        for record in in_progress_records:
            if record.staff.user and record.training_program:
                # Calculate progress based on status
                progress = 50.0  # Default for in-progress
                activities.append(TrainingActivityItem(
                    type="in_progress",
                    staff_name=f"{record.staff.user.first_name} {record.staff.user.last_name}",
                    course_title=record.training_program.program_name,
                    progress_percentage=progress,
                    timestamp=datetime.combine(record.start_date, datetime.min.time()) if record.start_date else datetime.now(),
                    staff_count=None,
                    days_until_due=None
                ))

        # Get upcoming due dates (next 7 days) - group by program
        today = date.today()
        seven_days_ahead = today + timedelta(days=7)

        upcoming_due = db.query(
            TrainingProgram.program_name,
            TrainingRecord.due_date,
            func.count(TrainingRecord.id).label('staff_count')
        ).join(
            Staff, TrainingRecord.staff_id == Staff.id
        ).join(
            TrainingProgram, TrainingRecord.training_program_id == TrainingProgram.id
        ).filter(
            Staff.organization_id == org_id,
            TrainingRecord.status != TrainingStatus.COMPLETED,
            TrainingRecord.due_date.isnot(None),
            TrainingRecord.due_date >= today,
            TrainingRecord.due_date <= seven_days_ahead
        ).group_by(
            TrainingProgram.program_name,
            TrainingRecord.due_date
        ).order_by(TrainingRecord.due_date).limit(2).all()

        for program_name, due_date, staff_count in upcoming_due:
            days_until = (due_date - today).days
            activities.append(TrainingActivityItem(
                type="due_soon",
                staff_name="",  # Not applicable for grouped activities
                course_title=program_name,
                progress_percentage=None,
                timestamp=datetime.combine(due_date, datetime.min.time()),
                staff_count=staff_count,
                days_until_due=days_until
            ))

        # Sort all activities by timestamp (most recent first)
        activities.sort(key=lambda x: x.timestamp, reverse=True)

        return activities[:limit]

    except Exception as e:
        import traceback
        print(f"ERROR in recent training activity: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve recent training activity: {str(e)}"
        )

@router.get("/training/assignments", response_model=List[TrainingAssignmentSummary])
async def get_training_assignments(
    status: Optional[str] = Query(None, description="Filter by status"),
    staff_id: Optional[str] = Query(None, description="Filter by staff member"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get training assignments for the organization
    """
    try:
        org_id = current_user.organization_id

        # Query training records with eager loading
        from sqlalchemy.orm import joinedload

        query = db.query(TrainingRecord).join(
            Staff, TrainingRecord.staff_id == Staff.id
        ).join(
            TrainingProgram, TrainingRecord.training_program_id == TrainingProgram.id
        ).options(
            joinedload(TrainingRecord.staff).joinedload(Staff.user)
        ).filter(
            Staff.organization_id == org_id
        )

        # Apply filters
        if status:
            try:
                status_enum = TrainingStatus[status.upper()]
                query = query.filter(TrainingRecord.status == status_enum)
            except KeyError:
                pass

        if staff_id:
            query = query.filter(TrainingRecord.staff_id == staff_id)

        # Execute query
        training_records = query.order_by(TrainingRecord.enrollment_date.desc()).offset(offset).limit(limit).all()

        # Build response
        results = []
        for record in training_records:
            staff = record.staff
            program = record.training_program

            # Calculate priority based on due date
            priority = "medium"
            if record.due_date:
                days_until_due = (record.due_date - date.today()).days
                if days_until_due < 7:
                    priority = "high"
                elif days_until_due > 30:
                    priority = "low"

            # Calculate progress percentage based on status
            progress_percentage = 0.0
            if record.status == TrainingStatus.COMPLETED:
                progress_percentage = 100.0
            elif record.status == TrainingStatus.IN_PROGRESS:
                progress_percentage = 50.0  # Default for in-progress

            results.append(TrainingAssignmentSummary(
                id=str(record.id),
                course_title=program.title,
                staff_name=f"{staff.user.first_name} {staff.user.last_name}" if staff.user else "Unknown",
                staff_id=str(staff.id),
                assigned_date=record.enrollment_date,
                due_date=record.due_date,
                completion_status=record.status.value if isinstance(record.status, TrainingStatus) else record.status,
                completed_date=record.completion_date,
                progress_percentage=progress_percentage,
                priority=priority
            ))

        return results

    except Exception as e:
        import traceback
        print(f"ERROR in training assignments: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve training assignments: {str(e)}"
        )

@router.get("/shifts", response_model=List[ShiftSummary])
async def get_shifts(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    staff_id: Optional[str] = Query(None, description="Filter by staff member"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get shifts for the organization
    """
    try:
        org_id = current_user.organization_id

        # Default to current week if no dates provided
        if not start_date:
            start_date = date.today() - timedelta(days=date.today().weekday())
        if not end_date:
            end_date = start_date + timedelta(days=6)

        # Query shifts with eager loading
        query = db.query(Shift).options(
            joinedload(Shift.staff).joinedload(Staff.user),
            joinedload(Shift.client)
        ).join(
            Staff, Shift.staff_id == Staff.id
        ).filter(
            Staff.organization_id == org_id,
            Shift.shift_date >= start_date,
            Shift.shift_date <= end_date
        )

        # Apply filters
        if staff_id:
            query = query.filter(Shift.staff_id == staff_id)

        if status:
            query = query.filter(Shift.status == status)

        # Execute query
        shifts = query.order_by(Shift.shift_date, Shift.start_time).offset(offset).limit(limit).all()

        # Build response
        results = []
        for shift in shifts:
            staff = shift.staff
            client = shift.client

            # Fetch location if location_id exists
            location = None
            location_name = None
            if shift.location_id:
                from app.models.location import Location
                location = db.query(Location).filter(Location.id == shift.location_id).first()
                if location:
                    location_name = location.name

            # Combine date and time
            start_datetime = datetime.combine(shift.shift_date, shift.start_time)
            end_datetime = datetime.combine(shift.shift_date, shift.end_time)

            results.append(ShiftSummary(
                id=str(shift.id),
                staff_name=staff.full_name,
                staff_id=str(staff.id),
                client_name=f"{client.first_name} {client.last_name}" if client else None,
                client_id=str(client.id) if client else None,
                location_name=location_name,
                location_id=str(shift.location_id) if shift.location_id else None,
                start_time=start_datetime,
                end_time=end_datetime,
                status=shift.status.value if hasattr(shift.status, 'value') else shift.status,
                shift_type=shift.shift_type.value if hasattr(shift.shift_type, 'value') else shift.shift_type
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shifts: {str(e)}"
        )

@router.get("/appointments", response_model=List[AppointmentSummary])
async def get_appointments(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    client_id: Optional[str] = Query(None, description="Filter by client"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get appointments for the organization
    """
    try:
        org_id = current_user.organization_id

        # Default to current week if no dates provided
        if not start_date:
            start_date = date.today() - timedelta(days=date.today().weekday())
        if not end_date:
            end_date = start_date + timedelta(days=6)

        # Convert dates to datetime for comparison
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Query appointments
        query = db.query(Appointment).join(
            Client, Appointment.client_id == Client.id
        ).filter(
            Client.organization_id == org_id,
            Appointment.start_datetime >= start_datetime,
            Appointment.start_datetime <= end_datetime
        )

        # Apply filters
        if client_id:
            query = query.filter(Appointment.client_id == client_id)

        if status:
            query = query.filter(Appointment.status == status)

        # Execute query
        appointments = query.order_by(Appointment.start_datetime).offset(offset).limit(limit).all()

        # Build response
        results = []
        for apt in appointments:
            client = apt.client
            staff = apt.staff

            results.append(AppointmentSummary(
                id=str(apt.id),
                client_name=f"{client.first_name} {client.last_name}",
                client_id=str(client.id),
                staff_name=f"{staff.first_name} {staff.last_name}" if staff else None,
                staff_id=str(staff.id) if staff else None,
                appointment_type=apt.appointment_type.value if hasattr(apt.appointment_type, 'value') else apt.appointment_type,
                start_time=apt.start_datetime,
                end_time=apt.end_datetime,
                status=apt.status.value if hasattr(apt.status, 'value') else apt.status,
                location=apt.location
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve appointments: {str(e)}"
        )

@router.post("/training/assign")
async def assign_training(
    assignment: TrainingAssignmentRequest,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Assign training course to staff members
    """
    try:
        org_id = current_user.organization_id

        # Verify training course exists and belongs to organization
        course = db.query(TrainingProgram).filter(
            TrainingProgram.id == assignment.course_id,
            TrainingProgram.organization_id == org_id
        ).first()

        if not course:
            raise HTTPException(status_code=404, detail="Training course not found")

        assigned_count = 0
        for staff_id in assignment.staff_ids:
            # Verify staff belongs to organization
            staff = db.query(Staff).filter(
                Staff.id == staff_id,
                Staff.organization_id == org_id
            ).first()

            if not staff:
                continue

            # Check if already enrolled
            existing = db.query(TrainingRecord).filter(
                TrainingRecord.staff_id == staff_id,
                TrainingRecord.training_program_id == assignment.course_id
            ).first()

            if existing:
                continue

            # Create training record
            training_record = TrainingRecord(
                staff_id=staff_id,
                training_program_id=assignment.course_id,
                enrollment_date=date.today(),
                due_date=assignment.due_date,
                status="NOT_STARTED",
                notes=assignment.notes
            )

            db.add(training_record)
            assigned_count += 1

        db.commit()

        return {
            "message": f"Training assigned to {assigned_count} staff members",
            "course_id": assignment.course_id,
            "assigned_count": assigned_count
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to assign training: {str(e)}"
        )

@router.post("/notices")
async def create_notice(
    notice_data: NoticeCreateRequest,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Create notice for team
    """
    try:
        org_id = current_user.organization_id

        new_notice = Notice(
            organization_id=org_id,
            title=notice_data.title,
            content=notice_data.content,
            author_id=current_user.id,
            priority=notice_data.priority,
            category=notice_data.category,
            published=True,
            published_at=datetime.utcnow(),
            expires_at=notice_data.expires_at,
            requires_acknowledgment=notice_data.requires_acknowledgment
        )

        db.add(new_notice)
        db.commit()
        db.refresh(new_notice)

        return {
            "message": "Notice created successfully",
            "notice_id": str(new_notice.id),
            "title": new_notice.title
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create notice: {str(e)}"
        )
