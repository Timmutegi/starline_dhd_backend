from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, date, time, timedelta
from app.core.database import get_db
from app.models.user import User
from app.models.staff import Staff
from app.models.scheduling import (
    TimeClockEntry, Shift, OvertimeTracking,
    TimeEntryType, ShiftStatus
)
from app.middleware.auth import get_current_user, require_permission
from app.schemas.scheduling import (
    TimeClockEntryCreate, TimeClockEntryResponse,
    ClockInRequest, ClockOutRequest,
    OvertimeTrackingResponse, PaginatedResponse,
    WorkedHoursSummary
)
from sqlalchemy import func, and_
from calendar import monthrange
from app.schemas.auth import MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/clock-in", response_model=TimeClockEntryResponse)
async def clock_in(
    clock_in_data: ClockInRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("time_clock", "create"))
):
    """Clock in for a shift."""

    # Get staff_id - use provided value or derive from current user
    staff_id = clock_in_data.staff_id
    if not staff_id:
        # Get staff record for current user
        staff = db.query(Staff).filter(
            Staff.user_id == current_user.id,
            Staff.organization_id == current_user.organization_id
        ).first()
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No staff record found for current user"
            )
        staff_id = staff.id
    else:
        # Validate provided staff_id
        staff = db.query(Staff).filter(
            Staff.id == staff_id,
            Staff.organization_id == current_user.organization_id
        ).first()
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found"
            )

    # Check for existing clock-in without clock-out
    existing_entry = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff_id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    if existing_entry:
        # Check if there's a corresponding clock-out
        clock_out = db.query(TimeClockEntry).filter(
            TimeClockEntry.staff_id == staff_id,
            TimeClockEntry.entry_type == TimeEntryType.CLOCK_OUT,
            TimeClockEntry.entry_datetime > existing_entry.entry_datetime
        ).first()

        if not clock_out:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Staff member is already clocked in"
            )

    try:
        # Create clock-in entry
        clock_in_entry = TimeClockEntry(
            staff_id=staff_id,
            shift_id=clock_in_data.shift_id,
            entry_type=TimeEntryType.CLOCK_IN,
            entry_datetime=datetime.now(timezone.utc).replace(tzinfo=None),
            location_verified=bool(clock_in_data.geolocation),
            geolocation=clock_in_data.geolocation,
            ip_address=request.client.host if request.client else None,
            device_info={
                "user_agent": request.headers.get("User-Agent", ""),
                "referer": request.headers.get("Referer", "")
            },
            photo_url=clock_in_data.photo_url,
            notes=clock_in_data.notes
        )

        db.add(clock_in_entry)

        # Update shift status if shift_id provided
        if clock_in_data.shift_id:
            shift = db.query(Shift).filter(Shift.id == clock_in_data.shift_id).first()
            if shift and shift.status == ShiftStatus.SCHEDULED:
                shift.status = ShiftStatus.IN_PROGRESS
                shift.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        db.commit()
        db.refresh(clock_in_entry)

        return TimeClockEntryResponse.model_validate(clock_in_entry)

    except Exception as e:
        db.rollback()
        logger.error(f"Error during clock-in: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clock in"
        )

@router.post("/clock-out", response_model=TimeClockEntryResponse)
async def clock_out(
    clock_out_data: ClockOutRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("time_clock", "create"))
):
    """Clock out from a shift."""

    logger.info(f"Clock-out request received: shift_id={clock_out_data.shift_id}, staff_id={clock_out_data.staff_id}")

    # Get staff_id - use provided value or derive from current user
    staff_id = clock_out_data.staff_id
    if not staff_id:
        # Get staff record for current user
        staff = db.query(Staff).filter(
            Staff.user_id == current_user.id,
            Staff.organization_id == current_user.organization_id
        ).first()
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No staff record found for current user"
            )
        staff_id = staff.id
    else:
        # Validate provided staff_id
        staff = db.query(Staff).filter(
            Staff.id == staff_id,
            Staff.organization_id == current_user.organization_id
        ).first()
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found"
            )

    # Find the most recent clock-in without clock-out
    clock_in_entry = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff_id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    if not clock_in_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active clock-in found"
        )

    # Check if already clocked out
    clock_out_check = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff_id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_OUT,
        TimeClockEntry.entry_datetime > clock_in_entry.entry_datetime
    ).first()

    if clock_out_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff member is already clocked out"
        )

    # Validate required documentation is completed before allowing clock-out
    shift_id = clock_out_data.shift_id or clock_in_entry.shift_id
    if shift_id:
        shift = db.query(Shift).filter(Shift.id == shift_id).first()
        if shift:
            # Determine required documentation with priority:
            # 1. Shift-specific override (if set and not empty)
            # 2. Client-specific requirement (from client.required_documentation)
            # 3. Default fallback (["shift_note"])
            required_docs = None

            if shift.required_documentation:
                required_docs = shift.required_documentation
            elif shift.client_id:
                from app.models.client import Client
                client = db.query(Client).filter(Client.id == shift.client_id).first()
                if client and client.required_documentation:
                    required_docs = client.required_documentation

            if not required_docs:
                required_docs = ["shift_note"]  # Default fallback

            # Check documentation status
            missing_docs = []

            for doc_type in required_docs:
                is_submitted = False

                if doc_type == "vitals_log" and shift.client_id:
                    from app.models.vitals_log import VitalsLog
                    # VitalsLog.recorded_at is timezone-aware, compare by date
                    vitals = db.query(VitalsLog).filter(
                        VitalsLog.client_id == shift.client_id,
                        VitalsLog.staff_id == current_user.id,
                        func.date(VitalsLog.recorded_at) == shift.shift_date
                    ).first()
                    is_submitted = vitals is not None

                elif doc_type == "shift_note":
                    from app.models.shift_note import ShiftNote
                    query = db.query(ShiftNote).filter(
                        ShiftNote.staff_id == current_user.id,
                        ShiftNote.shift_date == shift.shift_date
                    )
                    if shift.client_id:
                        query = query.filter(ShiftNote.client_id == shift.client_id)
                    note = query.first()
                    is_submitted = note is not None

                elif doc_type == "meal_log" and shift.client_id:
                    from app.models.meal_log import MealLog
                    # MealLog.meal_date is a DateTime, compare by date
                    meal = db.query(MealLog).filter(
                        MealLog.client_id == shift.client_id,
                        MealLog.staff_id == current_user.id,
                        func.date(MealLog.meal_date) == shift.shift_date
                    ).first()
                    is_submitted = meal is not None

                elif doc_type == "incident_report" and shift.client_id:
                    from app.models.incident_report import IncidentReport
                    incident = db.query(IncidentReport).filter(
                        IncidentReport.client_id == shift.client_id,
                        IncidentReport.staff_id == current_user.id,
                        IncidentReport.incident_date == shift.shift_date
                    ).first()
                    is_submitted = incident is not None

                elif doc_type == "activity_log" and shift.client_id:
                    from app.models.activity_log import ActivityLog
                    # ActivityLog.activity_date is likely a DateTime, compare by date
                    activity = db.query(ActivityLog).filter(
                        ActivityLog.client_id == shift.client_id,
                        ActivityLog.staff_id == current_user.id,
                        func.date(ActivityLog.activity_date) == shift.shift_date
                    ).first()
                    is_submitted = activity is not None

                elif doc_type == "sleep_log" and shift.client_id:
                    from app.models.sleep_log import SleepLog
                    sleep = db.query(SleepLog).filter(
                        SleepLog.client_id == shift.client_id,
                        SleepLog.staff_id == current_user.id,
                        SleepLog.shift_date == shift.shift_date
                    ).first()
                    is_submitted = sleep is not None

                elif doc_type == "bowel_movement_log" and shift.client_id:
                    from app.models.bowel_movement_log import BowelMovementLog
                    bowel = db.query(BowelMovementLog).filter(
                        BowelMovementLog.client_id == shift.client_id,
                        BowelMovementLog.staff_id == current_user.id,
                        func.date(BowelMovementLog.recorded_at) == shift.shift_date
                    ).first()
                    is_submitted = bowel is not None

                if not is_submitted:
                    missing_docs.append(doc_type)

            # Check for incomplete special requirements
            missing_requirements = []
            if shift.client_id:
                from app.models.special_requirement import (
                    SpecialRequirement, SpecialRequirementResponse,
                    RequirementStatus as SRStatus
                )

                # Get active special requirements for this client on this shift date
                active_requirements = db.query(SpecialRequirement).filter(
                    and_(
                        SpecialRequirement.client_id == shift.client_id,
                        SpecialRequirement.organization_id == current_user.organization_id,
                        SpecialRequirement.status == SRStatus.ACTIVE,
                        SpecialRequirement.start_date <= shift.shift_date,
                        SpecialRequirement.end_date >= shift.shift_date
                    )
                ).all()

                # Check which requirements are missing responses for this shift
                for req in active_requirements:
                    response = db.query(SpecialRequirementResponse).filter(
                        and_(
                            SpecialRequirementResponse.special_requirement_id == req.id,
                            SpecialRequirementResponse.staff_id == current_user.id,
                            SpecialRequirementResponse.shift_id == shift.id
                        )
                    ).first()

                    if not response:
                        missing_requirements.append(req.title)

            # Build comprehensive error message if anything is missing
            if missing_docs or missing_requirements:
                # Helper function to format doc types nicely (e.g., "shift_note" -> "Shift Note")
                def format_doc_name(doc_type: str) -> str:
                    return doc_type.replace("_", " ").title()

                error_parts = []
                if missing_docs:
                    formatted_docs = [format_doc_name(d) for d in missing_docs]
                    error_parts.append(f"documentation: {', '.join(formatted_docs)}")
                if missing_requirements:
                    error_parts.append(f"special requirements: {', '.join(missing_requirements)}")

                error_message = f"Cannot clock out. Please complete the following required {' and '.join(error_parts)}"
                logger.warning(f"Clock-out blocked for staff {staff_id}: {error_message}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_message
                )

    try:
        # Create clock-out entry
        clock_out_entry = TimeClockEntry(
            staff_id=staff_id,
            shift_id=shift_id,
            entry_type=TimeEntryType.CLOCK_OUT,
            entry_datetime=datetime.now(timezone.utc).replace(tzinfo=None),
            location_verified=bool(clock_out_data.geolocation),
            geolocation=clock_out_data.geolocation,
            ip_address=request.client.host if request.client else None,
            device_info={
                "user_agent": request.headers.get("User-Agent", ""),
                "referer": request.headers.get("Referer", "")
            },
            photo_url=clock_out_data.photo_url,
            notes=clock_out_data.notes
        )

        db.add(clock_out_entry)

        # Update shift status
        shift_id = clock_out_data.shift_id or clock_in_entry.shift_id
        if shift_id:
            shift = db.query(Shift).filter(Shift.id == shift_id).first()
            if shift and shift.status == ShiftStatus.IN_PROGRESS:
                shift.status = ShiftStatus.COMPLETED
                shift.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # Calculate and record overtime if applicable
        await calculate_overtime(
            staff_id=staff_id,
            shift_id=shift_id,
            clock_in_time=clock_in_entry.entry_datetime,
            clock_out_time=clock_out_entry.entry_datetime,
            db=db
        )

        db.commit()
        db.refresh(clock_out_entry)

        return TimeClockEntryResponse.model_validate(clock_out_entry)

    except Exception as e:
        db.rollback()
        logger.error(f"Error during clock-out: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clock out"
        )

@router.post("/break-start", response_model=TimeClockEntryResponse)
async def start_break(
    staff_id: UUID,
    shift_id: Optional[UUID] = None,
    notes: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("time_clock", "create"))
):
    """Start a break."""

    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Check if already on break
    latest_break = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff_id,
        TimeClockEntry.entry_type.in_([TimeEntryType.BREAK_START, TimeEntryType.BREAK_END])
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    if latest_break and latest_break.entry_type == TimeEntryType.BREAK_START:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff member is already on break"
        )

    try:
        break_entry = TimeClockEntry(
            staff_id=staff_id,
            shift_id=shift_id,
            entry_type=TimeEntryType.BREAK_START,
            entry_datetime=datetime.now(timezone.utc).replace(tzinfo=None),
            ip_address=request.client.host if request and request.client else None,
            notes=notes
        )

        db.add(break_entry)
        db.commit()
        db.refresh(break_entry)

        return TimeClockEntryResponse.model_validate(break_entry)

    except Exception as e:
        db.rollback()
        logger.error(f"Error starting break: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start break"
        )

@router.post("/break-end", response_model=TimeClockEntryResponse)
async def end_break(
    staff_id: UUID,
    shift_id: Optional[UUID] = None,
    notes: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("time_clock", "create"))
):
    """End a break."""

    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Find the most recent break start
    break_start = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff_id,
        TimeClockEntry.entry_type == TimeEntryType.BREAK_START
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    if not break_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active break found"
        )

    # Check if break already ended
    break_end_check = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff_id,
        TimeClockEntry.entry_type == TimeEntryType.BREAK_END,
        TimeClockEntry.entry_datetime > break_start.entry_datetime
    ).first()

    if break_end_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Break already ended"
        )

    try:
        break_end_entry = TimeClockEntry(
            staff_id=staff_id,
            shift_id=shift_id or break_start.shift_id,
            entry_type=TimeEntryType.BREAK_END,
            entry_datetime=datetime.now(timezone.utc).replace(tzinfo=None),
            ip_address=request.client.host if request and request.client else None,
            notes=notes
        )

        db.add(break_end_entry)
        db.commit()
        db.refresh(break_end_entry)

        return TimeClockEntryResponse.model_validate(break_end_entry)

    except Exception as e:
        db.rollback()
        logger.error(f"Error ending break: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end break"
        )

@router.get("/staff/{staff_id}/time-entries", response_model=PaginatedResponse)
async def get_staff_time_entries(
    staff_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("time_clock", "read"))
):
    """Get time entries for a staff member."""

    # Validate staff
    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    query = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff_id
    )

    # Apply date filters
    if start_date:
        query = query.filter(TimeClockEntry.entry_datetime >= datetime.combine(start_date, time.min))

    if end_date:
        query = query.filter(TimeClockEntry.entry_datetime <= datetime.combine(end_date, time.max))

    # Order by datetime descending
    query = query.order_by(TimeClockEntry.entry_datetime.desc())

    total = query.count()
    entries = query.offset(skip).limit(limit).all()

    pages = (total + limit - 1) // limit

    return PaginatedResponse(
        items=[TimeClockEntryResponse.model_validate(e) for e in entries],
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=pages
    )

@router.put("/time-entries/{entry_id}", response_model=TimeClockEntryResponse)
async def adjust_time_entry(
    entry_id: UUID,
    new_datetime: datetime,
    reason: str = Query(..., description="Reason for adjustment"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("time_clock", "update"))
):
    """Adjust a time entry (admin function)."""

    entry = db.query(TimeClockEntry).join(Staff).filter(
        TimeClockEntry.id == entry_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time entry not found"
        )

    try:
        original_time = entry.entry_datetime
        entry.entry_datetime = new_datetime
        entry.notes = f"{entry.notes or ''}\n\nADJUSTED: {original_time} -> {new_datetime} by {current_user.full_name}. Reason: {reason}".strip()

        db.commit()
        db.refresh(entry)

        return TimeClockEntryResponse.model_validate(entry)

    except Exception as e:
        db.rollback()
        logger.error(f"Error adjusting time entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to adjust time entry"
        )

@router.get("/overtime/staff/{staff_id}", response_model=List[OvertimeTrackingResponse])
async def get_staff_overtime(
    staff_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get overtime tracking for a staff member."""

    # Validate staff
    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    query = db.query(OvertimeTracking).filter(
        OvertimeTracking.staff_id == staff_id
    )

    if start_date:
        query = query.filter(OvertimeTracking.week_start_date >= start_date)

    if end_date:
        query = query.filter(OvertimeTracking.week_start_date <= end_date)

    overtime_records = query.order_by(OvertimeTracking.week_start_date.desc()).all()

    return [OvertimeTrackingResponse.model_validate(ot) for ot in overtime_records]

async def calculate_overtime(
    staff_id: UUID,
    shift_id: Optional[UUID],
    clock_in_time: datetime,
    clock_out_time: datetime,
    db: Session
):
    """Calculate and record overtime for a completed shift."""

    try:
        # Ensure both datetimes are timezone-naive for calculation
        if clock_in_time.tzinfo is not None:
            clock_in_time = clock_in_time.replace(tzinfo=None)
        if clock_out_time.tzinfo is not None:
            clock_out_time = clock_out_time.replace(tzinfo=None)

        # Get the week start date (Monday)
        shift_date = clock_in_time.date()
        days_since_monday = shift_date.weekday()
        week_start_date = shift_date - timedelta(days=days_since_monday)

        # Calculate hours worked this shift
        shift_duration = clock_out_time - clock_in_time
        hours_worked = shift_duration.total_seconds() / 3600

        # Get or create overtime tracking record for this week
        overtime_record = db.query(OvertimeTracking).filter(
            OvertimeTracking.staff_id == staff_id,
            OvertimeTracking.week_start_date == week_start_date
        ).first()

        if not overtime_record:
            overtime_record = OvertimeTracking(
                staff_id=staff_id,
                shift_id=shift_id,
                week_start_date=week_start_date,
                regular_hours=0.0,
                overtime_hours=0.0,
                double_time_hours=0.0,
                holiday_hours=0.0,
                total_hours=0.0
            )
            db.add(overtime_record)

        # Simple overtime calculation (40+ hours = overtime)
        current_total = float(overtime_record.total_hours)
        new_total = current_total + hours_worked

        if current_total < 40:
            if new_total <= 40:
                # All regular hours
                overtime_record.regular_hours = float(overtime_record.regular_hours) + hours_worked
            else:
                # Some regular, some overtime
                regular_portion = 40 - current_total
                overtime_portion = hours_worked - regular_portion
                overtime_record.regular_hours = float(overtime_record.regular_hours) + regular_portion
                overtime_record.overtime_hours = float(overtime_record.overtime_hours) + overtime_portion
        else:
            # All overtime hours
            overtime_record.overtime_hours = float(overtime_record.overtime_hours) + hours_worked

        overtime_record.total_hours = new_total
        db.flush()  # Save without committing the transaction

    except Exception as e:
        logger.error(f"Error calculating overtime: {str(e)}")
        # Don't fail the main transaction for overtime calculation errors


@router.get("/worked-hours/me", response_model=WorkedHoursSummary)
async def get_my_worked_hours(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get worked hours summary for the current user (DSP viewing their own hours).
    """

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No staff record found for current user"
        )

    # Call the main function with the staff_id
    return await get_staff_worked_hours(staff.id, db, current_user)


@router.get("/worked-hours/{staff_id}", response_model=WorkedHoursSummary)
async def get_staff_worked_hours(
    staff_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get worked hours summary for a staff member.
    Accessible by the staff member themselves, managers, and admins.
    """

    # Validate staff exists and belongs to organization
    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Check permission: staff can view their own, managers/admins can view all
    current_user_staff = db.query(Staff).filter(
        Staff.user_id == current_user.id
    ).first()

    is_own_record = current_user_staff and current_user_staff.id == staff_id

    # Check if user has manager/admin role - handle None role gracefully
    # Normalize role name for comparison: lowercase and remove spaces
    is_manager_or_admin = False
    if current_user.role is not None:
        role_name_normalized = current_user.role.name.lower().replace(' ', '').replace('_', '')
        # Check if the role name contains key words indicating admin/manager level
        admin_keywords = ['admin', 'manager', 'supervisor', 'superadmin', 'hrmanager']
        is_manager_or_admin = any(keyword in role_name_normalized for keyword in admin_keywords)

    if not is_own_record and not is_manager_or_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this staff member's hours"
        )

    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        today = now.date()

        # Calculate week start (Monday)
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)

        # Calculate month start/end
        month_start = today.replace(day=1)
        _, last_day = monthrange(today.year, today.month)
        month_end = today.replace(day=last_day)

        # Calculate year start/end
        year_start = date(today.year, 1, 1)
        year_end = date(today.year, 12, 31)

        # Get current week overtime record
        week_record = db.query(OvertimeTracking).filter(
            OvertimeTracking.staff_id == staff_id,
            OvertimeTracking.week_start_date == week_start
        ).first()

        current_week_hours = float(week_record.total_hours) if week_record else 0.0
        current_week_regular = float(week_record.regular_hours) if week_record else 0.0
        current_week_overtime = float(week_record.overtime_hours) if week_record else 0.0

        # Calculate month hours from overtime tracking
        month_records = db.query(OvertimeTracking).filter(
            OvertimeTracking.staff_id == staff_id,
            OvertimeTracking.week_start_date >= month_start,
            OvertimeTracking.week_start_date <= month_end
        ).all()

        current_month_hours = sum(float(r.total_hours) for r in month_records)

        # Calculate year hours from overtime tracking
        year_records = db.query(OvertimeTracking).filter(
            OvertimeTracking.staff_id == staff_id,
            OvertimeTracking.week_start_date >= year_start,
            OvertimeTracking.week_start_date <= year_end
        ).all()

        current_year_hours = sum(float(r.total_hours) for r in year_records)

        # Get last clock in/out times
        last_clock_in = db.query(TimeClockEntry).filter(
            TimeClockEntry.staff_id == staff_id,
            TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
        ).order_by(TimeClockEntry.entry_datetime.desc()).first()

        last_clock_out = db.query(TimeClockEntry).filter(
            TimeClockEntry.staff_id == staff_id,
            TimeClockEntry.entry_type == TimeEntryType.CLOCK_OUT
        ).order_by(TimeClockEntry.entry_datetime.desc()).first()

        # Determine if currently clocked in
        is_clocked_in = False
        if last_clock_in:
            if not last_clock_out:
                is_clocked_in = True
            elif last_clock_in.entry_datetime > last_clock_out.entry_datetime:
                is_clocked_in = True

        # PTO eligible hours (typically based on regular hours worked)
        # This is a simplified calculation - adjust based on your PTO policy
        pto_eligible_hours = current_year_hours

        # Get staff full name
        staff_name = f"{staff.first_name} {staff.last_name}" if hasattr(staff, 'first_name') else staff.full_name

        return WorkedHoursSummary(
            staff_id=staff.id,
            staff_name=staff_name,
            current_week_hours=round(current_week_hours, 2),
            current_week_regular=round(current_week_regular, 2),
            current_week_overtime=round(current_week_overtime, 2),
            current_month_hours=round(current_month_hours, 2),
            current_year_hours=round(current_year_hours, 2),
            last_clock_in=last_clock_in.entry_datetime if last_clock_in else None,
            last_clock_out=last_clock_out.entry_datetime if last_clock_out else None,
            is_currently_clocked_in=is_clocked_in,
            pto_eligible_hours=round(pto_eligible_hours, 2),
            week_start_date=week_start
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting worked hours for staff {staff_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve worked hours"
        )