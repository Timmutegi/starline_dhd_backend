from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, date
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
from app.models.incident_report import IncidentReport
from app.models.meal_log import MealLog
from app.models.activity_log import ActivityLog
from app.core.config import settings

router = APIRouter()

# Vitals Logging Endpoints
@router.post("/vitals", response_model=VitalsLogResponse)
async def create_vitals_log(
    vitals_data: VitalsLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new vitals log entry for a client
    """
    try:
        # Verify client exists and user has access
        client = db.query(Client).filter(
            and_(
                Client.id == vitals_data.client_id,
                Client.organization_id == current_user.organization_id
            )
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

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
            recorded_at=vitals_data.recorded_at or datetime.utcnow(),
            created_at=datetime.utcnow()
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

@router.get("/vitals", response_model=List[VitalsLogResponse])
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

        vitals_logs = query.order_by(VitalsLog.recorded_at.desc()).offset(offset).limit(limit).all()

        results = []
        for log in vitals_logs:
            client = db.query(Client).filter(Client.id == log.client_id).first()
            staff = db.query(User).filter(User.id == log.staff_id).first()

            results.append(VitalsLogResponse(
                id=str(log.id),
                client_id=str(log.client_id),
                client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
                staff_id=str(log.staff_id),
                staff_name=f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                temperature=log.temperature,
                blood_pressure_systolic=log.blood_pressure_systolic,
                blood_pressure_diastolic=log.blood_pressure_diastolic,
                blood_sugar=log.blood_sugar,
                weight=log.weight,
                heart_rate=log.heart_rate,
                oxygen_saturation=log.oxygen_saturation,
                notes=log.notes,
                recorded_at=log.recorded_at,
                created_at=log.created_at
            ))

        return results

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
            created_at=datetime.utcnow()
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

@router.get("/shift-notes", response_model=List[ShiftNoteResponse])
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

        shift_notes = query.order_by(ShiftNote.shift_date.desc()).offset(offset).limit(limit).all()

        results = []
        for note in shift_notes:
            client = db.query(Client).filter(Client.id == note.client_id).first()
            staff = db.query(User).filter(User.id == note.staff_id).first()

            results.append(ShiftNoteResponse(
                id=str(note.id),
                client_id=str(note.client_id),
                client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
                staff_id=str(note.staff_id),
                staff_name=f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                shift_date=note.shift_date,
                shift_time=note.shift_time,
                narrative=note.narrative,
                challenges_faced=note.challenges_faced,
                support_required=note.support_required,
                observations=note.observations,
                created_at=note.created_at
            ))

        return results

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

        # Create incident report
        incident = IncidentReport(
            id=uuid.uuid4(),
            client_id=client_id,
            staff_id=current_user.id,
            organization_id=current_user.organization_id,
            incident_type=incident_type,
            description=description,
            action_taken=action_taken,
            severity=severity,
            incident_date=incident_date,
            incident_time=incident_time,
            location=location,
            witnesses=witnesses,
            follow_up_required=follow_up_required,
            attached_files=uploaded_files,
            status="pending",
            created_at=datetime.utcnow()
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create incident report: {str(e)}"
        )

@router.get("/incidents", response_model=List[IncidentReportResponse])
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

        incidents = query.order_by(IncidentReport.incident_date.desc()).offset(offset).limit(limit).all()

        results = []
        for incident in incidents:
            client = db.query(Client).filter(Client.id == incident.client_id).first()
            staff = db.query(User).filter(User.id == incident.staff_id).first()

            results.append(IncidentReportResponse(
                id=str(incident.id),
                client_id=str(incident.client_id),
                client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
                staff_id=str(incident.staff_id),
                staff_name=f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
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
            ))

        return results

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

        # Create meal log entry
        meal_log = MealLog(
            id=uuid.uuid4(),
            client_id=meal_data.client_id,
            staff_id=current_user.id,
            organization_id=current_user.organization_id,
            meal_type=meal_data.meal_type,
            meal_date=meal_data.meal_date or datetime.utcnow(),
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

@router.get("/meals", response_model=List[MealLogResponse])
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

        meal_logs = query.order_by(MealLog.meal_date.desc()).offset(offset).limit(limit).all()

        results = []
        for log in meal_logs:
            client = db.query(Client).filter(Client.id == log.client_id).first()
            staff = db.query(User).filter(User.id == log.staff_id).first()

            results.append(MealLogResponse(
                id=str(log.id),
                client_id=str(log.client_id),
                client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
                staff_id=str(log.staff_id) if log.staff_id else "",
                staff_name=f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                meal_type=log.meal_type.value,
                meal_date=log.meal_date,
                meal_time=log.meal_time,
                food_items=log.food_items,
                intake_amount=log.intake_amount.value if log.intake_amount else None,
                percentage_consumed=log.percentage_consumed,
                calories=log.calories,
                protein_grams=log.protein_grams,
                carbs_grams=log.carbs_grams,
                fat_grams=log.fat_grams,
                water_intake_ml=log.water_intake_ml,
                other_fluids=log.other_fluids,
                appetite_level=log.appetite_level,
                dietary_preferences_followed=log.dietary_preferences_followed,
                dietary_restrictions_followed=log.dietary_restrictions_followed,
                assistance_required=log.assistance_required,
                assistance_type=log.assistance_type,
                refusals=log.refusals,
                allergic_reactions=log.allergic_reactions,
                choking_incidents=log.choking_incidents,
                notes=log.notes,
                recommendations=log.recommendations,
                photo_urls=log.photo_urls,
                created_at=log.created_at,
                updated_at=log.updated_at
            ))

        return results

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

        meal_log.updated_at = datetime.utcnow()

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