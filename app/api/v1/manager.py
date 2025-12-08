from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, timezone, date, timedelta
from typing import Optional, List
from app.core.database import get_db
from app.core.dependencies import get_manager_or_above
from app.services.email_service import EmailService
from app.core.config import settings
from app.models.user import User
from app.models.client import Client, CarePlan
from app.models.staff import (
    Staff, StaffAssignment, TimeOffRequest, TimeOffStatus,
    StaffCertification, TrainingRecord, TrainingProgram, CertificationStatus, TrainingStatus
)
from app.models.scheduling import Shift, Appointment, AppointmentStatus, ShiftExchangeRequest, ShiftExchangeStatus
from app.models.location import Location
from app.schemas.scheduling import (
    ShiftExchangeRequestResponse,
    ShiftExchangeRequestManagerResponse,
    StaffShiftInfo
)
from app.models.incident_report import IncidentReport, IncidentStatusEnum, IncidentSeverityEnum
from app.models.shift_note import ShiftNote
from app.models.task import Task, TaskStatusEnum
from app.models.vitals_log import VitalsLog
from app.models.meal_log import MealLog
from app.models.activity_log import ActivityLog
from app.models.notice import Notice
from app.models.sleep_log import SleepLog
from app.models.bowel_movement_log import BowelMovementLog
from app.schemas.manager import (
    ManagerDashboardOverview,
    TeamStats,
    DocumentationMetrics,
    IncidentMetrics,
    PendingApproval,
    StaffMemberSummary,
    ClientOversightSummary,
    ClientDetailResponse,
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
from pydantic import BaseModel, Field

router = APIRouter()


# Pydantic model for approval counts
class ApprovalCountResponse(BaseModel):
    time_off_pending: int = Field(..., description="Number of pending time-off requests")
    shift_exchange_pending: int = Field(..., description="Number of pending shift exchange requests")
    total_pending: int = Field(..., description="Total pending approvals")


@router.get("/approvals/count", response_model=ApprovalCountResponse)
async def get_approval_counts(
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get counts of pending approvals for sidebar badge indicator.
    Returns counts of pending time-off requests and shift exchange requests.
    """
    org_id = current_user.organization_id

    # Count pending time-off requests
    time_off_pending = db.query(TimeOffRequest).join(Staff).filter(
        Staff.organization_id == org_id,
        TimeOffRequest.status == TimeOffStatus.PENDING
    ).count()

    # Count pending shift exchange requests (pending_manager status)
    shift_exchange_pending = db.query(ShiftExchangeRequest).filter(
        ShiftExchangeRequest.organization_id == org_id,
        ShiftExchangeRequest.status == ShiftExchangeStatus.PENDING_MANAGER
    ).count()

    total_pending = time_off_pending + shift_exchange_pending

    return ApprovalCountResponse(
        time_off_pending=time_off_pending,
        shift_exchange_pending=shift_exchange_pending,
        total_pending=total_pending
    )

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

        # Shift exchange requests pending manager approval
        pending_exchanges = db.query(ShiftExchangeRequest).filter(
            ShiftExchangeRequest.organization_id == org_id,
            ShiftExchangeRequest.status == ShiftExchangeStatus.PENDING_MANAGER
        ).order_by(ShiftExchangeRequest.requested_at).limit(10).all()

        for exchange in pending_exchanges:
            requester_name = exchange.requester_staff.full_name if exchange.requester_staff else "Unknown"
            target_name = exchange.target_staff.full_name if exchange.target_staff else "Unknown"
            pending_approvals.append(PendingApproval(
                id=str(exchange.id),
                type="shift_exchange",
                staff_id=str(exchange.requester_staff_id),
                staff_name=requester_name,
                title="Shift Exchange Request",
                description=f"{requester_name} wants to exchange shifts with {target_name}",
                submitted_at=exchange.requested_at,
                priority="normal",
                metadata={
                    "requester_name": requester_name,
                    "target_name": target_name,
                    "requester_shift_id": str(exchange.requester_shift_id),
                    "target_shift_id": str(exchange.target_shift_id),
                    "peer_accepted_at": str(exchange.peer_responded_at) if exchange.peer_responded_at else None
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

        query = db.query(Staff).join(User, Staff.user_id == User.id).filter(
            Staff.organization_id == org_id,
            Staff.user_id != current_user.id  # Exclude the currently logged in user
        )

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

            # Get next appointment
            next_appointment = db.query(Appointment).filter(
                Appointment.client_id == client.id,
                Appointment.start_datetime > datetime.utcnow(),
                Appointment.status != AppointmentStatus.CANCELLED
            ).order_by(Appointment.start_datetime.asc()).first()

            results.append(ClientOversightSummary(
                id=str(client.id),
                client_id=client.client_id,  # Human readable client code
                user_id=str(client.user_id) if client.user_id else None,
                full_name=f"{client.first_name} {client.last_name}",
                status=client.status,
                location_id=str(client.location_id) if client.location_id else None,
                location_name=location_name,
                assigned_staff_count=assigned_staff_count,
                documentation_completion=documentation_completion,
                risk_level=client.risk_level if hasattr(client, 'risk_level') else None,
                recent_incidents=incidents_count,
                last_service_date=last_shift_note_time,
                next_appointment=next_appointment.start_datetime if next_appointment else None,
                care_plan_status=care_plan_status,
                required_documentation=client.required_documentation if hasattr(client, 'required_documentation') else None
            ))

        return results

    except Exception as e:
        import traceback
        print(f"ERROR in get_clients_oversight: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve clients: {str(e)}"
        )


@router.get("/clients/{client_id}", response_model=ClientDetailResponse)
async def get_client_details(
    client_id: str,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific client
    """
    try:
        org_id = current_user.organization_id

        # Fetch the client
        client = db.query(Client).filter(
            Client.id == client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

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

        # Get location
        location_name = None
        if client.location_id:
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
                loc = db.query(ClientLocation).filter(
                    ClientLocation.id == current_assignment.location_id
                ).first()
                if loc:
                    location_name = loc.name

        # Get next appointment
        next_appointment = db.query(Appointment).filter(
            Appointment.client_id == client.id,
            Appointment.start_datetime > datetime.utcnow(),
            Appointment.status != AppointmentStatus.CANCELLED
        ).order_by(Appointment.start_datetime.asc()).first()

        # Get organization name
        from app.models.user import Organization
        organization = db.query(Organization).filter(
            Organization.id == client.organization_id
        ).first()
        organization_name = organization.name if organization else None

        return ClientDetailResponse(
            id=str(client.id),
            client_id=client.client_id,
            user_id=str(client.user_id) if client.user_id else None,
            full_name=f"{client.first_name} {client.last_name}",
            first_name=client.first_name,
            last_name=client.last_name,
            status=client.status,
            date_of_birth=client.date_of_birth if hasattr(client, 'date_of_birth') else None,
            gender=client.gender if hasattr(client, 'gender') else None,
            email=client.email if hasattr(client, 'email') else None,
            phone=client.phone if hasattr(client, 'phone') else None,
            address=client.address if hasattr(client, 'address') else None,
            emergency_contact_name=client.emergency_contact_name if hasattr(client, 'emergency_contact_name') else None,
            emergency_contact_phone=client.emergency_contact_phone if hasattr(client, 'emergency_contact_phone') else None,
            location_id=str(client.location_id) if client.location_id else None,
            location_name=location_name,
            organization_name=organization_name,
            assigned_staff_count=assigned_staff_count,
            documentation_completion=documentation_completion,
            risk_level=client.risk_level if hasattr(client, 'risk_level') else None,
            recent_incidents=incidents_count,
            last_service_date=last_shift_note_time,
            next_appointment=next_appointment.start_datetime if next_appointment else None,
            care_plan_status=care_plan_status,
            required_documentation=client.required_documentation if hasattr(client, 'required_documentation') else None,
            created_at=client.created_at if hasattr(client, 'created_at') else None
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in get_client_details: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve client details: {str(e)}"
        )


@router.get("/clients/{client_id}/vitals")
async def get_client_vitals(
    client_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get vitals logs for a specific client"""
    try:
        org_id = current_user.organization_id

        # Verify client exists and belongs to organization
        client = db.query(Client).filter(
            Client.id == client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        vitals = db.query(VitalsLog).filter(
            VitalsLog.client_id == client_id,
            VitalsLog.organization_id == org_id
        ).order_by(desc(VitalsLog.recorded_at)).offset(offset).limit(limit).all()

        # Get staff names
        staff_ids = list(set([str(v.staff_id) for v in vitals if v.staff_id]))
        staff_map = {}
        if staff_ids:
            staff_users = db.query(User).filter(User.id.in_(staff_ids)).all()
            staff_map = {str(u.id): u.full_name for u in staff_users}

        return [
            {
                "id": str(v.id),
                "client_id": str(v.client_id),
                "staff_id": str(v.staff_id),
                "staff_name": staff_map.get(str(v.staff_id), "Unknown"),
                "temperature": v.temperature,
                "blood_pressure_systolic": v.blood_pressure_systolic,
                "blood_pressure_diastolic": v.blood_pressure_diastolic,
                "blood_sugar": v.blood_sugar,
                "weight": v.weight,
                "heart_rate": v.heart_rate,
                "oxygen_saturation": v.oxygen_saturation,
                "notes": v.notes,
                "recorded_at": v.recorded_at.isoformat() if v.recorded_at else None,
                "created_at": v.created_at.isoformat() if v.created_at else None
            }
            for v in vitals
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve vitals: {str(e)}")


@router.get("/clients/{client_id}/meals")
async def get_client_meals(
    client_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get meal logs for a specific client"""
    try:
        org_id = current_user.organization_id

        client = db.query(Client).filter(
            Client.id == client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        meals = db.query(MealLog).filter(
            MealLog.client_id == client_id,
            MealLog.organization_id == org_id
        ).order_by(desc(MealLog.meal_date)).offset(offset).limit(limit).all()

        # Get staff names
        staff_ids = list(set([str(m.staff_id) for m in meals if m.staff_id]))
        staff_map = {}
        if staff_ids:
            staff_users = db.query(User).filter(User.id.in_(staff_ids)).all()
            staff_map = {str(u.id): u.full_name for u in staff_users}

        return [
            {
                "id": str(m.id),
                "client_id": str(m.client_id),
                "staff_id": str(m.staff_id) if m.staff_id else None,
                "staff_name": staff_map.get(str(m.staff_id), "Unknown") if m.staff_id else "Unknown",
                "meal_type": m.meal_type.value if m.meal_type else None,
                "meal_time": m.meal_time,
                "food_items": m.food_items,
                "intake_amount": m.intake_amount.value if m.intake_amount else None,
                "percentage_consumed": m.percentage_consumed,
                "calories": m.calories,
                "water_intake_ml": m.water_intake_ml,
                "other_fluids": m.other_fluids,
                "appetite_level": m.appetite_level,
                "assistance_required": m.assistance_required,
                "assistance_type": m.assistance_type,
                "refusals": m.refusals,
                "notes": m.notes,
                "recorded_at": m.meal_date.isoformat() if m.meal_date else None,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in meals
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve meals: {str(e)}")


@router.get("/clients/{client_id}/sleep-logs")
async def get_client_sleep_logs(
    client_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get sleep logs for a specific client"""
    try:
        org_id = current_user.organization_id

        client = db.query(Client).filter(
            Client.id == client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        sleep_logs = db.query(SleepLog).filter(
            SleepLog.client_id == client_id,
            SleepLog.organization_id == org_id
        ).order_by(desc(SleepLog.recorded_at)).offset(offset).limit(limit).all()

        # Get staff names
        staff_ids = list(set([str(s.staff_id) for s in sleep_logs if s.staff_id]))
        staff_map = {}
        if staff_ids:
            staff_users = db.query(User).filter(User.id.in_(staff_ids)).all()
            staff_map = {str(u.id): u.full_name for u in staff_users}

        return [
            {
                "id": str(s.id),
                "client_id": str(s.client_id),
                "staff_id": str(s.staff_id),
                "staff_name": staff_map.get(str(s.staff_id), "Unknown"),
                "shift_date": s.shift_date.isoformat() if s.shift_date else None,
                "sleep_periods": s.sleep_periods,
                "total_sleep_minutes": s.total_sleep_minutes,
                "notes": s.notes,
                "recorded_at": s.recorded_at.isoformat() if s.recorded_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in sleep_logs
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sleep logs: {str(e)}")


@router.get("/clients/{client_id}/bowel-movements")
async def get_client_bowel_movements(
    client_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get bowel movement logs for a specific client"""
    try:
        org_id = current_user.organization_id

        client = db.query(Client).filter(
            Client.id == client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        bowel_logs = db.query(BowelMovementLog).filter(
            BowelMovementLog.client_id == client_id,
            BowelMovementLog.organization_id == org_id
        ).order_by(desc(BowelMovementLog.recorded_at)).offset(offset).limit(limit).all()

        # Get staff names
        staff_ids = list(set([str(b.staff_id) for b in bowel_logs if b.staff_id]))
        staff_map = {}
        if staff_ids:
            staff_users = db.query(User).filter(User.id.in_(staff_ids)).all()
            staff_map = {str(u.id): u.full_name for u in staff_users}

        return [
            {
                "id": str(b.id),
                "client_id": str(b.client_id),
                "staff_id": str(b.staff_id),
                "staff_name": staff_map.get(str(b.staff_id), "Unknown"),
                "stool_type": b.stool_type,
                "stool_color": b.stool_color,
                "additional_information": b.additional_information,
                "recorded_at": b.recorded_at.isoformat() if b.recorded_at else None,
                "created_at": b.created_at.isoformat() if b.created_at else None
            }
            for b in bowel_logs
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve bowel movements: {str(e)}")


@router.get("/clients/{client_id}/activities")
async def get_client_activities(
    client_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get activity logs for a specific client"""
    try:
        org_id = current_user.organization_id

        client = db.query(Client).filter(
            Client.id == client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        activities = db.query(ActivityLog).filter(
            ActivityLog.client_id == client_id,
            ActivityLog.organization_id == org_id
        ).order_by(desc(ActivityLog.activity_date)).offset(offset).limit(limit).all()

        # Get staff names
        staff_ids = list(set([str(a.staff_id) for a in activities if a.staff_id]))
        staff_map = {}
        if staff_ids:
            staff_users = db.query(User).filter(User.id.in_(staff_ids)).all()
            staff_map = {str(u.id): u.full_name for u in staff_users}

        return [
            {
                "id": str(a.id),
                "client_id": str(a.client_id),
                "staff_id": str(a.staff_id) if a.staff_id else None,
                "staff_name": staff_map.get(str(a.staff_id), "Unknown") if a.staff_id else "Unknown",
                "activity_type": a.activity_type.value if a.activity_type else None,
                "activity_name": a.activity_name,
                "duration_minutes": a.duration_minutes,
                "participation_level": a.participation_level.value if a.participation_level else None,
                "mood_before": a.mood_before.value if a.mood_before else None,
                "mood_after": a.mood_after.value if a.mood_after else None,
                "notes": a.staff_notes,
                "recorded_at": a.activity_date.isoformat() if a.activity_date else None,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in activities
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve activities: {str(e)}")


@router.get("/clients/{client_id}/shift-notes")
async def get_client_shift_notes(
    client_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get shift notes for a specific client"""
    try:
        org_id = current_user.organization_id

        client = db.query(Client).filter(
            Client.id == client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        shift_notes = db.query(ShiftNote).filter(
            ShiftNote.client_id == client_id,
            ShiftNote.organization_id == org_id
        ).order_by(desc(ShiftNote.created_at)).offset(offset).limit(limit).all()

        # Get staff names for shift notes
        staff_ids = list(set([str(sn.staff_id) for sn in shift_notes if sn.staff_id]))
        staff_map = {}
        if staff_ids:
            staff_users = db.query(User).filter(User.id.in_(staff_ids)).all()
            staff_map = {str(u.id): u.full_name for u in staff_users}

        return [
            {
                "id": str(sn.id),
                "client_id": str(sn.client_id),
                "staff_id": str(sn.staff_id) if sn.staff_id else None,
                "staff_name": staff_map.get(str(sn.staff_id), "Unknown"),
                "shift_date": sn.shift_date.isoformat() if sn.shift_date else None,
                "shift_time": sn.shift_time if hasattr(sn, 'shift_time') else None,
                "narrative": sn.narrative if hasattr(sn, 'narrative') else None,
                "challenges_faced": sn.challenges_faced if hasattr(sn, 'challenges_faced') else None,
                "support_required": sn.support_required if hasattr(sn, 'support_required') else None,
                "observations": sn.observations if hasattr(sn, 'observations') else None,
                "created_at": sn.created_at.isoformat() if sn.created_at else None
            }
            for sn in shift_notes
        ]
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in get_client_shift_notes: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve shift notes: {str(e)}")


@router.get("/clients/{client_id}/incidents")
async def get_client_incidents(
    client_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get incident reports for a specific client"""
    try:
        org_id = current_user.organization_id

        client = db.query(Client).filter(
            Client.id == client_id,
            Client.organization_id == org_id
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        incidents = db.query(IncidentReport).filter(
            IncidentReport.client_id == client_id,
            IncidentReport.organization_id == org_id
        ).order_by(desc(IncidentReport.incident_date)).offset(offset).limit(limit).all()

        # Get staff names for incidents
        staff_ids = list(set([str(i.staff_id) for i in incidents if i.staff_id]))
        staff_map = {}
        if staff_ids:
            staff_users = db.query(User).filter(User.id.in_(staff_ids)).all()
            staff_map = {str(u.id): u.full_name for u in staff_users}

        return [
            {
                "id": str(i.id),
                "client_id": str(i.client_id),
                "staff_id": str(i.staff_id) if i.staff_id else None,
                "reporter_name": staff_map.get(str(i.staff_id), "Unknown") if i.staff_id else "Unknown",
                "incident_date": i.incident_date.isoformat() if i.incident_date else None,
                "incident_time": i.incident_time,
                "incident_type": i.incident_type.value if i.incident_type else None,
                "severity": i.severity.value if i.severity else None,
                "status": i.status.value if i.status else None,
                "description": i.description,
                "action_taken": i.action_taken,
                "location": i.location,
                "witnesses": i.witnesses,
                "follow_up_required": i.follow_up_required,
                "follow_up_notes": i.follow_up_notes,
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None
            }
            for i in incidents
        ]
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in get_client_incidents: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve incidents: {str(e)}")


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
                total_hours=float(request.total_hours) if request.total_hours else 0.0,
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

        # Check for approval (handle both uppercase and lowercase values)
        is_approved = action.action.value.upper() == "APPROVED"
        if is_approved:
            time_off_request.status = TimeOffStatus.APPROVED
        else:
            time_off_request.status = TimeOffStatus.DENIED
            time_off_request.denial_reason = action.notes

        time_off_request.approved_by = current_user.id
        time_off_request.approved_date = datetime.utcnow()

        db.commit()

        # Send email notification to the staff member
        try:
            # Reload with staff relationship
            time_off_request = db.query(TimeOffRequest).options(
                joinedload(TimeOffRequest.staff).joinedload(Staff.user)
            ).filter(TimeOffRequest.id == request_id).first()

            staff_member = time_off_request.staff
            staff_user = staff_member.user
            manager_name = f"{current_user.first_name} {current_user.last_name}"

            # Format dates
            start_date_str = time_off_request.start_date.strftime("%a, %b %d, %Y")
            end_date_str = time_off_request.end_date.strftime("%a, %b %d, %Y")
            total_hours_str = str(time_off_request.total_hours)
            request_type_str = time_off_request.request_type.value.replace("_", " ").title()

            if is_approved:
                await EmailService.send_time_off_approved_email(
                    to_email=staff_user.email,
                    staff_name=staff_member.full_name,
                    manager_name=manager_name,
                    request_type=request_type_str,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    total_hours=total_hours_str,
                    manager_notes=action.notes
                )
            else:
                await EmailService.send_time_off_denied_email(
                    to_email=staff_user.email,
                    staff_name=staff_member.full_name,
                    manager_name=manager_name,
                    request_type=request_type_str,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    total_hours=total_hours_str,
                    denial_reason=action.notes
                )

            import logging
            logging.info(f"Time-off {'approved' if is_approved else 'denied'} email sent to {staff_user.email}")

        except Exception as email_error:
            import logging
            logging.error(f"Failed to send time-off decision email: {str(email_error)}")
            # Don't fail the request if email fails

        return {
            "message": f"Time off request {'approved' if is_approved else 'denied'}",
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


# ============================================================================
# SHIFT EXCHANGE MANAGEMENT ENDPOINTS
# ============================================================================

def _build_staff_shift_info(shift: Shift, staff: Staff, db: Session) -> StaffShiftInfo:
    """Helper function to build StaffShiftInfo from shift and staff objects"""
    client_name = None
    if shift.client:
        client_name = f"{shift.client.first_name} {shift.client.last_name}"

    location_name = None
    if shift.location_id:
        location = db.query(Location).filter(Location.id == shift.location_id).first()
        if location:
            location_name = location.name

    return StaffShiftInfo(
        staff_id=staff.id,
        staff_name=staff.full_name,
        staff_email=staff.user.email if staff.user else None,
        shift_id=shift.id,
        shift_date=shift.shift_date,
        start_time=shift.start_time,
        end_time=shift.end_time,
        shift_type=shift.shift_type.value if hasattr(shift.shift_type, 'value') else str(shift.shift_type),
        client_name=client_name,
        location_name=location_name
    )


def _build_exchange_response(exchange: ShiftExchangeRequest, db: Session) -> ShiftExchangeRequestResponse:
    """Helper function to build ShiftExchangeRequestResponse from exchange request"""
    requester_info = _build_staff_shift_info(exchange.requester_shift, exchange.requester_staff, db)
    target_info = _build_staff_shift_info(exchange.target_shift, exchange.target_staff, db)

    manager_name = None
    if exchange.manager_responded_by:
        from app.models.user import User
        manager = db.query(User).filter(User.id == exchange.manager_responded_by).first()
        if manager:
            manager_name = f"{manager.first_name} {manager.last_name}"

    return ShiftExchangeRequestResponse(
        id=exchange.id,
        organization_id=exchange.organization_id,
        status=exchange.status,
        reason=exchange.reason,
        requester=requester_info,
        target=target_info,
        requested_at=exchange.requested_at,
        peer_responded_at=exchange.peer_responded_at,
        peer_response_notes=exchange.peer_response_notes,
        manager_responded_by=exchange.manager_responded_by,
        manager_responded_at=exchange.manager_responded_at,
        manager_response_notes=exchange.manager_response_notes,
        manager_name=manager_name,
        created_at=exchange.created_at,
        updated_at=exchange.updated_at
    )


@router.get("/shift-exchange-requests", response_model=List[ShiftExchangeRequestResponse])
async def get_shift_exchange_requests(
    status: Optional[str] = Query(None, description="Filter by status (pending_peer, pending_manager, approved, denied, cancelled)"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get shift exchange requests for the organization.
    Managers typically filter by 'pending_manager' to see requests awaiting their approval.
    """
    try:
        org_id = current_user.organization_id

        query = db.query(ShiftExchangeRequest).options(
            joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
            joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
            joinedload(ShiftExchangeRequest.requester_shift).joinedload(Shift.client),
            joinedload(ShiftExchangeRequest.target_shift).joinedload(Shift.client)
        ).filter(
            ShiftExchangeRequest.organization_id == org_id
        )

        if status:
            try:
                status_enum = ShiftExchangeStatus(status.lower())
                query = query.filter(ShiftExchangeRequest.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        exchanges = query.order_by(ShiftExchangeRequest.requested_at.desc()).offset(offset).limit(limit).all()

        return [_build_exchange_response(exchange, db) for exchange in exchanges]

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in get_shift_exchange_requests: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shift exchange requests: {str(e)}"
        )


@router.get("/shift-exchange-requests/pending", response_model=List[ShiftExchangeRequestResponse])
async def get_pending_shift_exchange_requests(
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get shift exchange requests pending manager approval.
    Convenience endpoint that filters to only show requests in PENDING_MANAGER status.
    """
    try:
        org_id = current_user.organization_id

        query = db.query(ShiftExchangeRequest).options(
            joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
            joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
            joinedload(ShiftExchangeRequest.requester_shift).joinedload(Shift.client),
            joinedload(ShiftExchangeRequest.target_shift).joinedload(Shift.client)
        ).filter(
            ShiftExchangeRequest.organization_id == org_id,
            ShiftExchangeRequest.status == ShiftExchangeStatus.PENDING_MANAGER
        )

        exchanges = query.order_by(ShiftExchangeRequest.requested_at.desc()).offset(offset).limit(limit).all()

        return [_build_exchange_response(exchange, db) for exchange in exchanges]

    except Exception as e:
        import traceback
        print(f"ERROR in get_pending_shift_exchange_requests: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pending shift exchange requests: {str(e)}"
        )


@router.get("/shift-exchange-requests/{exchange_id}", response_model=ShiftExchangeRequestResponse)
async def get_shift_exchange_request(
    exchange_id: str,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Get a specific shift exchange request by ID
    """
    try:
        org_id = current_user.organization_id

        exchange = db.query(ShiftExchangeRequest).options(
            joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
            joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
            joinedload(ShiftExchangeRequest.requester_shift).joinedload(Shift.client),
            joinedload(ShiftExchangeRequest.target_shift).joinedload(Shift.client)
        ).filter(
            ShiftExchangeRequest.id == exchange_id,
            ShiftExchangeRequest.organization_id == org_id
        ).first()

        if not exchange:
            raise HTTPException(status_code=404, detail="Shift exchange request not found")

        return _build_exchange_response(exchange, db)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shift exchange request: {str(e)}"
        )


@router.post("/shift-exchange-requests/{exchange_id}/approve")
async def approve_shift_exchange_request(
    exchange_id: str,
    action: ShiftExchangeRequestManagerResponse,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Approve a shift exchange request (Step 3 of 3-step workflow).
    Only requests in PENDING_MANAGER status can be approved.
    Upon approval, the shifts are swapped between the two staff members.
    """
    try:
        org_id = current_user.organization_id

        exchange = db.query(ShiftExchangeRequest).options(
            joinedload(ShiftExchangeRequest.requester_shift),
            joinedload(ShiftExchangeRequest.target_shift)
        ).filter(
            ShiftExchangeRequest.id == exchange_id,
            ShiftExchangeRequest.organization_id == org_id
        ).first()

        if not exchange:
            raise HTTPException(status_code=404, detail="Shift exchange request not found")

        if exchange.status != ShiftExchangeStatus.PENDING_MANAGER:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve request in {exchange.status.value} status. Only requests in pending_manager status can be approved."
            )

        # Perform the shift swap
        requester_shift = exchange.requester_shift
        target_shift = exchange.target_shift

        # Swap staff assignments
        temp_staff_id = requester_shift.staff_id
        requester_shift.staff_id = target_shift.staff_id
        target_shift.staff_id = temp_staff_id

        # Update exchange status
        exchange.status = ShiftExchangeStatus.APPROVED
        exchange.manager_responded_by = current_user.id
        exchange.manager_responded_at = datetime.utcnow()
        exchange.manager_response_notes = action.notes

        db.commit()

        # Send email notifications to both staff members
        try:
            # Reload exchange with all relationships
            exchange = db.query(ShiftExchangeRequest).options(
                joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
                joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
                joinedload(ShiftExchangeRequest.requester_shift).joinedload(Shift.client),
                joinedload(ShiftExchangeRequest.target_shift).joinedload(Shift.client)
            ).filter(ShiftExchangeRequest.id == exchange_id).first()

            manager_name = f"{current_user.first_name} {current_user.last_name}"
            requester_staff = exchange.requester_staff
            target_staff_obj = exchange.target_staff
            requester_shift_obj = exchange.requester_shift
            target_shift_obj = exchange.target_shift

            # After swap: requester now has target's original shift
            requester_new_shift_date = target_shift_obj.shift_date.strftime("%a, %b %d, %Y")
            requester_new_shift_time = f"{target_shift_obj.start_time.strftime('%I:%M %p')} - {target_shift_obj.end_time.strftime('%I:%M %p')}"
            requester_new_client = None
            if target_shift_obj.client:
                requester_new_client = f"{target_shift_obj.client.first_name} {target_shift_obj.client.last_name}"

            # After swap: target now has requester's original shift
            target_new_shift_date = requester_shift_obj.shift_date.strftime("%a, %b %d, %Y")
            target_new_shift_time = f"{requester_shift_obj.start_time.strftime('%I:%M %p')} - {requester_shift_obj.end_time.strftime('%I:%M %p')}"
            target_new_client = None
            if requester_shift_obj.client:
                target_new_client = f"{requester_shift_obj.client.first_name} {requester_shift_obj.client.last_name}"

            # Email requester about their new shift
            await EmailService.send_shift_exchange_approved_email(
                to_email=requester_staff.user.email,
                recipient_name=requester_staff.full_name,
                manager_name=manager_name,
                new_shift_date=requester_new_shift_date,
                new_shift_time=requester_new_shift_time,
                new_client=requester_new_client,
                manager_notes=action.notes
            )

            # Email target about their new shift
            await EmailService.send_shift_exchange_approved_email(
                to_email=target_staff_obj.user.email,
                recipient_name=target_staff_obj.full_name,
                manager_name=manager_name,
                new_shift_date=target_new_shift_date,
                new_shift_time=target_new_shift_time,
                new_client=target_new_client,
                manager_notes=action.notes
            )

        except Exception as email_error:
            import logging
            logging.error(f"Failed to send shift exchange approved emails: {str(email_error)}")
            # Don't fail the request if email fails

        return {
            "message": "Shift exchange approved successfully",
            "exchange_id": str(exchange.id),
            "status": exchange.status.value,
            "requester_shift_id": str(requester_shift.id),
            "target_shift_id": str(target_shift.id)
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        print(f"ERROR in approve_shift_exchange_request: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve shift exchange request: {str(e)}"
        )


@router.post("/shift-exchange-requests/{exchange_id}/deny")
async def deny_shift_exchange_request(
    exchange_id: str,
    action: ShiftExchangeRequestManagerResponse,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Deny a shift exchange request.
    Only requests in PENDING_MANAGER status can be denied by manager.
    """
    try:
        org_id = current_user.organization_id

        exchange = db.query(ShiftExchangeRequest).filter(
            ShiftExchangeRequest.id == exchange_id,
            ShiftExchangeRequest.organization_id == org_id
        ).first()

        if not exchange:
            raise HTTPException(status_code=404, detail="Shift exchange request not found")

        if exchange.status != ShiftExchangeStatus.PENDING_MANAGER:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot deny request in {exchange.status.value} status. Only requests in pending_manager status can be denied."
            )

        # Update exchange status
        exchange.status = ShiftExchangeStatus.DENIED
        exchange.manager_responded_by = current_user.id
        exchange.manager_responded_at = datetime.utcnow()
        exchange.manager_response_notes = action.notes

        db.commit()

        # Send email notifications to both staff members
        try:
            # Reload exchange with all relationships
            exchange = db.query(ShiftExchangeRequest).options(
                joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
                joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
                joinedload(ShiftExchangeRequest.requester_shift).joinedload(Shift.client),
                joinedload(ShiftExchangeRequest.target_shift).joinedload(Shift.client)
            ).filter(ShiftExchangeRequest.id == exchange_id).first()

            manager_name = f"{current_user.first_name} {current_user.last_name}"
            requester_staff = exchange.requester_staff
            target_staff_obj = exchange.target_staff
            requester_shift_obj = exchange.requester_shift
            target_shift_obj = exchange.target_shift

            # Format shift details for requester
            requester_shift_date = requester_shift_obj.shift_date.strftime("%a, %b %d, %Y")
            requester_shift_time = f"{requester_shift_obj.start_time.strftime('%I:%M %p')} - {requester_shift_obj.end_time.strftime('%I:%M %p')}"
            requester_client = None
            if requester_shift_obj.client:
                requester_client = f"{requester_shift_obj.client.first_name} {requester_shift_obj.client.last_name}"

            # Format shift details for target
            target_shift_date = target_shift_obj.shift_date.strftime("%a, %b %d, %Y")
            target_shift_time = f"{target_shift_obj.start_time.strftime('%I:%M %p')} - {target_shift_obj.end_time.strftime('%I:%M %p')}"
            target_client = None
            if target_shift_obj.client:
                target_client = f"{target_shift_obj.client.first_name} {target_shift_obj.client.last_name}"

            # Email requester about denial (their shift stays the same)
            await EmailService.send_shift_exchange_denied_by_manager_email(
                to_email=requester_staff.user.email,
                recipient_name=requester_staff.full_name,
                manager_name=manager_name,
                your_shift_date=requester_shift_date,
                your_shift_time=requester_shift_time,
                your_client=requester_client,
                manager_notes=action.notes
            )

            # Email target about denial (their shift stays the same)
            await EmailService.send_shift_exchange_denied_by_manager_email(
                to_email=target_staff_obj.user.email,
                recipient_name=target_staff_obj.full_name,
                manager_name=manager_name,
                your_shift_date=target_shift_date,
                your_shift_time=target_shift_time,
                your_client=target_client,
                manager_notes=action.notes
            )

        except Exception as email_error:
            import logging
            logging.error(f"Failed to send shift exchange denied emails: {str(email_error)}")
            # Don't fail the request if email fails

        return {
            "message": "Shift exchange denied",
            "exchange_id": str(exchange.id),
            "status": exchange.status.value
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deny shift exchange request: {str(e)}"
        )
