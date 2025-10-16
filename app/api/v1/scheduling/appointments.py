from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from datetime import datetime, date, time, timedelta
from app.core.database import get_db
from app.models.user import User
from app.models.staff import Staff
from app.models.client import Client
from app.models.scheduling import (
    Appointment, RecurringAppointment, AppointmentStatus, AppointmentType,
    RecurrencePattern
)
from app.middleware.auth import get_current_user, require_permission
from app.schemas.scheduling import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    RecurringAppointmentCreate, RecurringAppointmentUpdate, RecurringAppointmentResponse
)
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.auth import MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Regular Appointments

@router.post("/", response_model=AppointmentResponse)
async def create_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "create"))
):
    """Create a new appointment."""

    # Validate client
    client = db.query(Client).filter(
        Client.id == appointment_data.client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Validate staff
    staff = db.query(Staff).filter(
        Staff.id == appointment_data.staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Validate transport staff if provided
    transport_staff = None
    if appointment_data.transport_staff_id:
        transport_staff = db.query(Staff).filter(
            Staff.id == appointment_data.transport_staff_id,
            Staff.organization_id == current_user.organization_id
        ).first()

        if not transport_staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transport staff not found"
            )

    # Check for scheduling conflicts
    conflict_check = db.query(Appointment).filter(
        Appointment.staff_id == appointment_data.staff_id,
        Appointment.status != AppointmentStatus.CANCELLED,
        Appointment.start_datetime < appointment_data.end_datetime,
        Appointment.end_datetime > appointment_data.start_datetime
    ).first()

    if conflict_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff member has a conflicting appointment"
        )

    try:
        new_appointment = Appointment(
            organization_id=appointment_data.organization_id,
            client_id=appointment_data.client_id,
            staff_id=appointment_data.staff_id,
            appointment_type=appointment_data.appointment_type,
            title=appointment_data.title,
            description=appointment_data.description,
            location=appointment_data.location,
            start_datetime=appointment_data.start_datetime,
            end_datetime=appointment_data.end_datetime,
            requires_transport=appointment_data.requires_transport,
            transport_staff_id=appointment_data.transport_staff_id,
            notes=appointment_data.notes
        )

        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)

        return AppointmentResponse.model_validate(new_appointment)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating appointment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create appointment"
        )

@router.get("/")
async def get_appointments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    client_id: Optional[UUID] = None,
    staff_id: Optional[UUID] = None,
    appointment_type: Optional[AppointmentType] = None,
    status: Optional[AppointmentStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "read"))
):
    """Get list of appointments with filtering."""

    query = db.query(Appointment).filter(
        Appointment.organization_id == current_user.organization_id
    )

    # If user is Support Staff (DSP), only show their appointments
    if current_user.role and current_user.role.name == "Support Staff":
        # Get staff record for current user to filter by staff_id
        staff = db.query(Staff).filter(Staff.user_id == current_user.id).first()
        if staff:
            query = query.filter(Appointment.staff_id == staff.id)
        else:
            # If no staff record, return empty result
            query = query.filter(Appointment.id == None)

    # Apply filters
    if client_id:
        query = query.filter(Appointment.client_id == client_id)

    if staff_id:
        # Only allow filtering by staff_id if user is not Support Staff
        if not (current_user.role and current_user.role.name == "Support Staff"):
            query = query.filter(Appointment.staff_id == staff_id)

    if appointment_type:
        query = query.filter(Appointment.appointment_type == appointment_type)

    if status:
        query = query.filter(Appointment.status == status)

    if start_date:
        query = query.filter(Appointment.start_datetime >= datetime.combine(start_date, time.min))

    if end_date:
        query = query.filter(Appointment.end_datetime <= datetime.combine(end_date, time.max))

    # Order by start datetime
    query = query.order_by(Appointment.start_datetime)

    total = query.count()
    appointments = query.offset(skip).limit(limit).all()

    pages = (total + limit - 1) // limit

    # Enrich appointments with client and staff names
    enriched_appointments = []
    for appointment in appointments:
        client = db.query(Client).filter(Client.id == appointment.client_id).first()
        staff = db.query(User).filter(User.id == appointment.staff_id).first()

        appointment_dict = {
            "id": str(appointment.id),
            "client_id": str(appointment.client_id),
            "client_name": f"{client.first_name} {client.last_name}" if client else "Unknown",
            "staff_id": str(appointment.staff_id),
            "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
            "appointment_type": appointment.appointment_type.value if hasattr(appointment.appointment_type, 'value') else str(appointment.appointment_type),
            "title": appointment.title,
            "description": appointment.description,
            "location": appointment.location,
            "start_datetime": appointment.start_datetime.isoformat(),
            "end_datetime": appointment.end_datetime.isoformat(),
            "scheduled_time": appointment.start_datetime.strftime("%I:%M %p"),
            "status": appointment.status.value if hasattr(appointment.status, 'value') else str(appointment.status),
            "created_at": appointment.created_at.isoformat(),
            "updated_at": appointment.updated_at.isoformat()
        }
        enriched_appointments.append(appointment_dict)

    return PaginatedResponse(
        data=enriched_appointments,
        pagination=PaginationMeta(
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
            pages=pages
        )
    )

@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "read"))
):
    """Get appointment details."""

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.organization_id == current_user.organization_id
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )

    return AppointmentResponse.model_validate(appointment)

@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: UUID,
    appointment_update: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "update"))
):
    """Update appointment."""

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.organization_id == current_user.organization_id
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )

    # Validate staff if being updated
    if appointment_update.staff_id:
        staff = db.query(Staff).filter(
            Staff.id == appointment_update.staff_id,
            Staff.organization_id == current_user.organization_id
        ).first()

        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found"
            )

    # Check for conflicts if datetime is being updated
    if appointment_update.start_datetime or appointment_update.end_datetime:
        start_time = appointment_update.start_datetime or appointment.start_datetime
        end_time = appointment_update.end_datetime or appointment.end_datetime
        staff_id = appointment_update.staff_id or appointment.staff_id

        conflict_check = db.query(Appointment).filter(
            Appointment.staff_id == staff_id,
            Appointment.id != appointment_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_datetime < end_time,
            Appointment.end_datetime > start_time
        ).first()

        if conflict_check:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Staff member has a conflicting appointment"
            )

    try:
        # Update fields
        update_data = appointment_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(appointment, field, value)

        appointment.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(appointment)

        return AppointmentResponse.model_validate(appointment)

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating appointment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update appointment"
        )

@router.delete("/{appointment_id}", response_model=MessageResponse)
async def cancel_appointment(
    appointment_id: UUID,
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "update"))
):
    """Cancel an appointment."""

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.organization_id == current_user.organization_id
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )

    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is already cancelled"
        )

    appointment.status = AppointmentStatus.CANCELLED
    if reason:
        appointment.notes = f"{appointment.notes or ''}\n\nCancelled: {reason}".strip()

    appointment.updated_at = datetime.utcnow()
    db.commit()

    return MessageResponse(
        message="Appointment cancelled successfully",
        success=True
    )

@router.get("/clients/{client_id}/appointments", response_model=List[AppointmentResponse])
async def get_client_appointments(
    client_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[AppointmentStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "read"))
):
    """Get appointments for a specific client."""

    # Validate client
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    query = db.query(Appointment).filter(
        Appointment.client_id == client_id,
        Appointment.organization_id == current_user.organization_id
    )

    if start_date:
        query = query.filter(Appointment.start_datetime >= datetime.combine(start_date, time.min))

    if end_date:
        query = query.filter(Appointment.end_datetime <= datetime.combine(end_date, time.max))

    if status:
        query = query.filter(Appointment.status == status)

    appointments = query.order_by(Appointment.start_datetime).limit(limit).all()

    return [AppointmentResponse.model_validate(a) for a in appointments]

# Recurring Appointments

@router.post("/recurring", response_model=RecurringAppointmentResponse)
async def create_recurring_appointment(
    recurring_data: RecurringAppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "create"))
):
    """Create a new recurring appointment."""

    # Validate client
    client = db.query(Client).filter(
        Client.id == recurring_data.client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Validate staff
    staff = db.query(Staff).filter(
        Staff.id == recurring_data.staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    try:
        new_recurring = RecurringAppointment(
            organization_id=recurring_data.organization_id,
            client_id=recurring_data.client_id,
            staff_id=recurring_data.staff_id,
            appointment_type=recurring_data.appointment_type,
            title=recurring_data.title,
            description=recurring_data.description,
            location=recurring_data.location,
            start_time=recurring_data.start_time,
            duration_minutes=recurring_data.duration_minutes,
            recurrence_pattern=recurring_data.recurrence_pattern,
            recurrence_days=recurring_data.recurrence_days,
            start_date=recurring_data.start_date,
            end_date=recurring_data.end_date,
            max_occurrences=recurring_data.max_occurrences
        )

        db.add(new_recurring)
        db.commit()
        db.refresh(new_recurring)

        return RecurringAppointmentResponse.model_validate(new_recurring)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating recurring appointment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create recurring appointment"
        )

@router.get("/recurring", response_model=List[RecurringAppointmentResponse])
async def get_recurring_appointments(
    client_id: Optional[UUID] = None,
    staff_id: Optional[UUID] = None,
    active_only: bool = Query(True, description="Only return active recurring appointments"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "read"))
):
    """Get list of recurring appointments."""

    query = db.query(RecurringAppointment).filter(
        RecurringAppointment.organization_id == current_user.organization_id
    )

    if client_id:
        query = query.filter(RecurringAppointment.client_id == client_id)

    if staff_id:
        query = query.filter(RecurringAppointment.staff_id == staff_id)

    if active_only:
        query = query.filter(RecurringAppointment.is_active == True)

    recurring_appointments = query.all()

    return [RecurringAppointmentResponse.model_validate(ra) for ra in recurring_appointments]

@router.put("/recurring/{recurring_id}", response_model=RecurringAppointmentResponse)
async def update_recurring_appointment(
    recurring_id: UUID,
    recurring_update: RecurringAppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "update"))
):
    """Update recurring appointment."""

    recurring = db.query(RecurringAppointment).filter(
        RecurringAppointment.id == recurring_id,
        RecurringAppointment.organization_id == current_user.organization_id
    ).first()

    if not recurring:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring appointment not found"
        )

    try:
        # Update fields
        update_data = recurring_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(recurring, field, value)

        recurring.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(recurring)

        return RecurringAppointmentResponse.model_validate(recurring)

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating recurring appointment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update recurring appointment"
        )

@router.post("/recurring/{recurring_id}/generate", response_model=List[AppointmentResponse])
async def generate_appointment_instances(
    recurring_id: UUID,
    start_date: date = Query(..., description="Start date for generation"),
    end_date: date = Query(..., description="End date for generation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("appointments", "create"))
):
    """Generate appointment instances from recurring appointment."""

    recurring = db.query(RecurringAppointment).filter(
        RecurringAppointment.id == recurring_id,
        RecurringAppointment.organization_id == current_user.organization_id
    ).first()

    if not recurring:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring appointment not found"
        )

    if not recurring.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recurring appointment is not active"
        )

    try:
        created_appointments = []
        current_date = max(start_date, recurring.start_date)
        generation_end = min(end_date, recurring.end_date) if recurring.end_date else end_date

        occurrences_created = 0
        max_occurrences = recurring.max_occurrences or 1000  # Safety limit

        while current_date <= generation_end and occurrences_created < max_occurrences:
            should_create = False

            if recurring.recurrence_pattern == RecurrencePattern.DAILY:
                should_create = True
                next_date = current_date + timedelta(days=1)

            elif recurring.recurrence_pattern == RecurrencePattern.WEEKLY:
                if recurring.recurrence_days:
                    weekday = current_date.weekday() + 1  # Convert to 1-7 format
                    if weekday in recurring.recurrence_days:
                        should_create = True
                next_date = current_date + timedelta(days=1)

            elif recurring.recurrence_pattern == RecurrencePattern.MONTHLY:
                if current_date.day == recurring.start_date.day:
                    should_create = True
                # Move to next month
                if current_date.month == 12:
                    next_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    next_date = current_date.replace(month=current_date.month + 1)

            else:
                # Custom pattern not implemented
                break

            if should_create:
                # Check if appointment already exists for this date
                start_datetime = datetime.combine(current_date, recurring.start_time)
                end_datetime = start_datetime + timedelta(minutes=recurring.duration_minutes)

                existing = db.query(Appointment).filter(
                    Appointment.client_id == recurring.client_id,
                    Appointment.staff_id == recurring.staff_id,
                    Appointment.start_datetime == start_datetime
                ).first()

                if not existing:
                    new_appointment = Appointment(
                        organization_id=recurring.organization_id,
                        client_id=recurring.client_id,
                        staff_id=recurring.staff_id,
                        appointment_type=AppointmentType.MEDICAL,  # Default type for recurring
                        title=recurring.title,
                        description=recurring.description,
                        location=recurring.location,
                        start_datetime=start_datetime,
                        end_datetime=end_datetime,
                        notes=f"Generated from recurring appointment: {recurring.title}"
                    )

                    db.add(new_appointment)
                    created_appointments.append(new_appointment)
                    occurrences_created += 1

            current_date = next_date

        db.commit()

        # Refresh all created appointments
        for appointment in created_appointments:
            db.refresh(appointment)

        return [AppointmentResponse.model_validate(a) for a in created_appointments]

    except Exception as e:
        db.rollback()
        logger.error(f"Error generating appointment instances: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate appointment instances"
        )