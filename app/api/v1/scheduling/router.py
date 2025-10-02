from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from datetime import datetime, date, timedelta
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
    """Get the current active shift for the logged-in DSP staff member."""

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

    # Get the current active shift (today's shift that is in progress or scheduled for today)
    today = date.today()
    current_shift = db.query(Shift).options(
        joinedload(Shift.schedule)
    ).filter(
        Shift.staff_id == staff.id,
        Shift.shift_date == today,
        Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.IN_PROGRESS])
    ).first()

    if not current_shift:
        return {
            "has_active_shift": False,
            "message": "No active shift found for today"
        }

    # Get client assignment details from shift assignments
    from app.models.staff import StaffAssignment
    from app.models.client import ClientLocation
    from app.models.scheduling import ShiftAssignment as ShiftClientAssignment

    # Get the first client assignment for this shift
    shift_client_assignment = db.query(ShiftClientAssignment).filter(
        ShiftClientAssignment.shift_id == current_shift.id
    ).first()

    client_id = shift_client_assignment.client_id if shift_client_assignment else None

    assignment = None
    if client_id:
        assignment = db.query(StaffAssignment).filter(
            StaffAssignment.staff_id == staff.id,
            StaffAssignment.client_id == client_id,
            StaffAssignment.is_active == True
        ).first()

    # Get tasks for this shift
    from app.models.task import Task, TaskStatus

    tasks_query = db.query(Task).filter(
        Task.assigned_to == current_user.id,
        Task.client_id == client_id if client_id else None,
        Task.due_date == today
    ) if client_id else db.query(Task).filter(Task.id == None)  # Empty query if no client

    total_tasks = tasks_query.count()
    completed_tasks = tasks_query.filter(Task.status == TaskStatus.COMPLETED).count()

    # Calculate time on shift
    from app.models.scheduling import TimeClockEntry, TimeEntryType

    clock_in_entry = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff.id,
        TimeClockEntry.shift_id == current_shift.id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    time_on_shift = None
    clock_in_time = None
    if clock_in_entry:
        clock_in_time = clock_in_entry.entry_datetime
        elapsed = datetime.utcnow() - clock_in_entry.entry_datetime
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        time_on_shift = f"{hours}h {minutes}m"

    # Build response
    location_name = assignment.location.name if assignment and assignment.location else "Location Not Set"
    location_address = assignment.location.address if assignment and assignment.location else ""

    return {
        "has_active_shift": True,
        "shift": {
            "id": str(current_shift.id),
            "shift_date": current_shift.shift_date.isoformat(),
            "start_time": current_shift.start_time.strftime("%I:%M %p") if current_shift.start_time else None,
            "end_time": current_shift.end_time.strftime("%I:%M %p") if current_shift.end_time else None,
            "status": current_shift.status.value,
            "notes": current_shift.notes
        },
        "client": {
            "id": str(current_shift.client.id) if current_shift.client else None,
            "full_name": current_shift.client.full_name if current_shift.client else "Unknown Client",
            "client_id": current_shift.client.client_id if current_shift.client else None,
            "special_needs": current_shift.client.primary_diagnosis if current_shift.client else None
        },
        "location": {
            "name": location_name,
            "address": location_address
        },
        "time_tracking": {
            "time_on_shift": time_on_shift,
            "clock_in_time": clock_in_time.strftime("%I:%M %p") if clock_in_time else None,
            "is_clocked_in": clock_in_time is not None
        },
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "pending": total_tasks - completed_tasks
        }
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

    schedule.updated_at = datetime.utcnow()
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
    schedule.approved_at = datetime.utcnow()
    schedule.updated_at = datetime.utcnow()

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

    shift.updated_at = datetime.utcnow()
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

    shift.updated_at = datetime.utcnow()
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