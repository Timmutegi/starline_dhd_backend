from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, date, time, timedelta
from app.core.database import get_db
from app.models.user import User
from app.models.staff import Staff
from app.models.scheduling import (
    CalendarEvent, Appointment, Shift, Schedule,
    EventType, EventVisibility
)
from app.middleware.auth import get_current_user, require_permission
from app.schemas.scheduling import (
    CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse,
    CalendarViewRequest, PaginatedResponse
)
from app.schemas.auth import MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/events", response_model=CalendarEventResponse)
async def create_calendar_event(
    event_data: CalendarEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("calendar", "create"))
):
    """Create a new calendar event."""

    # Validate attendees if provided
    if event_data.attendees:
        staff_count = db.query(Staff).filter(
            Staff.id.in_(event_data.attendees),
            Staff.organization_id == current_user.organization_id
        ).count()

        if staff_count != len(event_data.attendees):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Some attendees are not valid staff members"
            )

    try:
        new_event = CalendarEvent(
            organization_id=event_data.organization_id,
            event_type=event_data.event_type,
            title=event_data.title,
            description=event_data.description,
            start_datetime=event_data.start_datetime,
            end_datetime=event_data.end_datetime,
            location=event_data.location,
            all_day=event_data.all_day,
            is_recurring=event_data.is_recurring,
            recurrence_rule=event_data.recurrence_rule,
            attendees=event_data.attendees,
            color=event_data.color,
            visibility=event_data.visibility,
            created_by=current_user.id
        )

        db.add(new_event)
        db.commit()
        db.refresh(new_event)

        return CalendarEventResponse.model_validate(new_event)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating calendar event: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create calendar event"
        )

@router.get("/events", response_model=PaginatedResponse)
async def get_calendar_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    event_type: Optional[EventType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    attendee_id: Optional[UUID] = None,
    visibility: Optional[EventVisibility] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("calendar", "read"))
):
    """Get calendar events with filtering."""

    query = db.query(CalendarEvent).filter(
        CalendarEvent.organization_id == current_user.organization_id
    )

    # Apply filters
    if event_type:
        query = query.filter(CalendarEvent.event_type == event_type)

    if start_date:
        query = query.filter(CalendarEvent.start_datetime >= datetime.combine(start_date, time.min))

    if end_date:
        query = query.filter(CalendarEvent.end_datetime <= datetime.combine(end_date, time.max))

    if attendee_id:
        # Filter events where the attendee_id is in the attendees array
        query = query.filter(CalendarEvent.attendees.contains([attendee_id]))

    if visibility:
        query = query.filter(CalendarEvent.visibility == visibility)
    else:
        # Default to showing public and private events only (not confidential)
        query = query.filter(CalendarEvent.visibility.in_([EventVisibility.PUBLIC, EventVisibility.PRIVATE]))

    # Order by start datetime
    query = query.order_by(CalendarEvent.start_datetime)

    total = query.count()
    events = query.offset(skip).limit(limit).all()

    pages = (total + limit - 1) // limit

    return PaginatedResponse(
        items=[CalendarEventResponse.model_validate(e) for e in events],
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=pages
    )

@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_calendar_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("calendar", "read"))
):
    """Get calendar event details."""

    event = db.query(CalendarEvent).filter(
        CalendarEvent.id == event_id,
        CalendarEvent.organization_id == current_user.organization_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found"
        )

    return CalendarEventResponse.model_validate(event)

@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: UUID,
    event_update: CalendarEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("calendar", "update"))
):
    """Update calendar event."""

    event = db.query(CalendarEvent).filter(
        CalendarEvent.id == event_id,
        CalendarEvent.organization_id == current_user.organization_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found"
        )

    # Validate attendees if being updated
    if event_update.attendees:
        staff_count = db.query(Staff).filter(
            Staff.id.in_(event_update.attendees),
            Staff.organization_id == current_user.organization_id
        ).count()

        if staff_count != len(event_update.attendees):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Some attendees are not valid staff members"
            )

    try:
        # Update fields
        update_data = event_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(event, field, value)

        event.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(event)

        return CalendarEventResponse.model_validate(event)

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating calendar event: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update calendar event"
        )

@router.delete("/events/{event_id}", response_model=MessageResponse)
async def delete_calendar_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("calendar", "update"))
):
    """Delete calendar event."""

    event = db.query(CalendarEvent).filter(
        CalendarEvent.id == event_id,
        CalendarEvent.organization_id == current_user.organization_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found"
        )

    try:
        db.delete(event)
        db.commit()

        return MessageResponse(
            message="Calendar event deleted successfully",
            success=True
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting calendar event: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete calendar event"
        )

@router.post("/view", response_model=Dict[str, Any])
async def get_calendar_view(
    view_request: CalendarViewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("calendar", "read"))
):
    """Get unified calendar view with shifts, appointments, and events."""

    try:
        calendar_data = {
            "shifts": [],
            "appointments": [],
            "events": [],
            "time_off": [],
            "view_period": {
                "start_date": view_request.start_date.isoformat(),
                "end_date": view_request.end_date.isoformat()
            }
        }

        start_datetime = datetime.combine(view_request.start_date, time.min)
        end_datetime = datetime.combine(view_request.end_date, time.max)

        # Get shifts if requested
        if view_request.include_shifts:
            shift_query = db.query(Shift).join(Schedule).filter(
                Schedule.organization_id == current_user.organization_id,
                Shift.shift_date >= view_request.start_date,
                Shift.shift_date <= view_request.end_date
            )

            if view_request.staff_ids:
                shift_query = shift_query.filter(Shift.staff_id.in_(view_request.staff_ids))

            shifts = shift_query.all()

            for shift in shifts:
                shift_start = datetime.combine(shift.shift_date, shift.start_time)
                shift_end = datetime.combine(shift.shift_date, shift.end_time)

                calendar_data["shifts"].append({
                    "id": str(shift.id),
                    "type": "shift",
                    "title": f"Shift - {shift.staff.full_name if shift.staff else 'Unknown'}",
                    "start": shift_start.isoformat(),
                    "end": shift_end.isoformat(),
                    "staff_id": str(shift.staff_id),
                    "status": shift.status.value,
                    "shift_type": shift.shift_type.value,
                    "color": "#3B82F6"  # Blue for shifts
                })

        # Get appointments if requested
        if view_request.include_appointments:
            appointment_query = db.query(Appointment).filter(
                Appointment.organization_id == current_user.organization_id,
                Appointment.start_datetime >= start_datetime,
                Appointment.end_datetime <= end_datetime
            )

            if view_request.staff_ids:
                appointment_query = appointment_query.filter(Appointment.staff_id.in_(view_request.staff_ids))

            appointments = appointment_query.all()

            for appointment in appointments:
                calendar_data["appointments"].append({
                    "id": str(appointment.id),
                    "type": "appointment",
                    "title": appointment.title,
                    "start": appointment.start_datetime.isoformat(),
                    "end": appointment.end_datetime.isoformat(),
                    "staff_id": str(appointment.staff_id),
                    "client_id": str(appointment.client_id),
                    "appointment_type": appointment.appointment_type.value,
                    "status": appointment.status.value,
                    "location": appointment.location,
                    "color": "#10B981"  # Green for appointments
                })

        # Get events if requested
        if view_request.include_events:
            event_query = db.query(CalendarEvent).filter(
                CalendarEvent.organization_id == current_user.organization_id,
                CalendarEvent.start_datetime >= start_datetime,
                CalendarEvent.end_datetime <= end_datetime
            )

            events = event_query.all()

            for event in events:
                # Check if user should see this event based on visibility and attendees
                show_event = False

                if event.visibility == EventVisibility.PUBLIC:
                    show_event = True
                elif event.visibility == EventVisibility.PRIVATE:
                    # Show if user is creator or attendee
                    if event.created_by == current_user.id:
                        show_event = True
                    elif event.attendees and current_user.staff_profile:
                        show_event = current_user.staff_profile.id in event.attendees

                if show_event:
                    calendar_data["events"].append({
                        "id": str(event.id),
                        "type": "event",
                        "title": event.title,
                        "start": event.start_datetime.isoformat(),
                        "end": event.end_datetime.isoformat(),
                        "event_type": event.event_type.value,
                        "location": event.location,
                        "all_day": event.all_day,
                        "color": event.color,
                        "attendees": [str(attendee) for attendee in (event.attendees or [])]
                    })

        # Get time off if requested
        if view_request.include_time_off:
            from app.models.scheduling import TimeOffScheduling

            time_off_query = db.query(TimeOffScheduling).join(Staff).filter(
                Staff.organization_id == current_user.organization_id,
                TimeOffScheduling.start_datetime <= end_datetime,
                TimeOffScheduling.end_datetime >= start_datetime
            )

            if view_request.staff_ids:
                time_off_query = time_off_query.filter(TimeOffScheduling.staff_id.in_(view_request.staff_ids))

            time_off_requests = time_off_query.all()

            for time_off in time_off_requests:
                calendar_data["time_off"].append({
                    "id": str(time_off.id),
                    "type": "time_off",
                    "title": f"Time Off - {time_off.time_off_type.value.title()}",
                    "start": time_off.start_datetime.isoformat(),
                    "end": time_off.end_datetime.isoformat(),
                    "staff_id": str(time_off.staff_id),
                    "time_off_type": time_off.time_off_type.value,
                    "status": time_off.status.value,
                    "affects_scheduling": time_off.affects_scheduling,
                    "color": "#EF4444"  # Red for time off
                })

        return calendar_data

    except Exception as e:
        logger.error(f"Error getting calendar view: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get calendar view"
        )

@router.get("/ical/{calendar_id}")
async def export_calendar_ical(
    calendar_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("calendar", "read"))
):
    """Export calendar as iCal format."""

    try:
        # Generate iCal content
        ical_content = generate_ical_calendar(
            organization_id=current_user.organization_id,
            start_date=start_date,
            end_date=end_date,
            db=db
        )

        return Response(
            content=ical_content,
            media_type="text/calendar",
            headers={
                "Content-Disposition": f"attachment; filename=calendar_{calendar_id}.ics"
            }
        )

    except Exception as e:
        logger.error(f"Error exporting calendar: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export calendar"
        )

@router.post("/sync", response_model=MessageResponse, status_code=501)
async def sync_external_calendar(
    calendar_url: str = Query(..., description="External calendar URL (iCal, Google Calendar, Outlook)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("calendar", "update"))
):
    """
    Sync with external calendar systems.

    Future implementation will support:
    - Google Calendar API integration
    - Microsoft Outlook/Office 365 calendar sync
    - iCal/CalDAV subscriptions
    - Two-way synchronization of appointments and shifts
    - Conflict detection and resolution
    """
    from urllib.parse import urlparse

    # Validate URL format
    try:
        parsed_url = urlparse(calendar_url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid calendar URL format"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid calendar URL format"
        )

    # Return 501 Not Implemented with informative message
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "External calendar sync feature is planned but not yet implemented",
            "supported_formats": ["Google Calendar", "Microsoft Outlook", "iCal/CalDAV"],
            "requested_url": calendar_url,
            "contact": "Contact your system administrator for calendar integration requirements"
        }
    )

def generate_ical_calendar(
    organization_id: UUID,
    start_date: Optional[date],
    end_date: Optional[date],
    db: Session
) -> str:
    """Generate iCal format calendar content."""

    try:
        # Simple iCal generation (in a real implementation, use a proper iCal library)
        ical_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Starline//Scheduling Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH"
        ]

        # Query events, shifts, and appointments
        event_query = db.query(CalendarEvent).filter(
            CalendarEvent.organization_id == organization_id
        )

        if start_date:
            event_query = event_query.filter(
                CalendarEvent.start_datetime >= datetime.combine(start_date, time.min)
            )

        if end_date:
            event_query = event_query.filter(
                CalendarEvent.end_datetime <= datetime.combine(end_date, time.max)
            )

        events = event_query.all()

        for event in events:
            start_formatted = event.start_datetime.strftime("%Y%m%dT%H%M%SZ")
            end_formatted = event.end_datetime.strftime("%Y%m%dT%H%M%SZ")

            ical_lines.extend([
                "BEGIN:VEVENT",
                f"UID:{event.id}@starline.local",
                f"DTSTART:{start_formatted}",
                f"DTEND:{end_formatted}",
                f"SUMMARY:{event.title}",
                f"DESCRIPTION:{event.description or ''}",
                f"LOCATION:{event.location or ''}",
                f"STATUS:CONFIRMED",
                "END:VEVENT"
            ])

        ical_lines.append("END:VCALENDAR")

        return "\r\n".join(ical_lines)

    except Exception as e:
        logger.error(f"Error generating iCal: {str(e)}")
        raise