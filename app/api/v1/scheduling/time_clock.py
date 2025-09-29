from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from datetime import datetime, date, time, timedelta
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
    OvertimeTrackingResponse, PaginatedResponse
)
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

    # Validate staff
    staff = db.query(Staff).filter(
        Staff.id == clock_in_data.staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Check for existing clock-in without clock-out
    existing_entry = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == clock_in_data.staff_id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    if existing_entry:
        # Check if there's a corresponding clock-out
        clock_out = db.query(TimeClockEntry).filter(
            TimeClockEntry.staff_id == clock_in_data.staff_id,
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
            staff_id=clock_in_data.staff_id,
            shift_id=clock_in_data.shift_id,
            entry_type=TimeEntryType.CLOCK_IN,
            entry_datetime=datetime.utcnow(),
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
                shift.updated_at = datetime.utcnow()

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

    # Validate staff
    staff = db.query(Staff).filter(
        Staff.id == clock_out_data.staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Find the most recent clock-in without clock-out
    clock_in_entry = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == clock_out_data.staff_id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    if not clock_in_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active clock-in found"
        )

    # Check if already clocked out
    clock_out_check = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == clock_out_data.staff_id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_OUT,
        TimeClockEntry.entry_datetime > clock_in_entry.entry_datetime
    ).first()

    if clock_out_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff member is already clocked out"
        )

    try:
        # Create clock-out entry
        clock_out_entry = TimeClockEntry(
            staff_id=clock_out_data.staff_id,
            shift_id=clock_out_data.shift_id or clock_in_entry.shift_id,
            entry_type=TimeEntryType.CLOCK_OUT,
            entry_datetime=datetime.utcnow(),
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
                shift.updated_at = datetime.utcnow()

        # Calculate and record overtime if applicable
        await calculate_overtime(
            staff_id=clock_out_data.staff_id,
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
            entry_datetime=datetime.utcnow(),
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
            entry_datetime=datetime.utcnow(),
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