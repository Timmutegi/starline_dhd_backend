from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, date, timedelta
from app.core.database import get_db
from app.models.user import User
from app.models.staff import Staff
from app.models.client import Client
from app.models.scheduling import (
    Schedule, Shift, ShiftTemplate, ShiftAssignment, StaffAvailability,
    TimeOffScheduling, CoverageRequest, ShiftSwap, ScheduleConflict,
    ScheduleStatus, ShiftStatus, RequestStatus, ConflictType, ConflictSeverity
)
from app.middleware.auth import get_current_user, require_permission
from app.schemas.scheduling import (
    # Schedule schemas
    ScheduleCreate, ScheduleUpdate, ScheduleResponse,
    # Shift schemas
    ShiftCreate, ShiftUpdate, ShiftResponse, ShiftBulkCreate,
    # Shift Template schemas
    ShiftTemplateCreate, ShiftTemplateUpdate, ShiftTemplateResponse,
    # Shift Assignment schemas
    ShiftAssignmentCreate, ShiftAssignmentResponse,
    # Staff Availability schemas
    StaffAvailabilityCreate, StaffAvailabilityUpdate, StaffAvailabilityResponse,
    StaffAvailabilityBulkUpdate,
    # Coverage schemas
    CoverageRequestCreate, CoverageRequestUpdate, CoverageRequestResponse,
    # Conflict schemas
    ScheduleConflictResponse,
    # Reports
    ScheduleUtilizationReport, PaginatedResponse
)
from app.schemas.auth import MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Current Shift Endpoint for DSPs

@router.get("/shifts/me/current")
async def get_current_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current active shift for the logged-in DSP staff member.
    Only returns shift if current time is within the shift's start and end times.
    """
    import pytz
    from app.models.user import Organization

    logger.info(f"Fetching current shift for user {current_user.id} ({current_user.email})")

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        logger.warning(f"No staff record found for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    logger.info(f"Found staff record: {staff.id}")

    # Get user's timezone (user timezone > organization timezone > UTC)
    # Safely get organization timezone
    org_timezone = None
    if current_user.organization_id:
        organization = db.query(Organization).filter(
            Organization.id == current_user.organization_id
        ).first()
        if organization:
            org_timezone = organization.timezone

    user_timezone_str = current_user.timezone or org_timezone or "UTC"
    try:
        user_timezone = pytz.timezone(user_timezone_str)
        logger.info(f"Using timezone: {user_timezone_str}")
    except Exception as e:
        logger.error(f"Invalid timezone '{user_timezone_str}', falling back to UTC: {str(e)}")
        user_timezone = pytz.UTC
        user_timezone_str = "UTC"

    # Get today's date and current time in user's timezone
    now_utc = datetime.now(timezone.utc).replace(tzinfo=pytz.UTC)
    now_user_tz = now_utc.astimezone(user_timezone)
    today = now_user_tz.date()
    current_time = now_user_tz.time()

    logger.info(
        f"Current time - UTC: {now_utc}, "
        f"User TZ ({user_timezone_str}): {now_user_tz}, "
        f"Date: {today}, Time: {current_time}"
    )

    # Extract just the time component for comparison (shift times are stored as Time objects)
    current_time_only = current_time.time() if isinstance(current_time, datetime) else current_time

    # Query ALL shifts for today first (for debugging)
    all_today_shifts = db.query(Shift).filter(
        Shift.staff_id == staff.id,
        Shift.shift_date == today
    ).all()

    logger.info(f"Total shifts for today: {len(all_today_shifts)}")
    for shift in all_today_shifts:
        is_active = shift.start_time <= current_time_only <= shift.end_time
        logger.info(
            f"Shift {shift.id}: {shift.start_time} - {shift.end_time}, "
            f"Status: {shift.status}, Client: {shift.client_id}, "
            f"Current time: {current_time_only}, Active: {is_active}"
        )

    # Get the current active shift (time is within shift window)
    current_shift = db.query(Shift).options(
        joinedload(Shift.schedule),
        joinedload(Shift.client)  # Load client relationship
    ).filter(
        Shift.staff_id == staff.id,
        Shift.shift_date == today,
        Shift.start_time <= current_time_only,
        Shift.end_time >= current_time_only,
        Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.IN_PROGRESS])
    ).first()

    if not current_shift:
        logger.info("No active shift found for current time")

        # Find next upcoming shift today
        next_shift = db.query(Shift).filter(
            Shift.staff_id == staff.id,
            Shift.shift_date == today,
            Shift.start_time > current_time_only,
            Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.CONFIRMED])
        ).order_by(Shift.start_time).first()

        message = "No active shift at this time"
        if next_shift:
            message = f"Next shift starts at {next_shift.start_time.strftime('%I:%M %p')}"
            logger.info(f"Next shift found: {next_shift.id} at {next_shift.start_time}")

        return {
            "has_active_shift": False,
            "message": message
        }

    logger.info(f"Found active shift: {current_shift.id}")

    # Get client assignment - check direct client_id field first (used by seed data)
    from app.models.staff import StaffAssignment
    from app.models.client import ClientLocation
    from app.models.scheduling import ShiftAssignment as ShiftClientAssignment
    from app.models.client import Client

    client_id = None
    client = None
    assignment = None

    # First priority: Check direct client_id field on shift
    if current_shift.client_id:
        client_id = current_shift.client_id
        client = current_shift.client  # Use the pre-loaded relationship
        logger.info(f"Found client from direct shift.client_id: {client.full_name if client else client_id}")

        # Get staff assignment for this client
        assignment = db.query(StaffAssignment).filter(
            StaffAssignment.staff_id == staff.id,
            StaffAssignment.client_id == client_id,
            StaffAssignment.is_active == True
        ).first()

    # Second priority: Check shift assignments table
    if not client_id:
        shift_client_assignment = db.query(ShiftClientAssignment).options(
            joinedload(ShiftClientAssignment.client)
        ).filter(
            ShiftClientAssignment.shift_id == current_shift.id
        ).first()

        if shift_client_assignment:
            client_id = shift_client_assignment.client_id
            client = shift_client_assignment.client
            logger.info(f"Found client from ShiftAssignment: {client.full_name if client else client_id}")

    # Third priority: Get the first active staff assignment
    if not client_id:
        assignment = db.query(StaffAssignment).options(
            joinedload(StaffAssignment.client)
        ).filter(
            StaffAssignment.staff_id == staff.id,
            StaffAssignment.is_active == True
        ).first()

        if assignment and assignment.client:
            client_id = assignment.client_id
            client = assignment.client
            logger.info(f"Found client from StaffAssignment: {client.full_name if client else client_id}")

    # Get location - Priority order:
    # 1. Location from the shift itself
    # 2. Location from the client's direct location_id field
    # 3. Location from client's current assignment (legacy)
    from app.models.client import ClientAssignment, ClientLocation
    from app.models.location import Location

    location_name = "Location Not Set"
    location_address = ""
    location = None

    # First priority: Check shift's location_id
    if current_shift.location_id:
        location = db.query(Location).filter(
            Location.id == current_shift.location_id
        ).first()
        if location:
            location_name = location.name
            location_address = location.address or ""
            logger.info(f"Found location from shift: {location_name}")

    # Second priority: Check client's direct location_id
    if not location and client and client.location_id:
        location = db.query(Location).filter(
            Location.id == client.location_id
        ).first()
        if location:
            location_name = location.name
            location_address = location.address or ""
            logger.info(f"Found location from client: {location_name}")

    # Third priority: Check client assignment (legacy)
    if not location and client_id:
        client_assignment = db.query(ClientAssignment).options(
            joinedload(ClientAssignment.location)
        ).filter(
            ClientAssignment.client_id == client_id,
            ClientAssignment.is_current == True
        ).first()

        if client_assignment and client_assignment.location:
            location_name = client_assignment.location.name
            location_address = client_assignment.location.address
            logger.info(f"Found location from client assignment: {location_name}")

    # Get tasks for this shift
    from app.models.task import Task, TaskStatusEnum

    tasks_query = db.query(Task).filter(
        Task.assigned_to == current_user.id,
        Task.client_id == client_id if client_id else None,
        Task.due_date == today
    ) if client_id else db.query(Task).filter(Task.id == None)  # Empty query if no client

    total_tasks = tasks_query.count()
    completed_tasks = tasks_query.filter(Task.status == TaskStatusEnum.COMPLETED).count()

    # Calculate time on shift
    from app.models.scheduling import TimeClockEntry, TimeEntryType

    clock_in_entry = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff.id,
        TimeClockEntry.shift_id == current_shift.id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    time_on_shift = None
    clock_in_time = None
    clock_in_time_formatted = None
    if clock_in_entry:
        # Convert UTC clock in time to user's timezone
        # Ensure entry_datetime is timezone-aware (assume it's stored as UTC)
        if clock_in_entry.entry_datetime.tzinfo is None:
            clock_in_time_utc = clock_in_entry.entry_datetime.replace(tzinfo=pytz.UTC)
        else:
            clock_in_time_utc = clock_in_entry.entry_datetime

        clock_in_time = clock_in_time_utc.astimezone(user_timezone)
        clock_in_time_formatted = clock_in_time.strftime("%I:%M %p")

        # Calculate time elapsed - ensure both datetimes are timezone-aware
        now_utc = datetime.now(timezone.utc).replace(tzinfo=pytz.UTC)
        elapsed = now_utc - clock_in_time_utc
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        time_on_shift = f"{hours}h {minutes}m"

    # Check documentation status
    documentation_status = {}
    can_clock_out = True
    missing_documents = []

    if current_shift.client_id and current_shift.required_documentation:
        required_docs = current_shift.required_documentation

        for doc_type in required_docs:
            is_submitted = False

            if doc_type == "vitals_log":
                from app.models.vitals_log import VitalsLog
                vitals = db.query(VitalsLog).filter(
                    VitalsLog.client_id == current_shift.client_id,
                    VitalsLog.created_at >= datetime.combine(current_shift.shift_date, current_shift.start_time or datetime.min.time()),
                    VitalsLog.created_at <= datetime.now(timezone.utc)
                ).first()
                is_submitted = vitals is not None

            elif doc_type == "shift_note":
                from app.models.shift_note import ShiftNote
                note = db.query(ShiftNote).filter(
                    ShiftNote.client_id == current_shift.client_id,
                    ShiftNote.shift_date == current_shift.shift_date
                ).first()
                is_submitted = note is not None

            elif doc_type == "meal_log":
                from app.models.meal_log import MealLog
                meal = db.query(MealLog).filter(
                    MealLog.client_id == current_shift.client_id,
                    MealLog.meal_date == current_shift.shift_date
                ).first()
                is_submitted = meal is not None

            elif doc_type == "incident_report":
                from app.models.incident_report import IncidentReport
                incident = db.query(IncidentReport).filter(
                    IncidentReport.client_id == current_shift.client_id,
                    IncidentReport.incident_date == current_shift.shift_date
                ).first()
                is_submitted = incident is not None

            elif doc_type == "activity_log":
                from app.models.activity_log import ActivityLog
                activity = db.query(ActivityLog).filter(
                    ActivityLog.client_id == current_shift.client_id,
                    ActivityLog.activity_date == current_shift.shift_date
                ).first()
                is_submitted = activity is not None

            documentation_status[doc_type] = {
                "required": True,
                "submitted": is_submitted
            }

            if not is_submitted:
                missing_documents.append(doc_type)

        can_clock_out = len(missing_documents) == 0

    return {
        "has_active_shift": True,
        "shift": {
            "id": str(current_shift.id),
            "shift_date": current_shift.shift_date.isoformat(),
            "start_time": current_shift.start_time.strftime("%I:%M %p") if current_shift.start_time else None,
            "end_time": current_shift.end_time.strftime("%I:%M %p") if current_shift.end_time else None,
            "status": current_shift.status.value,
            "notes": current_shift.notes,
            "required_documentation": current_shift.required_documentation or []
        },
        "client": {
            "id": str(client.id) if client else None,
            "full_name": client.full_name if client else "Unknown Client",
            "client_id": client.client_id if client else None,
            "special_needs": client.primary_diagnosis if client else None
        },
        "location": {
            "name": location_name,
            "address": location_address
        },
        "time_tracking": {
            "time_on_shift": time_on_shift,
            "clock_in_time": clock_in_time_formatted,
            "is_clocked_in": clock_in_time is not None
        },
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "pending": total_tasks - completed_tasks
        },
        "documentation": {
            "status": documentation_status,
            "can_clock_out": can_clock_out,
            "missing_documents": missing_documents
        }
    }


@router.get("/shifts/me")
async def get_my_shifts(
    start_date: Optional[date] = Query(None, description="Filter shifts from this date"),
    end_date: Optional[date] = Query(None, description="Filter shifts until this date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all shifts for the logged-in DSP staff member."""
    from app.models.staff import StaffAssignment
    from app.models.client import ClientAssignment, ClientLocation
    from app.models.scheduling import ShiftAssignment as ShiftClientAssignment

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Build query for shifts with client relationship pre-loaded
    query = db.query(Shift).options(
        joinedload(Shift.schedule),
        joinedload(Shift.client)  # Pre-load client relationship
    ).filter(
        Shift.staff_id == staff.id
    )

    # Apply date filters
    if start_date:
        query = query.filter(Shift.shift_date >= start_date)
    else:
        # Default to showing shifts from today onwards
        query = query.filter(Shift.shift_date >= date.today())

    if end_date:
        query = query.filter(Shift.shift_date <= end_date)

    # Order by date and time
    shifts = query.order_by(Shift.shift_date, Shift.start_time).all()

    # Format shift data
    shifts_data = []
    for shift in shifts:
        # Priority 1: Check direct client_id field on shift (used by seed data)
        client = None
        if shift.client_id:
            client = shift.client  # Use pre-loaded relationship

        # Priority 2: Check shift assignments table
        if not client:
            shift_client_assignment = db.query(ShiftClientAssignment).options(
                joinedload(ShiftClientAssignment.client)
            ).filter(
                ShiftClientAssignment.shift_id == shift.id
            ).first()

            if shift_client_assignment:
                client = shift_client_assignment.client

        # Priority 3: Fall back to first active staff assignment
        if not client:
            assignment = db.query(StaffAssignment).options(
                joinedload(StaffAssignment.client)
            ).filter(
                StaffAssignment.staff_id == staff.id,
                StaffAssignment.is_active == True
            ).first()

            if assignment:
                client = assignment.client

        # Get location - check multiple sources
        location_name = ""
        if client:
            # Priority 1: Check ClientAssignment for current location
            client_assignment = db.query(ClientAssignment).options(
                joinedload(ClientAssignment.location)
            ).filter(
                ClientAssignment.client_id == client.id,
                ClientAssignment.is_current == True
            ).first()

            if client_assignment and client_assignment.location:
                location_name = client_assignment.location.name

            # Priority 2: Fall back to client's direct location_id (references locations table)
            if not location_name and client.location_id:
                from app.models.location import Location
                direct_location = db.query(Location).filter(
                    Location.id == client.location_id
                ).first()
                if direct_location:
                    location_name = direct_location.name

        # Determine activity type based on shift time or default to "Client Shift"
        activity_type = "Client Shift"

        shifts_data.append({
            "date": shift.shift_date.strftime("%a, %b %d") if shift.shift_date else "",
            "time": f"{shift.start_time.strftime('%I:%M %p') if shift.start_time else ''} - {shift.end_time.strftime('%I:%M %p') if shift.end_time else ''}",
            "client_name": client.full_name if client else "No Client Assigned",
            "location": location_name or "Location Not Set",
            "activity_type": activity_type,
            "status": shift.status.value.capitalize() if shift.status else "Scheduled",
            "shift_id": str(shift.id),
            "shift_date_iso": shift.shift_date.isoformat() if shift.shift_date else "",
            "start_time": shift.start_time.strftime("%H:%M:%S") if shift.start_time else "",
            "end_time": shift.end_time.strftime("%H:%M:%S") if shift.end_time else ""
        })

    return {
        "shifts": shifts_data,
        "total": len(shifts_data)
    }


# Schedule Management Endpoints

@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    schedule_data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "create"))
):
    """Create a new schedule."""
    try:
        new_schedule = Schedule(
            organization_id=schedule_data.organization_id,
            schedule_name=schedule_data.schedule_name,
            schedule_type=schedule_data.schedule_type,
            start_date=schedule_data.start_date,
            end_date=schedule_data.end_date,
            notes=schedule_data.notes,
            created_by=current_user.id
        )

        db.add(new_schedule)
        db.commit()
        db.refresh(new_schedule)

        return ScheduleResponse.model_validate(new_schedule)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating schedule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create schedule"
        )

@router.get("/schedules", response_model=PaginatedResponse)
async def get_schedules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[ScheduleStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get list of schedules with pagination and filtering."""

    query = db.query(Schedule).filter(
        Schedule.organization_id == current_user.organization_id
    )

    # Apply filters
    if status_filter:
        query = query.filter(Schedule.status == status_filter)

    if start_date:
        query = query.filter(Schedule.start_date >= start_date)

    if end_date:
        query = query.filter(Schedule.end_date <= end_date)

    # Get total count
    total = query.count()

    # Apply pagination
    schedules = query.offset(skip).limit(limit).all()

    pages = (total + limit - 1) // limit

    return PaginatedResponse(
        items=[ScheduleResponse.model_validate(s) for s in schedules],
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=pages
    )

@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get schedule details."""

    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    return ScheduleResponse.model_validate(schedule)

@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    schedule_update: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Update schedule."""

    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    # Update fields
    update_data = schedule_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    schedule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(schedule)

    return ScheduleResponse.model_validate(schedule)

@router.post("/schedules/{schedule_id}/publish", response_model=MessageResponse)
async def publish_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Publish a schedule."""

    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    if schedule.status == ScheduleStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schedule is already published"
        )

    schedule.status = ScheduleStatus.PUBLISHED
    schedule.approved_by = current_user.id
    schedule.approved_at = datetime.now(timezone.utc)
    schedule.updated_at = datetime.now(timezone.utc)

    db.commit()

    return MessageResponse(
        message="Schedule published successfully",
        success=True
    )

@router.post("/schedules/{schedule_id}/copy", response_model=ScheduleResponse)
async def copy_schedule(
    schedule_id: UUID,
    new_start_date: date = Query(..., description="Start date for the new schedule"),
    new_end_date: date = Query(..., description="End date for the new schedule"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "create"))
):
    """Copy an existing schedule to new dates."""

    original_schedule = db.query(Schedule).options(
        joinedload(Schedule.shifts)
    ).filter(
        Schedule.id == schedule_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not original_schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original schedule not found"
        )

    # Create new schedule
    new_schedule = Schedule(
        organization_id=original_schedule.organization_id,
        schedule_name=f"{original_schedule.schedule_name} (Copy)",
        schedule_type=original_schedule.schedule_type,
        start_date=new_start_date,
        end_date=new_end_date,
        notes=original_schedule.notes,
        created_by=current_user.id
    )

    db.add(new_schedule)
    db.flush()  # Get the new schedule ID

    # Copy shifts with date adjustments
    date_offset = (new_start_date - original_schedule.start_date).days

    for original_shift in original_schedule.shifts:
        new_shift_date = original_shift.shift_date + timedelta(days=date_offset)

        # Only copy if the new date is within the new schedule range
        if new_start_date <= new_shift_date <= new_end_date:
            new_shift = Shift(
                schedule_id=new_schedule.id,
                staff_id=original_shift.staff_id,
                location_id=original_shift.location_id,
                shift_date=new_shift_date,
                start_time=original_shift.start_time,
                end_time=original_shift.end_time,
                break_start=original_shift.break_start,
                break_end=original_shift.break_end,
                meal_start=original_shift.meal_start,
                meal_end=original_shift.meal_end,
                shift_type=original_shift.shift_type,
                is_mandatory=original_shift.is_mandatory,
                notes=original_shift.notes
            )
            db.add(new_shift)

    db.commit()
    db.refresh(new_schedule)

    return ScheduleResponse.model_validate(new_schedule)

# Shift Management Endpoints

@router.post("/shifts", response_model=ShiftResponse)
async def create_shift(
    shift_data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "create"))
):
    """Create a new shift."""

    # Validate schedule exists and belongs to organization
    schedule = db.query(Schedule).filter(
        Schedule.id == shift_data.schedule_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    # Validate staff exists and belongs to organization
    staff = db.query(Staff).filter(
        Staff.id == shift_data.staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    try:
        new_shift = Shift(
            schedule_id=shift_data.schedule_id,
            staff_id=shift_data.staff_id,
            client_id=shift_data.client_id,  # Primary client for this shift
            location_id=shift_data.location_id,
            shift_date=shift_data.shift_date,
            start_time=shift_data.start_time,
            end_time=shift_data.end_time,
            break_start=shift_data.break_start,
            break_end=shift_data.break_end,
            meal_start=shift_data.meal_start,
            meal_end=shift_data.meal_end,
            shift_type=shift_data.shift_type,
            is_mandatory=shift_data.is_mandatory,
            notes=shift_data.notes
        )

        db.add(new_shift)
        db.commit()
        db.refresh(new_shift)

        # Check for conflicts after creating shift
        await detect_shift_conflicts(new_shift.id, db)

        return ShiftResponse.model_validate(new_shift)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating shift: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create shift"
        )

@router.post("/shifts/bulk", response_model=List[ShiftResponse])
async def create_shifts_bulk(
    bulk_data: ShiftBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "create"))
):
    """Create multiple shifts in bulk."""

    # Validate schedule
    schedule = db.query(Schedule).filter(
        Schedule.id == bulk_data.schedule_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    try:
        created_shifts = []

        for shift_data in bulk_data.shifts:
            # Validate staff for each shift
            staff = db.query(Staff).filter(
                Staff.id == shift_data.staff_id,
                Staff.organization_id == current_user.organization_id
            ).first()

            if not staff:
                continue  # Skip invalid staff

            new_shift = Shift(
                schedule_id=shift_data.schedule_id,
                staff_id=shift_data.staff_id,
                location_id=shift_data.location_id,
                shift_date=shift_data.shift_date,
                start_time=shift_data.start_time,
                end_time=shift_data.end_time,
                break_start=shift_data.break_start,
                break_end=shift_data.break_end,
                meal_start=shift_data.meal_start,
                meal_end=shift_data.meal_end,
                shift_type=shift_data.shift_type,
                is_mandatory=shift_data.is_mandatory,
                notes=shift_data.notes
            )

            db.add(new_shift)
            created_shifts.append(new_shift)

        db.commit()

        # Refresh all created shifts
        for shift in created_shifts:
            db.refresh(shift)

        # Run conflict detection for all new shifts
        for shift in created_shifts:
            await detect_shift_conflicts(shift.id, db)

        return [ShiftResponse.model_validate(shift) for shift in created_shifts]

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating shifts in bulk: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create shifts in bulk"
        )

@router.get("/shifts", response_model=PaginatedResponse)
async def get_shifts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    schedule_id: Optional[UUID] = None,
    staff_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    shift_status: Optional[ShiftStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get list of shifts with filtering."""

    query = db.query(Shift).join(Schedule).filter(
        Schedule.organization_id == current_user.organization_id
    )

    # Apply filters
    if schedule_id:
        query = query.filter(Shift.schedule_id == schedule_id)

    if staff_id:
        query = query.filter(Shift.staff_id == staff_id)

    if start_date:
        query = query.filter(Shift.shift_date >= start_date)

    if end_date:
        query = query.filter(Shift.shift_date <= end_date)

    if shift_status:
        query = query.filter(Shift.status == shift_status)

    total = query.count()
    shifts = query.offset(skip).limit(limit).all()

    pages = (total + limit - 1) // limit

    return PaginatedResponse(
        items=[ShiftResponse.model_validate(s) for s in shifts],
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=pages
    )

@router.get("/shifts/{shift_id}", response_model=ShiftResponse)
async def get_shift(
    shift_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get shift details."""

    shift = db.query(Shift).join(Schedule).filter(
        Shift.id == shift_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shift not found"
        )

    return ShiftResponse.model_validate(shift)

@router.put("/shifts/{shift_id}", response_model=ShiftResponse)
async def update_shift(
    shift_id: UUID,
    shift_update: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Update shift."""

    shift = db.query(Shift).join(Schedule).filter(
        Shift.id == shift_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shift not found"
        )

    # Update fields
    update_data = shift_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(shift, field, value)

    shift.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(shift)

    # Re-run conflict detection
    await detect_shift_conflicts(shift.id, db)

    return ShiftResponse.model_validate(shift)

@router.delete("/shifts/{shift_id}", response_model=MessageResponse)
async def cancel_shift(
    shift_id: UUID,
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Cancel a shift."""

    shift = db.query(Shift).join(Schedule).filter(
        Shift.id == shift_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shift not found"
        )

    shift.status = ShiftStatus.CANCELLED
    if reason:
        shift.notes = f"{shift.notes or ''}\n\nCancelled: {reason}".strip()

    shift.updated_at = datetime.now(timezone.utc)
    db.commit()

    return MessageResponse(
        message="Shift cancelled successfully",
        success=True
    )

# Conflict Detection Helper
async def detect_shift_conflicts(shift_id: UUID, db: Session):
    """Detect and log conflicts for a shift."""

    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        return

    conflicts = []

    # Check for double bookings
    overlapping_shifts = db.query(Shift).filter(
        Shift.staff_id == shift.staff_id,
        Shift.shift_date == shift.shift_date,
        Shift.id != shift.id,
        Shift.status != ShiftStatus.CANCELLED
    ).all()

    for overlap_shift in overlapping_shifts:
        if (shift.start_time < overlap_shift.end_time and
            shift.end_time > overlap_shift.start_time):

            conflict = ScheduleConflict(
                conflict_type=ConflictType.DOUBLE_BOOKING,
                shift_id=shift.id,
                staff_id=shift.staff_id,
                conflict_description=f"Double booking detected with shift {overlap_shift.id}",
                severity=ConflictSeverity.HIGH
            )
            conflicts.append(conflict)

    # Check availability conflicts
    day_of_week = shift.shift_date.weekday() + 1  # Convert to 1-7 format
    availability = db.query(StaffAvailability).filter(
        StaffAvailability.staff_id == shift.staff_id,
        StaffAvailability.day_of_week == day_of_week,
        StaffAvailability.effective_date <= shift.shift_date
    ).filter(
        (StaffAvailability.expiry_date.is_(None)) |
        (StaffAvailability.expiry_date >= shift.shift_date)
    ).first()

    if availability and availability.availability_type.value == "unavailable":
        if (shift.start_time < availability.end_time and
            shift.end_time > availability.start_time):

            conflict = ScheduleConflict(
                conflict_type=ConflictType.AVAILABILITY_CONFLICT,
                shift_id=shift.id,
                staff_id=shift.staff_id,
                conflict_description="Shift scheduled during unavailable time",
                severity=ConflictSeverity.MEDIUM
            )
            conflicts.append(conflict)

    # Save conflicts
    for conflict in conflicts:
        existing_conflict = db.query(ScheduleConflict).filter(
            ScheduleConflict.shift_id == conflict.shift_id,
            ScheduleConflict.conflict_type == conflict.conflict_type,
            ScheduleConflict.resolved == False
        ).first()

        if not existing_conflict:
            db.add(conflict)

    if conflicts:
        db.commit()

# Conflicts Endpoint
@router.get("/conflicts", response_model=List[ScheduleConflictResponse])
async def get_schedule_conflicts(
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    severity: Optional[ConflictSeverity] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get scheduling conflicts."""

    query = db.query(ScheduleConflict).join(Staff).filter(
        Staff.organization_id == current_user.organization_id
    )

    if resolved is not None:
        query = query.filter(ScheduleConflict.resolved == resolved)

    if severity:
        query = query.filter(ScheduleConflict.severity == severity)

    if start_date or end_date:
        query = query.join(Shift)
        if start_date:
            query = query.filter(Shift.shift_date >= start_date)
        if end_date:
            query = query.filter(Shift.shift_date <= end_date)

    conflicts = query.all()

    return [ScheduleConflictResponse.model_validate(c) for c in conflicts]

# Documentation Status Endpoint
@router.get("/shifts/{shift_id}/documentation-status")
async def get_shift_documentation_status(
    shift_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get documentation completion status for a shift.
    Returns which required documents have been submitted.
    """
    # Get shift
    shift = db.query(Shift).join(Schedule).filter(
        Shift.id == shift_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shift not found"
        )

    # Get required documentation list
    required_docs = shift.required_documentation or []

    # Check which documents have been submitted
    documentation_status = {}

    for doc_type in required_docs:
        is_submitted = False

        if doc_type == "vitals_log":
            from app.models.vitals_log import VitalsLog
            vitals = db.query(VitalsLog).filter(
                VitalsLog.client_id == shift.client_id,
                VitalsLog.created_at >= datetime.combine(shift.shift_date, shift.start_time or datetime.min.time()),
                VitalsLog.created_at <= datetime.combine(shift.shift_date, shift.end_time or datetime.max.time())
            ).first()
            is_submitted = vitals is not None

        elif doc_type == "shift_note":
            from app.models.shift_note import ShiftNote
            note = db.query(ShiftNote).filter(
                ShiftNote.client_id == shift.client_id,
                ShiftNote.shift_date == shift.shift_date
            ).first()
            is_submitted = note is not None

        elif doc_type == "meal_log":
            from app.models.meal_log import MealLog
            meal = db.query(MealLog).filter(
                MealLog.client_id == shift.client_id,
                MealLog.meal_date == shift.shift_date
            ).first()
            is_submitted = meal is not None

        elif doc_type == "incident_report":
            from app.models.incident_report import IncidentReport
            incident = db.query(IncidentReport).filter(
                IncidentReport.client_id == shift.client_id,
                IncidentReport.incident_date == shift.shift_date
            ).first()
            is_submitted = incident is not None

        elif doc_type == "activity_log":
            from app.models.activity_log import ActivityLog
            activity = db.query(ActivityLog).filter(
                ActivityLog.client_id == shift.client_id,
                ActivityLog.activity_date == shift.shift_date
            ).first()
            is_submitted = activity is not None

        documentation_status[doc_type] = {
            "required": True,
            "submitted": is_submitted
        }

    # Calculate completion percentage
    total_required = len(required_docs)
    total_submitted = sum(1 for status in documentation_status.values() if status["submitted"])
    completion_percentage = (total_submitted / total_required * 100) if total_required > 0 else 100

    all_complete = total_submitted == total_required

    return {
        "shift_id": str(shift_id),
        "shift_date": shift.shift_date.isoformat(),
        "client_id": str(shift.client_id) if shift.client_id else None,
        "documentation_status": documentation_status,
        "completion_percentage": round(completion_percentage, 2),
        "all_complete": all_complete,
        "can_clock_out": all_complete,
        "missing_documents": [doc for doc, status in documentation_status.items() if not status["submitted"]]
    }