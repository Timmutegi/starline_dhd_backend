from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, date, timezone
from typing import Optional, List
import uuid
import os
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.client import Client
from app.schemas.documentation import (
    VitalsLogCreate,
    VitalsLogResponse,
    ShiftNoteCreate,
    ShiftNoteResponse,
    IncidentReportCreate,
    IncidentReportResponse,
    DocumentationEntry,
    MealLogCreate,
    MealLogResponse,
    MealLogUpdate,
    ActivityLogCreate,
    ActivityLogResponse,
    ActivityLogUpdate
)
from app.models.vitals_log import VitalsLog
from app.models.shift_note import ShiftNote
from app.models.incident_report import IncidentReport, IncidentTypeEnum, IncidentSeverityEnum, IncidentStatusEnum
from app.models.meal_log import MealLog
from app.models.activity_log import ActivityLog
from app.models.staff import Staff, StaffAssignment
from app.models.scheduling import Shift, ShiftStatus, TimeClockEntry, TimeEntryType
from app.core.config import settings
import pytz
from datetime import time as time_type
import logging

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()

# Helper function to verify client assignment
def verify_client_assignment(db: Session, staff_user_id: str, client_id: str, organization_id: str) -> bool:
    """
    Verify that a client is assigned to the staff member.
    Returns True if the client is assigned, False otherwise.
    """
    # Get staff record from user_id
    staff = db.query(Staff).filter(
        Staff.user_id == staff_user_id,
        Staff.organization_id == organization_id
    ).first()

    if not staff:
        return False

    # Check if there's an active assignment for this staff and client
    assignment = db.query(StaffAssignment).filter(
        and_(
            StaffAssignment.staff_id == staff.id,
            StaffAssignment.client_id == client_id,
            StaffAssignment.is_active == True
        )
    ).first()

    return assignment is not None


# Helper function to verify documentation is created during active shift
def verify_shift_time(db: Session, staff_user_id: str, client_id: str, organization_id: str, user_timezone: str = "UTC") -> bool:
    """
    Verify that documentation is being created during an active shift for the client.
    Returns True if there's an active shift for this staff-client pair at the current time.
    Uses DSP's timezone to determine current time and compare with shift window.
    """
    logger.info(f"Verifying shift time for staff user {staff_user_id}, client {client_id}, timezone {user_timezone}")

    # Get staff record from user_id
    staff = db.query(Staff).filter(
        Staff.user_id == staff_user_id,
        Staff.organization_id == organization_id
    ).first()

    if not staff:
        logger.warning(f"No staff record found for user {staff_user_id}")
        return False

    # Get user's timezone
    try:
        tz = pytz.timezone(user_timezone)
        logger.info(f"Using timezone: {user_timezone}")
    except Exception as e:
        logger.error(f"Invalid timezone '{user_timezone}', falling back to UTC: {str(e)}")
        tz = pytz.UTC
        user_timezone = "UTC"

    # Get current time in user's timezone
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    now_utc_aware = pytz.UTC.localize(now_utc)
    now_user_tz = now_utc_aware.astimezone(tz)
    current_date = now_user_tz.date()
    current_time = now_user_tz.time()

    logger.info(
        f"Current time - UTC: {now_utc}, "
        f"User TZ ({user_timezone}): {now_user_tz}, "
        f"Date: {current_date}, Time: {current_time}"
    )

    # Query for all shifts for this staff-client pair today
    all_shifts_today = db.query(Shift).filter(
        and_(
            Shift.staff_id == staff.id,
            Shift.client_id == client_id,
            Shift.shift_date == current_date
        )
    ).all()

    logger.info(f"Total shifts today for staff-client pair: {len(all_shifts_today)}")
    for shift in all_shifts_today:
        is_active = shift.start_time <= current_time <= shift.end_time
        logger.info(
            f"Shift {shift.id}: {shift.start_time} - {shift.end_time}, "
            f"Status: {shift.status}, Active: {is_active}"
        )

    # Query for active shift at current time
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

    if active_shift:
        logger.info(f"Active shift found: {active_shift.id}")
        return True
    else:
        logger.warning(f"No active shift found for staff-client pair at current time")
        return False


# Helper function to verify staff is clocked in
def verify_clocked_in(db: Session, staff_user_id: str, organization_id: str) -> bool:
    """
    Verify that a staff member is currently clocked in.
    Returns True if clocked in, raises HTTPException if not clocked in.
    """
    logger.info(f"Verifying clock-in status for staff user {staff_user_id}")

    # Get staff record from user_id
    staff = db.query(Staff).filter(
        Staff.user_id == staff_user_id,
        Staff.organization_id == organization_id
    ).first()

    if not staff:
        logger.warning(f"No staff record found for user {staff_user_id}")
        raise HTTPException(
            status_code=404,
            detail="Staff record not found"
        )

    # Find the most recent clock-in entry for this staff member
    most_recent_clock_in = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff.id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_IN
    ).order_by(TimeClockEntry.entry_datetime.desc()).first()

    if not most_recent_clock_in:
        logger.warning(f"Staff {staff.id} has never clocked in")
        raise HTTPException(
            status_code=403,
            detail="You must clock in before submitting documentation. Please tap 'Time In' in the Shift Clock."
        )

    # Check if there's a clock-out entry after the most recent clock-in
    clock_out_after_clock_in = db.query(TimeClockEntry).filter(
        TimeClockEntry.staff_id == staff.id,
        TimeClockEntry.entry_type == TimeEntryType.CLOCK_OUT,
        TimeClockEntry.entry_datetime > most_recent_clock_in.entry_datetime
    ).first()

    if clock_out_after_clock_in:
        logger.warning(f"Staff {staff.id} is not currently clocked in (clocked out at {clock_out_after_clock_in.entry_datetime})")
        raise HTTPException(
            status_code=403,
            detail="You must clock in before submitting documentation. Please tap 'Time In' in the Shift Clock."
        )

    logger.info(f"Staff {staff.id} is currently clocked in (clock-in time: {most_recent_clock_in.entry_datetime})")
    return True


# Vitals Logging Endpoints
@router.post("/vitals", response_model=VitalsLogResponse)
async def create_vitals_log(
    vitals_data: VitalsLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new vitals log entry for a client.
    Validates that the client is assigned to the DSP and that the DSP is on an active shift.
    """
    logger.info(f"Creating vitals log for client {vitals_data.client_id} by user {current_user.id} ({current_user.email})")

    try:
        # Verify client exists and user has access
        client = db.query(Client).filter(
            and_(
                Client.id == vitals_data.client_id,
                Client.organization_id == current_user.organization_id
            )
        ).first()

        if not client:
            logger.error(f"Client {vitals_data.client_id} not found or not in user's organization")
            raise HTTPException(status_code=404, detail="Client not found")

        logger.info(f"Found client: {client.full_name} (ID: {client.id})")

        # Verify client is assigned to the staff member
        if not verify_client_assignment(db, current_user.id, vitals_data.client_id, current_user.organization_id):
            logger.error(f"User {current_user.id} is not assigned to client {vitals_data.client_id}")
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients assigned to you"
            )

        logger.info("Client assignment verified")

        # Verify documentation is being created during an active shift
        user_tz = current_user.timezone or (current_user.organization.timezone if current_user.organization else "UTC")
        logger.info(f"Checking shift time with timezone: {user_tz}")

        if not verify_shift_time(db, current_user.id, vitals_data.client_id, current_user.organization_id, user_tz):
            logger.error(f"User {current_user.id} is not on an active shift for client {vitals_data.client_id}")
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients during your scheduled shift time"
            )

        logger.info("Shift time verified")

        # Verify staff member is clocked in
        verify_clocked_in(db, current_user.id, current_user.organization_id)
        logger.info("Clock-in status verified - creating vitals log")

        # Create vitals log entry
        vitals_log = VitalsLog(
            id=uuid.uuid4(),
            client_id=vitals_data.client_id,
            staff_id=current_user.id,
            organization_id=current_user.organization_id,
            temperature=vitals_data.temperature,
            blood_pressure_systolic=vitals_data.blood_pressure_systolic,
            blood_pressure_diastolic=vitals_data.blood_pressure_diastolic,
            blood_sugar=vitals_data.blood_sugar,
            weight=vitals_data.weight,
            heart_rate=vitals_data.heart_rate,
            oxygen_saturation=vitals_data.oxygen_saturation,
            notes=vitals_data.notes,
            recorded_at=vitals_data.recorded_at or datetime.now(timezone.utc).replace(tzinfo=None),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )

        db.add(vitals_log)
        db.commit()
        db.refresh(vitals_log)

        return VitalsLogResponse(
            id=str(vitals_log.id),
            client_id=str(vitals_log.client_id),
            client_name=f"{client.first_name} {client.last_name}",
            staff_id=str(vitals_log.staff_id),
            staff_name=f"{current_user.first_name} {current_user.last_name}",
            temperature=vitals_log.temperature,
            blood_pressure_systolic=vitals_log.blood_pressure_systolic,
            blood_pressure_diastolic=vitals_log.blood_pressure_diastolic,
            blood_sugar=vitals_log.blood_sugar,
            weight=vitals_log.weight,
            heart_rate=vitals_log.heart_rate,
            oxygen_saturation=vitals_log.oxygen_saturation,
            notes=vitals_log.notes,
            recorded_at=vitals_log.recorded_at,
            created_at=vitals_log.created_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create vitals log: {str(e)}"
        )

@router.get("/vitals")
async def get_vitals_logs(
    client_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get vitals logs with optional filtering
    Returns paginated response with data array
    """
    try:
        query = db.query(VitalsLog).filter(
            VitalsLog.organization_id == current_user.organization_id
        )

        if client_id:
            query = query.filter(VitalsLog.client_id == client_id)

        if date_from:
            query = query.filter(func.date(VitalsLog.recorded_at) >= date_from)

        if date_to:
            query = query.filter(func.date(VitalsLog.recorded_at) <= date_to)

        # Get total count before pagination
        total = query.count()

        vitals_logs = query.order_by(VitalsLog.recorded_at.desc()).offset(offset).limit(limit).all()

        results = []
        for log in vitals_logs:
            client = db.query(Client).filter(Client.id == log.client_id).first()
            staff = db.query(User).filter(User.id == log.staff_id).first()

            results.append({
                "id": str(log.id),
                "client_id": str(log.client_id),
                "client_name": f"{client.first_name} {client.last_name}" if client else "Unknown",
                "staff_id": str(log.staff_id),
                "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                "temperature": log.temperature,
                "blood_pressure_systolic": log.blood_pressure_systolic,
                "blood_pressure_diastolic": log.blood_pressure_diastolic,
                "blood_sugar": log.blood_sugar,
                "weight": log.weight,
                "heart_rate": log.heart_rate,
                "oxygen_saturation": log.oxygen_saturation,
                "notes": log.notes,
                "recorded_at": log.recorded_at,
                "created_at": log.created_at
            })

        return {
            "data": results,
            "pagination": {
                "total": total,
                "page": (offset // limit) + 1 if limit > 0 else 1,
                "page_size": limit,
                "pages": (total + limit - 1) // limit if limit > 0 else 1
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve vitals logs: {str(e)}"
        )

# Shift Notes Endpoints
@router.post("/shift-notes", response_model=ShiftNoteResponse)
async def create_shift_note(
    shift_note_data: ShiftNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new shift note for a client
    """
    try:
        # Verify client exists and user has access
        client = db.query(Client).filter(
            and_(
                Client.id == shift_note_data.client_id,
                Client.organization_id == current_user.organization_id
            )
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Verify client is assigned to the staff member
        if not verify_client_assignment(db, current_user.id, shift_note_data.client_id, current_user.organization_id):
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients assigned to you"
            )

        # Verify documentation is being created during an active shift
        user_tz = current_user.timezone or (current_user.organization.timezone if current_user.organization else "UTC")
        if not verify_shift_time(db, current_user.id, shift_note_data.client_id, current_user.organization_id, user_tz):
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients during your scheduled shift time"
            )

        # Verify staff member is clocked in
        verify_clocked_in(db, current_user.id, current_user.organization_id)

        # Create shift note
        shift_note = ShiftNote(
            id=uuid.uuid4(),
            client_id=shift_note_data.client_id,
            staff_id=current_user.id,
            organization_id=current_user.organization_id,
            shift_date=shift_note_data.shift_date,
            shift_time=shift_note_data.shift_time,
            narrative=shift_note_data.narrative,
            challenges_faced=shift_note_data.challenges_faced,
            support_required=shift_note_data.support_required,
            observations=shift_note_data.observations,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )

        db.add(shift_note)
        db.commit()
        db.refresh(shift_note)

        return ShiftNoteResponse(
            id=str(shift_note.id),
            client_id=str(shift_note.client_id),
            client_name=f"{client.first_name} {client.last_name}",
            staff_id=str(shift_note.staff_id),
            staff_name=f"{current_user.first_name} {current_user.last_name}",
            shift_date=shift_note.shift_date,
            shift_time=shift_note.shift_time,
            narrative=shift_note.narrative,
            challenges_faced=shift_note.challenges_faced,
            support_required=shift_note.support_required,
            observations=shift_note.observations,
            created_at=shift_note.created_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create shift note: {str(e)}"
        )

@router.get("/shift-notes")
async def get_shift_notes(
    client_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get shift notes with optional filtering
    Returns paginated response with data array
    """
    try:
        query = db.query(ShiftNote).filter(
            ShiftNote.organization_id == current_user.organization_id
        )

        if client_id:
            query = query.filter(ShiftNote.client_id == client_id)

        if date_from:
            query = query.filter(ShiftNote.shift_date >= date_from)

        if date_to:
            query = query.filter(ShiftNote.shift_date <= date_to)

        # Get total count before pagination
        total = query.count()

        shift_notes = query.order_by(ShiftNote.shift_date.desc()).offset(offset).limit(limit).all()

        results = []
        for note in shift_notes:
            client = db.query(Client).filter(Client.id == note.client_id).first()
            staff = db.query(User).filter(User.id == note.staff_id).first()

            results.append({
                "id": str(note.id),
                "client_id": str(note.client_id),
                "client_name": f"{client.first_name} {client.last_name}" if client else "Unknown",
                "staff_id": str(note.staff_id),
                "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                "shift_date": note.shift_date,
                "shift_time": note.shift_time,
                "narrative": note.narrative,
                "challenges_faced": note.challenges_faced,
                "support_required": note.support_required,
                "observations": note.observations,
                "created_at": note.created_at
            })

        return {
            "data": results,
            "pagination": {
                "total": total,
                "page": (offset // limit) + 1 if limit > 0 else 1,
                "page_size": limit,
                "pages": (total + limit - 1) // limit if limit > 0 else 1
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shift notes: {str(e)}"
        )

# Incident Reporting Endpoints
@router.post("/incidents", response_model=IncidentReportResponse)
async def create_incident_report(
    client_id: str = Form(...),
    incident_type: str = Form(...),
    description: str = Form(...),
    action_taken: str = Form(...),
    severity: str = Form(...),
    incident_date: date = Form(...),
    incident_time: str = Form(...),
    location: Optional[str] = Form(None),
    witnesses: Optional[str] = Form(None),
    follow_up_required: bool = Form(False),
    files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new incident report with optional file attachments
    """
    try:
        # Verify client exists and user has access
        client = db.query(Client).filter(
            and_(
                Client.id == client_id,
                Client.organization_id == current_user.organization_id
            )
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Verify client is assigned to the staff member
        if not verify_client_assignment(db, current_user.id, client_id, current_user.organization_id):
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients assigned to you"
            )

        # Verify documentation is being created during an active shift
        user_tz = current_user.timezone or (current_user.organization.timezone if current_user.organization else "UTC")
        if not verify_shift_time(db, current_user.id, client_id, current_user.organization_id, user_tz):
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients during your scheduled shift time"
            )

        # Verify staff member is clocked in
        verify_clocked_in(db, current_user.id, current_user.organization_id)

        # Handle file uploads
        uploaded_files = []
        if files and files[0].filename:  # Check if actual files were uploaded
            upload_dir = f"{settings.UPLOAD_DIR}/incidents/{incident_date.year}/{incident_date.month}"
            os.makedirs(upload_dir, exist_ok=True)

            for file in files:
                if file.filename:
                    file_id = str(uuid.uuid4())
                    file_extension = os.path.splitext(file.filename)[1]
                    file_path = f"{upload_dir}/{file_id}{file_extension}"

                    with open(file_path, "wb") as buffer:
                        content = await file.read()
                        buffer.write(content)

                    uploaded_files.append({
                        "id": file_id,
                        "filename": file.filename,
                        "path": file_path,
                        "size": len(content)
                    })

        # Convert string to enum values
        try:
            incident_type_enum = IncidentTypeEnum[incident_type.upper().replace(' ', '_')]
            severity_enum = IncidentSeverityEnum[severity.upper()]
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")

        # Create incident report
        incident = IncidentReport(
            id=uuid.uuid4(),
            client_id=client_id,
            staff_id=current_user.id,
            organization_id=current_user.organization_id,
            incident_type=incident_type_enum,
            description=description,
            action_taken=action_taken,
            severity=severity_enum,
            incident_date=incident_date,
            incident_time=incident_time,
            location=location,
            witnesses=witnesses,
            follow_up_required=follow_up_required,
            attached_files=uploaded_files,
            status=IncidentStatusEnum.PENDING,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )

        db.add(incident)
        db.commit()
        db.refresh(incident)

        return IncidentReportResponse(
            id=str(incident.id),
            client_id=str(incident.client_id),
            client_name=f"{client.first_name} {client.last_name}",
            staff_id=str(incident.staff_id),
            staff_name=f"{current_user.first_name} {current_user.last_name}",
            incident_type=incident.incident_type,
            description=incident.description,
            action_taken=incident.action_taken,
            severity=incident.severity,
            incident_date=incident.incident_date,
            incident_time=incident.incident_time,
            location=incident.location,
            witnesses=incident.witnesses,
            follow_up_required=incident.follow_up_required,
            attached_files=incident.attached_files,
            status=incident.status,
            created_at=incident.created_at
        )

    except Exception as e:
        db.rollback()
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating incident report: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create incident report: {str(e)}"
        )

@router.get("/incidents")
async def get_incident_reports(
    client_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get incident reports with optional filtering
    Returns paginated response with data array
    """
    try:
        query = db.query(IncidentReport).filter(
            IncidentReport.organization_id == current_user.organization_id
        )

        if client_id:
            query = query.filter(IncidentReport.client_id == client_id)

        if severity:
            query = query.filter(IncidentReport.severity == severity)

        if status:
            query = query.filter(IncidentReport.status == status)

        if date_from:
            query = query.filter(IncidentReport.incident_date >= date_from)

        if date_to:
            query = query.filter(IncidentReport.incident_date <= date_to)

        # Get total count before pagination
        total = query.count()

        incidents = query.order_by(IncidentReport.incident_date.desc()).offset(offset).limit(limit).all()

        results = []
        for incident in incidents:
            client = db.query(Client).filter(Client.id == incident.client_id).first()
            staff = db.query(User).filter(User.id == incident.staff_id).first()

            results.append({
                "id": str(incident.id),
                "client_id": str(incident.client_id),
                "client_name": f"{client.first_name} {client.last_name}" if client else "Unknown",
                "staff_id": str(incident.staff_id),
                "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                "incident_type": incident.incident_type.value if hasattr(incident.incident_type, 'value') else incident.incident_type,
                "description": incident.description,
                "action_taken": incident.action_taken,
                "severity": incident.severity.value if hasattr(incident.severity, 'value') else incident.severity,
                "incident_date": incident.incident_date,
                "incident_time": incident.incident_time,
                "location": incident.location,
                "witnesses": incident.witnesses,
                "follow_up_required": incident.follow_up_required,
                "attached_files": incident.attached_files,
                "status": incident.status.value if hasattr(incident.status, 'value') else incident.status,
                "created_at": incident.created_at
            })

        return {
            "data": results,
            "pagination": {
                "total": total,
                "page": (offset // limit) + 1 if limit > 0 else 1,
                "page_size": limit,
                "pages": (total + limit - 1) // limit if limit > 0 else 1
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve incident reports: {str(e)}"
        )

@router.get("/incidents/{incident_id}/files/{file_id}")
async def download_incident_file(
    incident_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download a file attached to an incident report
    """
    try:
        # Verify incident exists and user has access
        incident = db.query(IncidentReport).filter(
            and_(
                IncidentReport.id == incident_id,
                IncidentReport.organization_id == current_user.organization_id
            )
        ).first()

        if not incident:
            raise HTTPException(status_code=404, detail="Incident report not found")

        # Find the file in attached_files
        file_info = None
        for file in incident.attached_files or []:
            if file.get("id") == file_id:
                file_info = file
                break

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        if not os.path.exists(file_info["path"]):
            raise HTTPException(status_code=404, detail="File no longer exists on server")

        return FileResponse(
            path=file_info["path"],
            filename=file_info["filename"],
            media_type='application/octet-stream'
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )

# Meal Logging Endpoints
@router.post("/meals", response_model=MealLogResponse)
async def create_meal_log(
    meal_data: MealLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new meal log entry for a client
    """
    try:
        # Verify client exists and user has access
        client = db.query(Client).filter(
            and_(
                Client.id == meal_data.client_id,
                Client.organization_id == current_user.organization_id
            )
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Verify client is assigned to the staff member
        if not verify_client_assignment(db, current_user.id, meal_data.client_id, current_user.organization_id):
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients assigned to you"
            )

        # Verify documentation is being created during an active shift
        user_tz = current_user.timezone or (current_user.organization.timezone if current_user.organization else "UTC")
        if not verify_shift_time(db, current_user.id, meal_data.client_id, current_user.organization_id, user_tz):
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients during your scheduled shift time"
            )

        # Verify staff member is clocked in
        verify_clocked_in(db, current_user.id, current_user.organization_id)

        # Create meal log entry
        meal_log = MealLog(
            id=uuid.uuid4(),
            client_id=meal_data.client_id,
            staff_id=current_user.id,
            organization_id=current_user.organization_id,
            meal_type=meal_data.meal_type,
            meal_date=meal_data.meal_date or datetime.now(timezone.utc).replace(tzinfo=None),
            meal_time=meal_data.meal_time,
            food_items=meal_data.food_items,
            intake_amount=meal_data.intake_amount,
            percentage_consumed=meal_data.percentage_consumed,
            calories=meal_data.calories,
            protein_grams=meal_data.protein_grams,
            carbs_grams=meal_data.carbs_grams,
            fat_grams=meal_data.fat_grams,
            water_intake_ml=meal_data.water_intake_ml,
            other_fluids=meal_data.other_fluids,
            appetite_level=meal_data.appetite_level,
            dietary_preferences_followed=meal_data.dietary_preferences_followed,
            dietary_restrictions_followed=meal_data.dietary_restrictions_followed,
            assistance_required=meal_data.assistance_required,
            assistance_type=meal_data.assistance_type,
            refusals=meal_data.refusals,
            allergic_reactions=meal_data.allergic_reactions,
            choking_incidents=meal_data.choking_incidents,
            notes=meal_data.notes,
            recommendations=meal_data.recommendations,
            photo_urls=meal_data.photo_urls
        )

        db.add(meal_log)
        db.commit()
        db.refresh(meal_log)

        return MealLogResponse(
            id=str(meal_log.id),
            client_id=str(meal_log.client_id),
            client_name=f"{client.first_name} {client.last_name}",
            staff_id=str(meal_log.staff_id),
            staff_name=f"{current_user.first_name} {current_user.last_name}",
            meal_type=meal_log.meal_type.value,
            meal_date=meal_log.meal_date,
            meal_time=meal_log.meal_time,
            food_items=meal_log.food_items,
            intake_amount=meal_log.intake_amount.value if meal_log.intake_amount else None,
            percentage_consumed=meal_log.percentage_consumed,
            calories=meal_log.calories,
            protein_grams=meal_log.protein_grams,
            carbs_grams=meal_log.carbs_grams,
            fat_grams=meal_log.fat_grams,
            water_intake_ml=meal_log.water_intake_ml,
            other_fluids=meal_log.other_fluids,
            appetite_level=meal_log.appetite_level,
            dietary_preferences_followed=meal_log.dietary_preferences_followed,
            dietary_restrictions_followed=meal_log.dietary_restrictions_followed,
            assistance_required=meal_log.assistance_required,
            assistance_type=meal_log.assistance_type,
            refusals=meal_log.refusals,
            allergic_reactions=meal_log.allergic_reactions,
            choking_incidents=meal_log.choking_incidents,
            notes=meal_log.notes,
            recommendations=meal_log.recommendations,
            photo_urls=meal_log.photo_urls,
            created_at=meal_log.created_at,
            updated_at=meal_log.updated_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create meal log: {str(e)}"
        )

@router.get("/meals")
async def get_meal_logs(
    client_id: Optional[str] = None,
    meal_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get meal logs with optional filtering
    Returns paginated response with data array
    """
    try:
        query = db.query(MealLog).filter(
            MealLog.organization_id == current_user.organization_id
        )

        if client_id:
            query = query.filter(MealLog.client_id == client_id)

        if meal_type:
            query = query.filter(MealLog.meal_type == meal_type)

        if date_from:
            query = query.filter(func.date(MealLog.meal_date) >= date_from)

        if date_to:
            query = query.filter(func.date(MealLog.meal_date) <= date_to)

        # Get total count before pagination
        total = query.count()

        meal_logs = query.order_by(MealLog.meal_date.desc()).offset(offset).limit(limit).all()

        results = []
        for log in meal_logs:
            client = db.query(Client).filter(Client.id == log.client_id).first()
            staff = db.query(User).filter(User.id == log.staff_id).first()

            results.append({
                "id": str(log.id),
                "client_id": str(log.client_id),
                "client_name": f"{client.first_name} {client.last_name}" if client else "Unknown",
                "staff_id": str(log.staff_id) if log.staff_id else "",
                "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                "meal_type": log.meal_type.value,
                "meal_date": log.meal_date,
                "meal_time": log.meal_time,
                "food_items": log.food_items,
                "intake_amount": log.intake_amount.value if log.intake_amount else None,
                "percentage_consumed": log.percentage_consumed,
                "calories": log.calories,
                "protein_grams": log.protein_grams,
                "carbs_grams": log.carbs_grams,
                "fat_grams": log.fat_grams,
                "water_intake_ml": log.water_intake_ml,
                "other_fluids": log.other_fluids,
                "appetite_level": log.appetite_level,
                "dietary_preferences_followed": log.dietary_preferences_followed,
                "dietary_restrictions_followed": log.dietary_restrictions_followed,
                "assistance_required": log.assistance_required,
                "assistance_type": log.assistance_type,
                "refusals": log.refusals,
                "allergic_reactions": log.allergic_reactions,
                "choking_incidents": log.choking_incidents,
                "notes": log.notes,
                "recommendations": log.recommendations,
                "photo_urls": log.photo_urls,
                "created_at": log.created_at,
                "updated_at": log.updated_at
            })

        return {
            "data": results,
            "pagination": {
                "total": total,
                "page": (offset // limit) + 1 if limit > 0 else 1,
                "page_size": limit,
                "pages": (total + limit - 1) // limit if limit > 0 else 1
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve meal logs: {str(e)}"
        )

@router.get("/meals/{meal_log_id}", response_model=MealLogResponse)
async def get_meal_log(
    meal_log_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific meal log by ID
    """
    try:
        meal_log = db.query(MealLog).filter(
            and_(
                MealLog.id == meal_log_id,
                MealLog.organization_id == current_user.organization_id
            )
        ).first()

        if not meal_log:
            raise HTTPException(status_code=404, detail="Meal log not found")

        client = db.query(Client).filter(Client.id == meal_log.client_id).first()
        staff = db.query(User).filter(User.id == meal_log.staff_id).first() if meal_log.staff_id else None

        return MealLogResponse(
            id=str(meal_log.id),
            client_id=str(meal_log.client_id),
            client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
            staff_id=str(meal_log.staff_id) if meal_log.staff_id else "",
            staff_name=f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
            meal_type=meal_log.meal_type.value,
            meal_date=meal_log.meal_date,
            meal_time=meal_log.meal_time,
            food_items=meal_log.food_items,
            intake_amount=meal_log.intake_amount.value if meal_log.intake_amount else None,
            percentage_consumed=meal_log.percentage_consumed,
            calories=meal_log.calories,
            protein_grams=meal_log.protein_grams,
            carbs_grams=meal_log.carbs_grams,
            fat_grams=meal_log.fat_grams,
            water_intake_ml=meal_log.water_intake_ml,
            other_fluids=meal_log.other_fluids,
            appetite_level=meal_log.appetite_level,
            dietary_preferences_followed=meal_log.dietary_preferences_followed,
            dietary_restrictions_followed=meal_log.dietary_restrictions_followed,
            assistance_required=meal_log.assistance_required,
            assistance_type=meal_log.assistance_type,
            refusals=meal_log.refusals,
            allergic_reactions=meal_log.allergic_reactions,
            choking_incidents=meal_log.choking_incidents,
            notes=meal_log.notes,
            recommendations=meal_log.recommendations,
            photo_urls=meal_log.photo_urls,
            created_at=meal_log.created_at,
            updated_at=meal_log.updated_at
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve meal log: {str(e)}"
        )

@router.put("/meals/{meal_log_id}", response_model=MealLogResponse)
async def update_meal_log(
    meal_log_id: str,
    meal_update: MealLogUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a meal log
    """
    try:
        meal_log = db.query(MealLog).filter(
            and_(
                MealLog.id == meal_log_id,
                MealLog.organization_id == current_user.organization_id
            )
        ).first()

        if not meal_log:
            raise HTTPException(status_code=404, detail="Meal log not found")

        # Update fields if provided
        update_data = meal_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(meal_log, field, value)

        meal_log.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        db.commit()
        db.refresh(meal_log)

        # Return updated meal log
        client = db.query(Client).filter(Client.id == meal_log.client_id).first()
        staff = db.query(User).filter(User.id == meal_log.staff_id).first() if meal_log.staff_id else None

        return MealLogResponse(
            id=str(meal_log.id),
            client_id=str(meal_log.client_id),
            client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
            staff_id=str(meal_log.staff_id) if meal_log.staff_id else "",
            staff_name=f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
            meal_type=meal_log.meal_type.value,
            meal_date=meal_log.meal_date,
            meal_time=meal_log.meal_time,
            food_items=meal_log.food_items,
            intake_amount=meal_log.intake_amount.value if meal_log.intake_amount else None,
            percentage_consumed=meal_log.percentage_consumed,
            calories=meal_log.calories,
            protein_grams=meal_log.protein_grams,
            carbs_grams=meal_log.carbs_grams,
            fat_grams=meal_log.fat_grams,
            water_intake_ml=meal_log.water_intake_ml,
            other_fluids=meal_log.other_fluids,
            appetite_level=meal_log.appetite_level,
            dietary_preferences_followed=meal_log.dietary_preferences_followed,
            dietary_restrictions_followed=meal_log.dietary_restrictions_followed,
            assistance_required=meal_log.assistance_required,
            assistance_type=meal_log.assistance_type,
            refusals=meal_log.refusals,
            allergic_reactions=meal_log.allergic_reactions,
            choking_incidents=meal_log.choking_incidents,
            notes=meal_log.notes,
            recommendations=meal_log.recommendations,
            photo_urls=meal_log.photo_urls,
            created_at=meal_log.created_at,
            updated_at=meal_log.updated_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update meal log: {str(e)}"
        )

@router.delete("/meals/{meal_log_id}")
async def delete_meal_log(
    meal_log_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a meal log
    """
    try:
        meal_log = db.query(MealLog).filter(
            and_(
                MealLog.id == meal_log_id,
                MealLog.organization_id == current_user.organization_id
            )
        ).first()

        if not meal_log:
            raise HTTPException(status_code=404, detail="Meal log not found")

        db.delete(meal_log)
        db.commit()

        return {"message": "Meal log deleted successfully", "id": meal_log_id}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete meal log: {str(e)}"
        )


# Activity Log Endpoints
@router.post("/activities", response_model=ActivityLogResponse)
async def create_activity_log(
    activity_data: ActivityLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new activity log entry for a client
    """
    try:
        # Verify client exists and user has access
        client = db.query(Client).filter(
            and_(
                Client.id == activity_data.client_id,
                Client.organization_id == current_user.organization_id
            )
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Verify client is assigned to the staff member
        if not verify_client_assignment(db, current_user.id, activity_data.client_id, current_user.organization_id):
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients assigned to you"
            )

        # Verify documentation is being created during an active shift
        user_tz = current_user.timezone or (current_user.organization.timezone if current_user.organization else "UTC")
        if not verify_shift_time(db, current_user.id, activity_data.client_id, current_user.organization_id, user_tz):
            raise HTTPException(
                status_code=403,
                detail="You can only create documentation for clients during your scheduled shift time"
            )

        # Verify staff member is clocked in
        verify_clocked_in(db, current_user.id, current_user.organization_id)

        # Create activity log
        activity_log = ActivityLog(
            id=uuid.uuid4(),
            client_id=activity_data.client_id,
            staff_id=current_user.id,
            organization_id=current_user.organization_id,
            activity_type=activity_data.activity_type,
            activity_name=activity_data.activity_name,
            activity_description=activity_data.activity_description,
            activity_date=activity_data.activity_date or datetime.now(timezone.utc).replace(tzinfo=None),
            start_time=activity_data.start_time,
            end_time=activity_data.end_time,
            duration_minutes=activity_data.duration_minutes,
            location=activity_data.location,
            location_type=activity_data.location_type,
            participation_level=activity_data.participation_level,
            independence_level=activity_data.independence_level,
            assistance_required=activity_data.assistance_required,
            assistance_details=activity_data.assistance_details,
            participants=activity_data.participants,
            peer_interaction=activity_data.peer_interaction,
            peer_interaction_quality=activity_data.peer_interaction_quality,
            mood_before=activity_data.mood_before,
            mood_during=activity_data.mood_during,
            mood_after=activity_data.mood_after,
            behavior_observations=activity_data.behavior_observations,
            challenging_behaviors=activity_data.challenging_behaviors,
            skills_practiced=activity_data.skills_practiced,
            skills_progress=activity_data.skills_progress,
            goals_addressed=activity_data.goals_addressed,
            engagement_level=activity_data.engagement_level,
            enjoyment_level=activity_data.enjoyment_level,
            focus_attention=activity_data.focus_attention,
            physical_complaints=activity_data.physical_complaints,
            fatigue_level=activity_data.fatigue_level,
            injuries_incidents=activity_data.injuries_incidents,
            activity_completed=activity_data.activity_completed,
            completion_percentage=activity_data.completion_percentage,
            achievements=activity_data.achievements,
            challenges_faced=activity_data.challenges_faced,
            staff_notes=activity_data.staff_notes,
            recommendations=activity_data.recommendations,
            follow_up_needed=activity_data.follow_up_needed,
            photo_urls=activity_data.photo_urls,
            video_urls=activity_data.video_urls
        )

        db.add(activity_log)
        db.commit()
        db.refresh(activity_log)

        # Get client and staff names
        client_name = f"{client.first_name} {client.last_name}"
        staff_name = f"{current_user.first_name} {current_user.last_name}"

        return ActivityLogResponse(
            id=str(activity_log.id),
            client_id=str(activity_log.client_id),
            client_name=client_name,
            staff_id=str(activity_log.staff_id) if activity_log.staff_id else None,
            staff_name=staff_name,
            organization_id=str(activity_log.organization_id),
            activity_type=activity_log.activity_type,
            activity_name=activity_log.activity_name,
            activity_description=activity_log.activity_description,
            activity_date=activity_log.activity_date,
            start_time=activity_log.start_time,
            end_time=activity_log.end_time,
            duration_minutes=activity_log.duration_minutes,
            location=activity_log.location,
            location_type=activity_log.location_type,
            participation_level=activity_log.participation_level,
            independence_level=activity_log.independence_level,
            assistance_required=activity_log.assistance_required,
            assistance_details=activity_log.assistance_details,
            participants=activity_log.participants,
            peer_interaction=activity_log.peer_interaction,
            peer_interaction_quality=activity_log.peer_interaction_quality,
            mood_before=activity_log.mood_before,
            mood_during=activity_log.mood_during,
            mood_after=activity_log.mood_after,
            behavior_observations=activity_log.behavior_observations,
            challenging_behaviors=activity_log.challenging_behaviors,
            skills_practiced=activity_log.skills_practiced,
            skills_progress=activity_log.skills_progress,
            goals_addressed=activity_log.goals_addressed,
            engagement_level=activity_log.engagement_level,
            enjoyment_level=activity_log.enjoyment_level,
            focus_attention=activity_log.focus_attention,
            physical_complaints=activity_log.physical_complaints,
            fatigue_level=activity_log.fatigue_level,
            injuries_incidents=activity_log.injuries_incidents,
            activity_completed=activity_log.activity_completed,
            completion_percentage=activity_log.completion_percentage,
            achievements=activity_log.achievements,
            challenges_faced=activity_log.challenges_faced,
            staff_notes=activity_log.staff_notes,
            recommendations=activity_log.recommendations,
            follow_up_needed=activity_log.follow_up_needed,
            photo_urls=activity_log.photo_urls,
            video_urls=activity_log.video_urls,
            created_at=activity_log.created_at,
            updated_at=activity_log.updated_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create activity log: {str(e)}"
        )


@router.get("/activities")
async def get_activity_logs(
    client_id: Optional[str] = None,
    activity_date: Optional[date] = None,
    activity_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get activity logs with optional filtering by client, date, or type
    Returns paginated response with data array
    """
    try:
        query = db.query(ActivityLog).filter(
            ActivityLog.organization_id == current_user.organization_id
        )

        if client_id:
            query = query.filter(ActivityLog.client_id == client_id)

        if activity_date:
            query = query.filter(func.date(ActivityLog.activity_date) == activity_date)

        if activity_type:
            query = query.filter(ActivityLog.activity_type == activity_type)

        # Get total count before pagination
        total = query.count()

        activity_logs = query.order_by(ActivityLog.activity_date.desc()).offset(offset).limit(limit).all()

        # Build response with client and staff names
        response_list = []
        for log in activity_logs:
            # Get client name
            client = db.query(Client).filter(Client.id == log.client_id).first()
            client_name = f"{client.first_name} {client.last_name}" if client else "Unknown Client"

            # Get staff name
            staff_name = "Unknown Staff"
            if log.staff_id:
                staff = db.query(User).filter(User.id == log.staff_id).first()
                staff_name = f"{staff.first_name} {staff.last_name}" if staff else "Unknown Staff"

            response_list.append({
                "id": str(log.id),
                "client_id": str(log.client_id),
                "client_name": client_name,
                "staff_id": str(log.staff_id) if log.staff_id else None,
                "staff_name": staff_name,
                "organization_id": str(log.organization_id),
                "activity_type": log.activity_type,
                "activity_name": log.activity_name,
                "activity_description": log.activity_description,
                "activity_date": log.activity_date,
                "start_time": log.start_time,
                "end_time": log.end_time,
                "duration_minutes": log.duration_minutes,
                "location": log.location,
                "location_type": log.location_type,
                "participation_level": log.participation_level,
                "independence_level": log.independence_level,
                "assistance_required": log.assistance_required,
                "assistance_details": log.assistance_details,
                "participants": log.participants,
                "peer_interaction": log.peer_interaction,
                "peer_interaction_quality": log.peer_interaction_quality,
                "mood_before": log.mood_before,
                "mood_during": log.mood_during,
                "mood_after": log.mood_after,
                "behavior_observations": log.behavior_observations,
                "challenging_behaviors": log.challenging_behaviors,
                "skills_practiced": log.skills_practiced,
                "skills_progress": log.skills_progress,
                "goals_addressed": log.goals_addressed,
                "engagement_level": log.engagement_level,
                "enjoyment_level": log.enjoyment_level,
                "focus_attention": log.focus_attention,
                "physical_complaints": log.physical_complaints,
                "fatigue_level": log.fatigue_level,
                "injuries_incidents": log.injuries_incidents,
                "activity_completed": log.activity_completed,
                "completion_percentage": log.completion_percentage,
                "achievements": log.achievements,
                "challenges_faced": log.challenges_faced,
                "staff_notes": log.staff_notes,
                "recommendations": log.recommendations,
                "follow_up_needed": log.follow_up_needed,
                "photo_urls": log.photo_urls,
                "video_urls": log.video_urls,
                "created_at": log.created_at,
                "updated_at": log.updated_at
            })

        return {
            "data": response_list,
            "pagination": {
                "total": total,
                "page": (offset // limit) + 1 if limit > 0 else 1,
                "page_size": limit,
                "pages": (total + limit - 1) // limit if limit > 0 else 1
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch activity logs: {str(e)}"
        )


@router.get("/activities/{activity_log_id}", response_model=ActivityLogResponse)
async def get_activity_log(
    activity_log_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific activity log by ID
    """
    try:
        activity_log = db.query(ActivityLog).filter(
            and_(
                ActivityLog.id == activity_log_id,
                ActivityLog.organization_id == current_user.organization_id
            )
        ).first()

        if not activity_log:
            raise HTTPException(status_code=404, detail="Activity log not found")

        # Get client and staff names
        client = db.query(Client).filter(Client.id == activity_log.client_id).first()
        client_name = f"{client.first_name} {client.last_name}" if client else "Unknown Client"

        staff_name = "Unknown Staff"
        if activity_log.staff_id:
            staff = db.query(User).filter(User.id == activity_log.staff_id).first()
            staff_name = f"{staff.first_name} {staff.last_name}" if staff else "Unknown Staff"

        return ActivityLogResponse(
            id=str(activity_log.id),
            client_id=str(activity_log.client_id),
            client_name=client_name,
            staff_id=str(activity_log.staff_id) if activity_log.staff_id else None,
            staff_name=staff_name,
            organization_id=str(activity_log.organization_id),
            activity_type=activity_log.activity_type,
            activity_name=activity_log.activity_name,
            activity_description=activity_log.activity_description,
            activity_date=activity_log.activity_date,
            start_time=activity_log.start_time,
            end_time=activity_log.end_time,
            duration_minutes=activity_log.duration_minutes,
            location=activity_log.location,
            location_type=activity_log.location_type,
            participation_level=activity_log.participation_level,
            independence_level=activity_log.independence_level,
            assistance_required=activity_log.assistance_required,
            assistance_details=activity_log.assistance_details,
            participants=activity_log.participants,
            peer_interaction=activity_log.peer_interaction,
            peer_interaction_quality=activity_log.peer_interaction_quality,
            mood_before=activity_log.mood_before,
            mood_during=activity_log.mood_during,
            mood_after=activity_log.mood_after,
            behavior_observations=activity_log.behavior_observations,
            challenging_behaviors=activity_log.challenging_behaviors,
            skills_practiced=activity_log.skills_practiced,
            skills_progress=activity_log.skills_progress,
            goals_addressed=activity_log.goals_addressed,
            engagement_level=activity_log.engagement_level,
            enjoyment_level=activity_log.enjoyment_level,
            focus_attention=activity_log.focus_attention,
            physical_complaints=activity_log.physical_complaints,
            fatigue_level=activity_log.fatigue_level,
            injuries_incidents=activity_log.injuries_incidents,
            activity_completed=activity_log.activity_completed,
            completion_percentage=activity_log.completion_percentage,
            achievements=activity_log.achievements,
            challenges_faced=activity_log.challenges_faced,
            staff_notes=activity_log.staff_notes,
            recommendations=activity_log.recommendations,
            follow_up_needed=activity_log.follow_up_needed,
            photo_urls=activity_log.photo_urls,
            video_urls=activity_log.video_urls,
            created_at=activity_log.created_at,
            updated_at=activity_log.updated_at
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch activity log: {str(e)}"
        )