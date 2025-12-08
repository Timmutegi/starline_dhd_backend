from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, date, timezone
from typing import Optional, List
import uuid
import pytz
import logging

from app.core.database import get_db
from app.core.dependencies import get_manager_or_above
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.client import Client
from app.models.staff import Staff, StaffAssignment
from app.models.scheduling import Shift, ShiftStatus, TimeClockEntry, TimeEntryType
from app.models.special_requirement import (
    SpecialRequirement,
    SpecialRequirementResponse,
    PriorityLevel,
    RequirementStatus
)
from app.schemas.special_requirement import (
    SpecialRequirementCreate,
    SpecialRequirementUpdate,
    SpecialRequirementSchema,
    SpecialRequirementResponseCreate,
    SpecialRequirementResponseSchema,
    ActiveSpecialRequirementForDSP,
    PendingSpecialRequirement,
    PendingRequirementsAlert,
    ActionPlanItem
)

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== HELPER FUNCTIONS ====================
# Reusing validation patterns from documentation.py

def verify_client_assignment(db: Session, staff_user_id: str, client_id: str, organization_id: str) -> bool:
    """
    Verify that a client is assigned to the staff member.
    Returns True if the client is assigned, False otherwise.
    """
    staff = db.query(Staff).filter(
        Staff.user_id == staff_user_id,
        Staff.organization_id == organization_id
    ).first()

    if not staff:
        return False

    assignment = db.query(StaffAssignment).filter(
        and_(
            StaffAssignment.staff_id == staff.id,
            StaffAssignment.client_id == client_id,
            StaffAssignment.is_active == True
        )
    ).first()

    return assignment is not None


def verify_shift_time(db: Session, staff_user_id: str, client_id: str, organization_id: str, user_timezone: str = "UTC") -> tuple:
    """
    Verify that there's an active shift for this staff-client pair.
    Returns (is_valid, shift) tuple.
    """
    staff = db.query(Staff).filter(
        Staff.user_id == staff_user_id,
        Staff.organization_id == organization_id
    ).first()

    if not staff:
        return False, None

    try:
        tz = pytz.timezone(user_timezone)
    except Exception:
        tz = pytz.UTC

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    now_utc_aware = pytz.UTC.localize(now_utc)
    now_user_tz = now_utc_aware.astimezone(tz)
    current_date = now_user_tz.date()
    current_time = now_user_tz.time()

    active_shift = db.query(Shift).filter(
        and_(
            Shift.staff_id == staff.id,
            Shift.client_id == client_id,
            Shift.shift_date == current_date,
            Shift.start_time <= current_time,
            Shift.end_time >= current_time,
            Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.CONFIRMED, ShiftStatus.IN_PROGRESS])
        )
    ).first()

    return active_shift is not None, active_shift


def verify_clocked_in(db: Session, staff_user_id: str, organization_id: str) -> bool:
    """
    Verify that a staff member is currently clocked in.
    """
    staff = db.query(Staff).filter(
        Staff.user_id == staff_user_id,
        Staff.organization_id == organization_id
    ).first()

    if not staff:
        raise HTTPException(status_code=404, detail="Staff record not found")

    most_recent_clock_in = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff.id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    if not most_recent_clock_in:
        raise HTTPException(
            status_code=403,
            detail="You must clock in before submitting documentation. Please tap 'Time In' in the Shift Clock."
        )

    clock_out_after = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff.id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_OUT,
        TimeClockEntry.entry_datetime > most_recent_clock_in.entry_datetime
    ).first()

    if clock_out_after:
        raise HTTPException(
            status_code=403,
            detail="You must clock in before submitting documentation. Please tap 'Time In' in the Shift Clock."
        )

    return True


def is_requirement_active(requirement: SpecialRequirement, check_date: date = None) -> bool:
    """Check if a requirement is currently active based on status and date range"""
    if check_date is None:
        check_date = date.today()
    return (
        requirement.status == RequirementStatus.ACTIVE and
        requirement.start_date <= check_date <= requirement.end_date
    )


def generate_certification_statement(requirement: SpecialRequirement, staff: User, client: Client, shift: Shift) -> str:
    """Generate legal certification statement for DSP response"""
    shift_time = f"{shift.start_time} to {shift.end_time}" if shift else "during my assigned shift"
    acknowledged_count = len(requirement.action_plan_items) if requirement.action_plan_items else 0

    return f"""I, {staff.first_name} {staff.last_name}, certify that on {date.today()}, {shift_time}, I have:

1. Read and understood the special requirement "{requirement.title}" for client {client.first_name} {client.last_name}
2. Completed all {acknowledged_count} action plan items as specified
3. Documented my intervention as described above

This certification is made for legal compliance and client care documentation purposes.

Certified at: {datetime.now(timezone.utc).isoformat()}
Staff ID: {staff.id}"""


# ==================== MANAGER ENDPOINTS ====================

@router.post("/", response_model=SpecialRequirementSchema)
async def create_special_requirement(
    data: SpecialRequirementCreate,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    Create a new special requirement for a client.
    Only managers and above can create special requirements.
    """
    logger.info(f"Manager {current_user.id} creating special requirement for client {data.client_id}")

    # Verify client exists and belongs to organization
    client = db.query(Client).filter(
        and_(
            Client.id == data.client_id,
            Client.organization_id == current_user.organization_id
        )
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Prepare action plan items with UUIDs if not provided
    action_items = []
    for i, item in enumerate(data.action_plan_items):
        action_items.append({
            "id": item.id if item.id else str(uuid.uuid4()),
            "text": item.text,
            "order": item.order if item.order is not None else i
        })

    # Create the special requirement
    requirement = SpecialRequirement(
        id=uuid.uuid4(),
        organization_id=current_user.organization_id,
        client_id=data.client_id,
        created_by=current_user.id,
        title=data.title,
        instructions=data.instructions,
        action_plan_items=action_items,
        start_date=data.start_date,
        end_date=data.end_date,
        priority=PriorityLevel(data.priority.value),
        status=RequirementStatus.ACTIVE,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )

    db.add(requirement)
    db.commit()
    db.refresh(requirement)

    logger.info(f"Created special requirement {requirement.id}")

    return SpecialRequirementSchema(
        id=str(requirement.id),
        organization_id=str(requirement.organization_id),
        client_id=str(requirement.client_id),
        client_name=f"{client.first_name} {client.last_name}",
        created_by=str(requirement.created_by) if requirement.created_by else None,
        created_by_name=f"{current_user.first_name} {current_user.last_name}",
        title=requirement.title,
        instructions=requirement.instructions,
        action_plan_items=[ActionPlanItem(**item) for item in requirement.action_plan_items],
        start_date=requirement.start_date,
        end_date=requirement.end_date,
        priority=requirement.priority.value,
        status=requirement.status.value,
        is_active=is_requirement_active(requirement),
        response_count=0,
        created_at=requirement.created_at,
        updated_at=requirement.updated_at
    )


@router.get("/", response_model=dict)
async def list_special_requirements(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    active_only: bool = Query(False, description="Only return currently active requirements"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """
    List special requirements for the organization.
    Only managers and above can list all requirements.
    """
    query = db.query(SpecialRequirement).filter(
        SpecialRequirement.organization_id == current_user.organization_id
    )

    if client_id:
        query = query.filter(SpecialRequirement.client_id == client_id)

    if status:
        query = query.filter(SpecialRequirement.status == RequirementStatus(status))

    if priority:
        query = query.filter(SpecialRequirement.priority == PriorityLevel(priority))

    if active_only:
        today = date.today()
        query = query.filter(
            and_(
                SpecialRequirement.status == RequirementStatus.ACTIVE,
                SpecialRequirement.start_date <= today,
                SpecialRequirement.end_date >= today
            )
        )

    total = query.count()
    requirements = query.order_by(SpecialRequirement.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for req in requirements:
        client = db.query(Client).filter(Client.id == req.client_id).first()
        creator = db.query(User).filter(User.id == req.created_by).first() if req.created_by else None
        response_count = db.query(SpecialRequirementResponse).filter(
            SpecialRequirementResponse.special_requirement_id == req.id
        ).count()

        results.append(SpecialRequirementSchema(
            id=str(req.id),
            organization_id=str(req.organization_id),
            client_id=str(req.client_id),
            client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
            created_by=str(req.created_by) if req.created_by else None,
            created_by_name=f"{creator.first_name} {creator.last_name}" if creator else None,
            title=req.title,
            instructions=req.instructions,
            action_plan_items=[ActionPlanItem(**item) for item in req.action_plan_items],
            start_date=req.start_date,
            end_date=req.end_date,
            priority=req.priority.value,
            status=req.status.value,
            is_active=is_requirement_active(req),
            response_count=response_count,
            created_at=req.created_at,
            updated_at=req.updated_at
        ))

    return {
        "data": results,
        "pagination": {
            "total": total,
            "page": (offset // limit) + 1 if limit > 0 else 1,
            "page_size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
    }


# ==================== DSP ENDPOINTS (BEFORE PARAMETERIZED ROUTES) ====================
# These must be defined BEFORE /{requirement_id} to avoid route conflicts

@router.get("/my-pending", response_model=PendingRequirementsAlert)
async def get_my_pending_requirements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all pending special requirements for DSP's currently scheduled clients.
    Used to show prominent alerts on DSP dashboard.
    """
    logger.info(f"DSP {current_user.id} fetching pending requirements")

    # Get staff record
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        return PendingRequirementsAlert(
            total_pending=0,
            highest_priority="low",
            requirements=[]
        )

    # Get current timezone and date
    user_tz = current_user.timezone or "UTC"
    try:
        tz = pytz.timezone(user_tz)
    except Exception:
        tz = pytz.UTC

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    now_utc_aware = pytz.UTC.localize(now_utc)
    now_user_tz = now_utc_aware.astimezone(tz)
    current_date = now_user_tz.date()
    current_time = now_user_tz.time()

    # Get active shifts for today
    active_shifts = db.query(Shift).filter(
        and_(
            Shift.staff_id == staff.id,
            Shift.shift_date == current_date,
            Shift.start_time <= current_time,
            Shift.end_time >= current_time,
            Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.CONFIRMED, ShiftStatus.IN_PROGRESS])
        )
    ).all()

    if not active_shifts:
        return PendingRequirementsAlert(
            total_pending=0,
            highest_priority="low",
            requirements=[]
        )

    pending_requirements = []
    highest_priority = "low"
    priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    for shift in active_shifts:
        # Get active requirements for this client
        requirements = db.query(SpecialRequirement).filter(
            and_(
                SpecialRequirement.client_id == shift.client_id,
                SpecialRequirement.organization_id == current_user.organization_id,
                SpecialRequirement.status == RequirementStatus.ACTIVE,
                SpecialRequirement.start_date <= current_date,
                SpecialRequirement.end_date >= current_date
            )
        ).all()

        for req in requirements:
            # Check if already responded this shift
            existing_response = db.query(SpecialRequirementResponse).filter(
                and_(
                    SpecialRequirementResponse.special_requirement_id == req.id,
                    SpecialRequirementResponse.staff_id == current_user.id,
                    SpecialRequirementResponse.shift_id == shift.id
                )
            ).first()

            if not existing_response:
                client = db.query(Client).filter(Client.id == req.client_id).first()
                pending_requirements.append(PendingSpecialRequirement(
                    id=str(req.id),
                    title=req.title,
                    priority=req.priority.value,
                    client_id=str(req.client_id),
                    client_name=f"{client.first_name} {client.last_name}" if client else "Unknown"
                ))

                # Track highest priority
                if priority_order.get(req.priority.value, 0) > priority_order.get(highest_priority, 0):
                    highest_priority = req.priority.value

    return PendingRequirementsAlert(
        total_pending=len(pending_requirements),
        highest_priority=highest_priority,
        requirements=pending_requirements
    )


@router.get("/my-history", response_model=dict)
async def get_my_special_requirements_history(
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get DSP's history of completed special requirement responses.
    This allows DSPs to view their past responses even when not on an active shift.
    """
    logger.info(f"DSP {current_user.id} fetching special requirements history")

    # Query all responses by this staff member
    # Note: staff_id stores the user's ID directly, not the staff record ID
    query = db.query(SpecialRequirementResponse).filter(
        SpecialRequirementResponse.staff_id == current_user.id
    )

    logger.info(f"Querying responses for staff_id: {current_user.id}")

    total = query.count()
    logger.info(f"Found {total} total responses for staff_id: {current_user.id}")

    responses = query.order_by(SpecialRequirementResponse.created_at.desc()).offset(offset).limit(limit).all()
    logger.info(f"Retrieved {len(responses)} responses after pagination")

    results = []
    for resp in responses:
        logger.info(f"Processing response: {resp.id}, staff_id: {resp.staff_id}")
        # Get requirement details
        requirement = db.query(SpecialRequirement).filter(
            SpecialRequirement.id == resp.special_requirement_id
        ).first()

        # Get client details
        client = db.query(Client).filter(Client.id == resp.client_id).first()

        if requirement:
            results.append({
                "id": str(resp.id),
                "special_requirement_id": str(resp.special_requirement_id),
                "requirement_title": requirement.title,
                "requirement_instructions": requirement.instructions,
                "requirement_priority": requirement.priority.value,
                "action_plan_items": [ActionPlanItem(**item) for item in requirement.action_plan_items],
                "client_id": str(resp.client_id),
                "client_name": f"{client.first_name} {client.last_name}" if client else "Unknown",
                "instructions_acknowledged": resp.instructions_acknowledged,
                "acknowledged_items": resp.acknowledged_items,
                "intervention_notes": resp.intervention_notes,
                "is_certified": resp.is_certified,
                "shift_date": resp.shift_date,
                "shift_start_time": resp.shift_start_time,
                "shift_end_time": resp.shift_end_time,
                "created_at": resp.created_at,
            })
        else:
            logger.warning(f"Requirement not found for response: {resp.id}")

    logger.info(f"Returning {len(results)} results")

    return {
        "data": results,
        "pagination": {
            "total": total,
            "page": (offset // limit) + 1 if limit > 0 else 1,
            "page_size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
    }


# ==================== MANAGER ENDPOINTS WITH PATH PARAMETERS ====================

@router.get("/{requirement_id}", response_model=SpecialRequirementSchema)
async def get_special_requirement(
    requirement_id: str,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get a specific special requirement by ID."""
    requirement = db.query(SpecialRequirement).filter(
        and_(
            SpecialRequirement.id == requirement_id,
            SpecialRequirement.organization_id == current_user.organization_id
        )
    ).first()

    if not requirement:
        raise HTTPException(status_code=404, detail="Special requirement not found")

    client = db.query(Client).filter(Client.id == requirement.client_id).first()
    creator = db.query(User).filter(User.id == requirement.created_by).first() if requirement.created_by else None
    response_count = db.query(SpecialRequirementResponse).filter(
        SpecialRequirementResponse.special_requirement_id == requirement.id
    ).count()

    return SpecialRequirementSchema(
        id=str(requirement.id),
        organization_id=str(requirement.organization_id),
        client_id=str(requirement.client_id),
        client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
        created_by=str(requirement.created_by) if requirement.created_by else None,
        created_by_name=f"{creator.first_name} {creator.last_name}" if creator else None,
        title=requirement.title,
        instructions=requirement.instructions,
        action_plan_items=[ActionPlanItem(**item) for item in requirement.action_plan_items],
        start_date=requirement.start_date,
        end_date=requirement.end_date,
        priority=requirement.priority.value,
        status=requirement.status.value,
        is_active=is_requirement_active(requirement),
        response_count=response_count,
        created_at=requirement.created_at,
        updated_at=requirement.updated_at
    )


@router.put("/{requirement_id}", response_model=SpecialRequirementSchema)
async def update_special_requirement(
    requirement_id: str,
    data: SpecialRequirementUpdate,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Update a special requirement."""
    requirement = db.query(SpecialRequirement).filter(
        and_(
            SpecialRequirement.id == requirement_id,
            SpecialRequirement.organization_id == current_user.organization_id
        )
    ).first()

    if not requirement:
        raise HTTPException(status_code=404, detail="Special requirement not found")

    # Update fields if provided
    if data.title is not None:
        requirement.title = data.title
    if data.instructions is not None:
        requirement.instructions = data.instructions
    if data.action_plan_items is not None:
        action_items = []
        for i, item in enumerate(data.action_plan_items):
            action_items.append({
                "id": item.id if item.id else str(uuid.uuid4()),
                "text": item.text,
                "order": item.order if item.order is not None else i
            })
        requirement.action_plan_items = action_items
    if data.start_date is not None:
        requirement.start_date = data.start_date
    if data.end_date is not None:
        requirement.end_date = data.end_date
    if data.priority is not None:
        requirement.priority = PriorityLevel(data.priority.value)
    if data.status is not None:
        requirement.status = RequirementStatus(data.status.value)

    requirement.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(requirement)

    client = db.query(Client).filter(Client.id == requirement.client_id).first()
    creator = db.query(User).filter(User.id == requirement.created_by).first() if requirement.created_by else None
    response_count = db.query(SpecialRequirementResponse).filter(
        SpecialRequirementResponse.special_requirement_id == requirement.id
    ).count()

    return SpecialRequirementSchema(
        id=str(requirement.id),
        organization_id=str(requirement.organization_id),
        client_id=str(requirement.client_id),
        client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
        created_by=str(requirement.created_by) if requirement.created_by else None,
        created_by_name=f"{creator.first_name} {creator.last_name}" if creator else None,
        title=requirement.title,
        instructions=requirement.instructions,
        action_plan_items=[ActionPlanItem(**item) for item in requirement.action_plan_items],
        start_date=requirement.start_date,
        end_date=requirement.end_date,
        priority=requirement.priority.value,
        status=requirement.status.value,
        is_active=is_requirement_active(requirement),
        response_count=response_count,
        created_at=requirement.created_at,
        updated_at=requirement.updated_at
    )


@router.post("/{requirement_id}/deactivate")
async def deactivate_special_requirement(
    requirement_id: str,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Deactivate a special requirement."""
    requirement = db.query(SpecialRequirement).filter(
        and_(
            SpecialRequirement.id == requirement_id,
            SpecialRequirement.organization_id == current_user.organization_id
        )
    ).first()

    if not requirement:
        raise HTTPException(status_code=404, detail="Special requirement not found")

    requirement.status = RequirementStatus.INACTIVE
    requirement.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()

    return {"message": "Special requirement deactivated", "id": requirement_id}


@router.get("/{requirement_id}/responses", response_model=dict)
async def get_requirement_responses(
    requirement_id: str,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    staff_id: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get all DSP responses for a specific requirement."""
    # Verify requirement exists
    requirement = db.query(SpecialRequirement).filter(
        and_(
            SpecialRequirement.id == requirement_id,
            SpecialRequirement.organization_id == current_user.organization_id
        )
    ).first()

    if not requirement:
        raise HTTPException(status_code=404, detail="Special requirement not found")

    query = db.query(SpecialRequirementResponse).filter(
        SpecialRequirementResponse.special_requirement_id == requirement_id
    )

    if date_from:
        query = query.filter(SpecialRequirementResponse.shift_date >= date_from)
    if date_to:
        query = query.filter(SpecialRequirementResponse.shift_date <= date_to)
    if staff_id:
        query = query.filter(SpecialRequirementResponse.staff_id == staff_id)

    total = query.count()
    responses = query.order_by(SpecialRequirementResponse.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for resp in responses:
        client = db.query(Client).filter(Client.id == resp.client_id).first()
        staff = db.query(User).filter(User.id == resp.staff_id).first() if resp.staff_id else None

        results.append(SpecialRequirementResponseSchema(
            id=str(resp.id),
            special_requirement_id=str(resp.special_requirement_id),
            requirement_title=requirement.title,
            client_id=str(resp.client_id),
            client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
            staff_id=str(resp.staff_id) if resp.staff_id else "",
            staff_name=f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
            shift_id=str(resp.shift_id) if resp.shift_id else None,
            instructions_acknowledged=resp.instructions_acknowledged,
            acknowledged_items=resp.acknowledged_items,
            intervention_notes=resp.intervention_notes,
            is_certified=resp.is_certified,
            certification_statement=resp.certification_statement,
            certified_at=resp.certified_at,
            shift_date=resp.shift_date,
            shift_start_time=resp.shift_start_time,
            shift_end_time=resp.shift_end_time,
            created_at=resp.created_at,
            updated_at=resp.updated_at
        ))

    return {
        "data": results,
        "pagination": {
            "total": total,
            "page": (offset // limit) + 1 if limit > 0 else 1,
            "page_size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
    }


# ==================== DSP ENDPOINTS ====================

@router.get("/client/{client_id}/active", response_model=List[ActiveSpecialRequirementForDSP])
async def get_active_requirements_for_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get active special requirements for a client (DSP view).
    Includes whether DSP has already responded this shift.
    Uses same 3-layer validation as documentation endpoints.
    """
    logger.info(f"DSP {current_user.id} fetching active requirements for client {client_id}")

    # Verify client exists and belongs to organization
    client = db.query(Client).filter(
        and_(
            Client.id == client_id,
            Client.organization_id == current_user.organization_id
        )
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify client assignment
    if not verify_client_assignment(db, current_user.id, client_id, current_user.organization_id):
        raise HTTPException(
            status_code=403,
            detail="You can only view requirements for clients assigned to you"
        )

    # Get current shift
    user_tz = current_user.timezone or "UTC"
    is_on_shift, active_shift = verify_shift_time(db, current_user.id, client_id, current_user.organization_id, user_tz)

    # Get active requirements for this client
    today = date.today()
    requirements = db.query(SpecialRequirement).filter(
        and_(
            SpecialRequirement.client_id == client_id,
            SpecialRequirement.organization_id == current_user.organization_id,
            SpecialRequirement.status == RequirementStatus.ACTIVE,
            SpecialRequirement.start_date <= today,
            SpecialRequirement.end_date >= today
        )
    ).order_by(SpecialRequirement.priority.desc()).all()

    results = []
    for req in requirements:
        # Check if DSP has already responded this shift
        existing_response = None
        if active_shift:
            existing_response = db.query(SpecialRequirementResponse).filter(
                and_(
                    SpecialRequirementResponse.special_requirement_id == req.id,
                    SpecialRequirementResponse.staff_id == current_user.id,
                    SpecialRequirementResponse.shift_id == active_shift.id
                )
            ).first()

        results.append(ActiveSpecialRequirementForDSP(
            id=str(req.id),
            title=req.title,
            instructions=req.instructions,
            action_plan_items=[ActionPlanItem(**item) for item in req.action_plan_items],
            priority=req.priority.value,
            client_id=str(req.client_id),
            client_name=f"{client.first_name} {client.last_name}",
            start_date=req.start_date,
            end_date=req.end_date,
            has_response_this_shift=existing_response is not None,
            existing_response_id=str(existing_response.id) if existing_response else None
        ))

    return results


@router.post("/responses", response_model=SpecialRequirementResponseSchema)
async def submit_requirement_response(
    data: SpecialRequirementResponseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit DSP response/certification for a special requirement.
    Uses same 3-layer validation as other documentation:
    1. verify_client_assignment()
    2. verify_shift_time()
    3. verify_clocked_in()
    """
    logger.info(f"DSP {current_user.id} submitting response for requirement {data.special_requirement_id}")

    # Verify requirement exists
    requirement = db.query(SpecialRequirement).filter(
        and_(
            SpecialRequirement.id == data.special_requirement_id,
            SpecialRequirement.organization_id == current_user.organization_id
        )
    ).first()

    if not requirement:
        raise HTTPException(status_code=404, detail="Special requirement not found")

    # Verify requirement is active
    if not is_requirement_active(requirement):
        raise HTTPException(status_code=400, detail="This special requirement is not currently active")

    # Verify client exists
    client = db.query(Client).filter(
        and_(
            Client.id == data.client_id,
            Client.organization_id == current_user.organization_id
        )
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify requirement is for this client
    if str(requirement.client_id) != data.client_id:
        raise HTTPException(status_code=400, detail="This requirement is not for the specified client")

    # 1. Verify client assignment
    if not verify_client_assignment(db, current_user.id, data.client_id, current_user.organization_id):
        raise HTTPException(
            status_code=403,
            detail="You can only submit responses for clients assigned to you"
        )

    # 2. Verify shift time and get active shift
    user_tz = current_user.timezone or "UTC"
    is_on_shift, active_shift = verify_shift_time(db, current_user.id, data.client_id, current_user.organization_id, user_tz)

    if not is_on_shift or not active_shift:
        raise HTTPException(
            status_code=403,
            detail="You can only submit responses during your scheduled shift time"
        )

    # 3. Verify clocked in
    verify_clocked_in(db, current_user.id, current_user.organization_id)

    # Check if already responded this shift
    existing_response = db.query(SpecialRequirementResponse).filter(
        and_(
            SpecialRequirementResponse.special_requirement_id == data.special_requirement_id,
            SpecialRequirementResponse.staff_id == current_user.id,
            SpecialRequirementResponse.shift_id == active_shift.id
        )
    ).first()

    if existing_response:
        raise HTTPException(
            status_code=400,
            detail="You have already submitted a response for this requirement during this shift"
        )

    # Validate all action items are acknowledged
    required_item_ids = {item["id"] for item in requirement.action_plan_items}
    acknowledged_ids = set(data.acknowledged_items)

    if not required_item_ids.issubset(acknowledged_ids):
        missing_count = len(required_item_ids - acknowledged_ids)
        raise HTTPException(
            status_code=400,
            detail=f"You must acknowledge all {len(required_item_ids)} action plan items. {missing_count} items are missing."
        )

    # Generate certification statement
    certification_statement = generate_certification_statement(requirement, current_user, client, active_shift)
    certified_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create response
    response = SpecialRequirementResponse(
        id=uuid.uuid4(),
        organization_id=current_user.organization_id,
        special_requirement_id=data.special_requirement_id,
        client_id=data.client_id,
        staff_id=current_user.id,
        shift_id=active_shift.id,
        instructions_acknowledged=data.instructions_acknowledged,
        acknowledged_items=data.acknowledged_items,
        intervention_notes=data.intervention_notes,
        is_certified=data.is_certified,
        certification_statement=certification_statement,
        certified_at=certified_at,
        shift_date=active_shift.shift_date,
        shift_start_time=str(active_shift.start_time) if active_shift.start_time else None,
        shift_end_time=str(active_shift.end_time) if active_shift.end_time else None,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )

    db.add(response)
    db.commit()
    db.refresh(response)

    logger.info(f"Created special requirement response {response.id}")

    return SpecialRequirementResponseSchema(
        id=str(response.id),
        special_requirement_id=str(response.special_requirement_id),
        requirement_title=requirement.title,
        client_id=str(response.client_id),
        client_name=f"{client.first_name} {client.last_name}",
        staff_id=str(response.staff_id),
        staff_name=f"{current_user.first_name} {current_user.last_name}",
        shift_id=str(response.shift_id) if response.shift_id else None,
        instructions_acknowledged=response.instructions_acknowledged,
        acknowledged_items=response.acknowledged_items,
        intervention_notes=response.intervention_notes,
        is_certified=response.is_certified,
        certification_statement=response.certification_statement,
        certified_at=response.certified_at,
        shift_date=response.shift_date,
        shift_start_time=response.shift_start_time,
        shift_end_time=response.shift_end_time,
        created_at=response.created_at,
        updated_at=response.updated_at
    )
