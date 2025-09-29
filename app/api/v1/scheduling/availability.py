from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, date
from app.core.database import get_db
from app.models.user import User
from app.models.staff import Staff
from app.models.scheduling import (
    StaffAvailability, TimeOffScheduling, CoverageRequest, ShiftSwap,
    AvailabilityType, TimeOffType, RequestType, RequestStatus, SwapStatus
)
from app.middleware.auth import get_current_user, require_permission
from app.schemas.scheduling import (
    StaffAvailabilityCreate, StaffAvailabilityUpdate, StaffAvailabilityResponse,
    StaffAvailabilityBulkUpdate, TimeOffSchedulingCreate, TimeOffSchedulingResponse,
    CoverageRequestCreate, CoverageRequestUpdate, CoverageRequestResponse,
    ShiftSwapCreate, ShiftSwapResponse, PaginatedResponse
)
from app.schemas.auth import MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Staff Availability Management

@router.get("/staff/{staff_id}/availability", response_model=List[StaffAvailabilityResponse])
async def get_staff_availability(
    staff_id: UUID,
    effective_date: Optional[date] = Query(None, description="Filter by effective date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get availability for a staff member."""

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

    query = db.query(StaffAvailability).filter(
        StaffAvailability.staff_id == staff_id
    )

    if effective_date:
        query = query.filter(
            StaffAvailability.effective_date <= effective_date
        ).filter(
            (StaffAvailability.expiry_date.is_(None)) |
            (StaffAvailability.expiry_date >= effective_date)
        )

    availability_slots = query.order_by(
        StaffAvailability.day_of_week,
        StaffAvailability.start_time
    ).all()

    return [StaffAvailabilityResponse.model_validate(slot) for slot in availability_slots]

@router.post("/staff/{staff_id}/availability", response_model=StaffAvailabilityResponse)
async def create_staff_availability(
    staff_id: UUID,
    availability_data: StaffAvailabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Create availability slot for a staff member."""

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

    # Check for overlapping availability on the same day
    overlap_check = db.query(StaffAvailability).filter(
        StaffAvailability.staff_id == staff_id,
        StaffAvailability.day_of_week == availability_data.day_of_week,
        StaffAvailability.effective_date <= availability_data.effective_date,
        StaffAvailability.start_time < availability_data.end_time,
        StaffAvailability.end_time > availability_data.start_time
    ).filter(
        (StaffAvailability.expiry_date.is_(None)) |
        (StaffAvailability.expiry_date >= availability_data.effective_date)
    ).first()

    if overlap_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Overlapping availability slot exists"
        )

    try:
        # Set staff_id from path parameter
        availability_data.staff_id = staff_id

        new_availability = StaffAvailability(
            staff_id=availability_data.staff_id,
            day_of_week=availability_data.day_of_week,
            start_time=availability_data.start_time,
            end_time=availability_data.end_time,
            availability_type=availability_data.availability_type,
            effective_date=availability_data.effective_date,
            expiry_date=availability_data.expiry_date,
            notes=availability_data.notes
        )

        db.add(new_availability)
        db.commit()
        db.refresh(new_availability)

        return StaffAvailabilityResponse.model_validate(new_availability)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating staff availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create availability slot"
        )

@router.put("/staff/{staff_id}/availability/{availability_id}", response_model=StaffAvailabilityResponse)
async def update_staff_availability(
    staff_id: UUID,
    availability_id: UUID,
    availability_update: StaffAvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Update availability slot."""

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

    availability = db.query(StaffAvailability).filter(
        StaffAvailability.id == availability_id,
        StaffAvailability.staff_id == staff_id
    ).first()

    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability slot not found"
        )

    try:
        # Update fields
        update_data = availability_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(availability, field, value)

        availability.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(availability)

        return StaffAvailabilityResponse.model_validate(availability)

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating staff availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update availability slot"
        )

@router.delete("/staff/{staff_id}/availability/{availability_id}", response_model=MessageResponse)
async def delete_staff_availability(
    staff_id: UUID,
    availability_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Delete availability slot."""

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

    availability = db.query(StaffAvailability).filter(
        StaffAvailability.id == availability_id,
        StaffAvailability.staff_id == staff_id
    ).first()

    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability slot not found"
        )

    try:
        db.delete(availability)
        db.commit()

        return MessageResponse(
            message="Availability slot deleted successfully",
            success=True
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting staff availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete availability slot"
        )

@router.put("/staff/{staff_id}/availability/bulk", response_model=List[StaffAvailabilityResponse])
async def bulk_update_staff_availability(
    staff_id: UUID,
    bulk_data: StaffAvailabilityBulkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Bulk update staff availability (replaces all existing availability)."""

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

    try:
        # Delete existing availability
        db.query(StaffAvailability).filter(
            StaffAvailability.staff_id == staff_id
        ).delete()

        # Create new availability slots
        new_slots = []
        for slot_data in bulk_data.availability_slots:
            new_slot = StaffAvailability(
                staff_id=staff_id,
                day_of_week=slot_data.day_of_week,
                start_time=slot_data.start_time,
                end_time=slot_data.end_time,
                availability_type=slot_data.availability_type,
                effective_date=slot_data.effective_date,
                expiry_date=slot_data.expiry_date,
                notes=slot_data.notes
            )
            db.add(new_slot)
            new_slots.append(new_slot)

        db.commit()

        # Refresh all new slots
        for slot in new_slots:
            db.refresh(slot)

        return [StaffAvailabilityResponse.model_validate(slot) for slot in new_slots]

    except Exception as e:
        db.rollback()
        logger.error(f"Error bulk updating staff availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk update availability"
        )

# Time Off Management

@router.post("/time-off", response_model=TimeOffSchedulingResponse)
async def create_time_off_request(
    time_off_data: TimeOffSchedulingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "create"))
):
    """Create a time off request that affects scheduling."""

    # Validate staff
    staff = db.query(Staff).filter(
        Staff.id == time_off_data.staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    try:
        new_time_off = TimeOffScheduling(
            staff_id=time_off_data.staff_id,
            start_datetime=time_off_data.start_datetime,
            end_datetime=time_off_data.end_datetime,
            time_off_type=time_off_data.time_off_type,
            affects_scheduling=time_off_data.affects_scheduling,
            replacement_required=time_off_data.replacement_required,
            notes=time_off_data.notes
        )

        db.add(new_time_off)
        db.commit()
        db.refresh(new_time_off)

        return TimeOffSchedulingResponse.model_validate(new_time_off)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating time off request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create time off request"
        )

@router.get("/time-off", response_model=List[TimeOffSchedulingResponse])
async def get_time_off_requests(
    staff_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[RequestStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get time off requests that affect scheduling."""

    query = db.query(TimeOffScheduling).join(Staff).filter(
        Staff.organization_id == current_user.organization_id
    )

    if staff_id:
        query = query.filter(TimeOffScheduling.staff_id == staff_id)

    if start_date:
        query = query.filter(TimeOffScheduling.start_datetime >= datetime.combine(start_date, datetime.min.time()))

    if end_date:
        query = query.filter(TimeOffScheduling.end_datetime <= datetime.combine(end_date, datetime.max.time()))

    if status:
        query = query.filter(TimeOffScheduling.status == status)

    time_off_requests = query.order_by(TimeOffScheduling.start_datetime).all()

    return [TimeOffSchedulingResponse.model_validate(to) for to in time_off_requests]

# Coverage Requests

@router.post("/coverage-requests", response_model=CoverageRequestResponse)
async def create_coverage_request(
    coverage_data: CoverageRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "create"))
):
    """Create a shift coverage request."""

    # Validate shift and staff belong to organization
    from app.models.scheduling import Shift, Schedule

    shift = db.query(Shift).join(Schedule).filter(
        Shift.id == coverage_data.original_shift_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shift not found"
        )

    staff = db.query(Staff).filter(
        Staff.id == coverage_data.requesting_staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Check if request already exists for this shift
    existing_request = db.query(CoverageRequest).filter(
        CoverageRequest.original_shift_id == coverage_data.original_shift_id,
        CoverageRequest.status == RequestStatus.PENDING
    ).first()

    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coverage request already exists for this shift"
        )

    try:
        new_request = CoverageRequest(
            original_shift_id=coverage_data.original_shift_id,
            requesting_staff_id=coverage_data.requesting_staff_id,
            reason=coverage_data.reason,
            request_type=coverage_data.request_type,
            notes=coverage_data.notes
        )

        db.add(new_request)
        db.commit()
        db.refresh(new_request)

        return CoverageRequestResponse.model_validate(new_request)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating coverage request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create coverage request"
        )

@router.get("/coverage-requests", response_model=PaginatedResponse)
async def get_coverage_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[RequestStatus] = None,
    request_type: Optional[RequestType] = None,
    staff_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get coverage requests."""

    from app.models.scheduling import Shift, Schedule

    query = db.query(CoverageRequest).join(
        Staff, CoverageRequest.requesting_staff_id == Staff.id
    ).filter(
        Staff.organization_id == current_user.organization_id
    )

    if status:
        query = query.filter(CoverageRequest.status == status)

    if request_type:
        query = query.filter(CoverageRequest.request_type == request_type)

    if staff_id:
        query = query.filter(CoverageRequest.requesting_staff_id == staff_id)

    total = query.count()
    requests = query.order_by(CoverageRequest.requested_at.desc()).offset(skip).limit(limit).all()

    pages = (total + limit - 1) // limit

    return PaginatedResponse(
        items=[CoverageRequestResponse.model_validate(r) for r in requests],
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=pages
    )

@router.put("/coverage-requests/{request_id}", response_model=CoverageRequestResponse)
async def update_coverage_request(
    request_id: UUID,
    request_update: CoverageRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Update/respond to a coverage request."""

    coverage_request = db.query(CoverageRequest).join(
        Staff, CoverageRequest.requesting_staff_id == Staff.id
    ).filter(
        CoverageRequest.id == request_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not coverage_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coverage request not found"
        )

    try:
        # Update fields
        update_data = request_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(coverage_request, field, value)

        if request_update.status:
            coverage_request.responded_at = datetime.utcnow()
            coverage_request.responded_by = current_user.id

        db.commit()
        db.refresh(coverage_request)

        return CoverageRequestResponse.model_validate(coverage_request)

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating coverage request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update coverage request"
        )

@router.post("/coverage-requests/{request_id}/approve", response_model=MessageResponse)
async def approve_coverage_request(
    request_id: UUID,
    notes: Optional[str] = Query(None, description="Approval notes"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "update"))
):
    """Approve a coverage request."""

    coverage_request = db.query(CoverageRequest).join(
        Staff, CoverageRequest.requesting_staff_id == Staff.id
    ).filter(
        CoverageRequest.id == request_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not coverage_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coverage request not found"
        )

    if coverage_request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coverage request is not pending"
        )

    try:
        coverage_request.status = RequestStatus.APPROVED
        coverage_request.responded_at = datetime.utcnow()
        coverage_request.responded_by = current_user.id
        if notes:
            coverage_request.notes = f"{coverage_request.notes or ''}\n\nApproval Notes: {notes}".strip()

        db.commit()

        return MessageResponse(
            message="Coverage request approved successfully",
            success=True
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error approving coverage request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve coverage request"
        )

# Shift Swaps

@router.post("/shift-swaps", response_model=ShiftSwapResponse)
async def create_shift_swap(
    swap_data: ShiftSwapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "create"))
):
    """Create a shift swap between two staff members."""

    from app.models.scheduling import Shift, Schedule

    # Validate all shifts and staff belong to organization
    shift_a = db.query(Shift).join(Schedule).filter(
        Shift.id == swap_data.shift_a_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    shift_b = db.query(Shift).join(Schedule).filter(
        Shift.id == swap_data.shift_b_id,
        Schedule.organization_id == current_user.organization_id
    ).first()

    if not shift_a or not shift_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both shifts not found"
        )

    staff_a = db.query(Staff).filter(
        Staff.id == swap_data.staff_a_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    staff_b = db.query(Staff).filter(
        Staff.id == swap_data.staff_b_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff_a or not staff_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both staff members not found"
        )

    try:
        new_swap = ShiftSwap(
            coverage_request_id=swap_data.coverage_request_id,
            shift_a_id=swap_data.shift_a_id,
            shift_b_id=swap_data.shift_b_id,
            staff_a_id=swap_data.staff_a_id,
            staff_b_id=swap_data.staff_b_id,
            swap_date=swap_data.swap_date
        )

        db.add(new_swap)
        db.commit()
        db.refresh(new_swap)

        return ShiftSwapResponse.model_validate(new_swap)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating shift swap: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create shift swap"
        )

@router.get("/shift-swaps", response_model=List[ShiftSwapResponse])
async def get_shift_swaps(
    status: Optional[SwapStatus] = None,
    staff_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("scheduling", "read"))
):
    """Get shift swaps."""

    query = db.query(ShiftSwap).join(
        Staff, (ShiftSwap.staff_a_id == Staff.id) | (ShiftSwap.staff_b_id == Staff.id)
    ).filter(
        Staff.organization_id == current_user.organization_id
    )

    if status:
        query = query.filter(ShiftSwap.status == status)

    if staff_id:
        query = query.filter(
            (ShiftSwap.staff_a_id == staff_id) | (ShiftSwap.staff_b_id == staff_id)
        )

    if start_date:
        query = query.filter(ShiftSwap.swap_date >= start_date)

    if end_date:
        query = query.filter(ShiftSwap.swap_date <= end_date)

    swaps = query.order_by(ShiftSwap.swap_date.desc()).all()

    return [ShiftSwapResponse.model_validate(swap) for swap in swaps]