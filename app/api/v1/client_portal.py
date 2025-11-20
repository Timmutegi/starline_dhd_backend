"""
Client Portal API endpoints
Provides read-only access for clients to view their own data
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from uuid import UUID

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.client import Client
from app.models.vitals_log import VitalsLog
from app.models.meal_log import MealLog
from app.models.activity_log import ActivityLog
from app.models.shift_note import ShiftNote
from app.models.scheduling import Shift
from pydantic import BaseModel, Field

router = APIRouter()


# Pydantic schemas for responses
class ClientDashboardData(BaseModel):
    client_info: dict
    today_schedule: dict
    recent_vitals: dict
    meal_summary: dict
    upcoming_appointments: List[dict]
    recent_shift_notes: List[dict]
    last_updated: datetime

    class Config:
        from_attributes = True


class ClientProfileResponse(BaseModel):
    id: UUID
    client_id: str
    full_name: str
    preferred_name: Optional[str]
    date_of_birth: date
    age: int
    gender: str
    email: str
    photo_url: Optional[str]
    location_name: Optional[str]
    location_address: Optional[str]
    admission_date: date
    primary_diagnosis: Optional[str]
    secondary_diagnoses: List[str]
    allergies: List[str]
    dietary_restrictions: List[str]
    emergency_contacts: List[dict]

    class Config:
        from_attributes = True


class HelpRequestCreate(BaseModel):
    request_type: str = Field(..., description="Type of help request")
    priority: str = Field(default="normal", description="Priority level")
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    preferred_time: Optional[datetime] = None


class HelpRequestResponse(BaseModel):
    id: UUID
    request_type: str
    priority: str
    title: str
    description: str
    preferred_time: Optional[datetime]
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
    response: Optional[str]

    class Config:
        from_attributes = True


def get_client_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Verify user is a client and get their client record"""
    if not current_user.role or current_user.role.name.lower() != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to clients"
        )

    client = db.query(Client).filter(Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile not found"
        )

    return client


@router.get("/dashboard", response_model=ClientDashboardData)
async def get_client_dashboard(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db)
):
    """Get client dashboard overview data"""
    today = date.today()

    # Client info
    client_info = {
        "full_name": client.full_name,
        "client_id": client.client_id,
        "location_name": None,
        "admission_date": client.admission_date.isoformat() if client.admission_date else None,
    }

    # Today's schedule
    shifts_today = db.query(Shift).filter(
        Shift.client_id == client.id,
        Shift.shift_date == today
    ).count()

    activities_today = db.query(ActivityLog).filter(
        ActivityLog.client_id == client.id,
        func.date(ActivityLog.activity_date) == today
    ).all()

    completed_activities = sum(1 for a in activities_today if a.activity_completed == True)
    pending_activities = sum(1 for a in activities_today if a.activity_completed == False)

    today_schedule = {
        "scheduled_shifts": shifts_today,
        "completed_activities": completed_activities,
        "pending_activities": pending_activities,
    }

    # Recent vitals
    latest_vital = db.query(VitalsLog).filter(
        VitalsLog.client_id == client.id
    ).order_by(desc(VitalsLog.recorded_at)).first()

    logged_today = False
    if latest_vital and latest_vital.recorded_at:
        logged_today = latest_vital.recorded_at.date() == today

    recent_vitals = {
        "logged_today": logged_today,
        "last_logged": latest_vital.recorded_at.isoformat() if latest_vital else None,
        "temperature": latest_vital.temperature if latest_vital else None,
        "blood_pressure": f"{latest_vital.blood_pressure_systolic}/{latest_vital.blood_pressure_diastolic}" if latest_vital and latest_vital.blood_pressure_systolic else None,
    }

    # Meal summary
    meals_today = db.query(MealLog).filter(
        MealLog.client_id == client.id,
        func.date(MealLog.meal_date) == today
    ).all()

    meal_summary = {
        "meals_today": len(meals_today),
        "missed_meals": sum(1 for m in meals_today if m.refusals or (m.intake_amount and m.intake_amount.value == "none")),
    }

    # Upcoming appointments (next 7 days)
    upcoming_shifts = db.query(Shift).filter(
        Shift.client_id == client.id,
        Shift.shift_date >= today,
        Shift.shift_date <= today + timedelta(days=7)
    ).order_by(Shift.shift_date, Shift.start_time).limit(5).all()

    upcoming_appointments = [
        {
            "id": str(shift.id),
            "title": f"{(shift.shift_type.value if hasattr(shift.shift_type, 'value') else shift.shift_type).replace('_', ' ').title()} Shift",
            "scheduled_time": datetime.combine(shift.shift_date, shift.start_time).isoformat(),
            "type": shift.shift_type.value if hasattr(shift.shift_type, 'value') else shift.shift_type,
        }
        for shift in upcoming_shifts
    ]

    # Recent shift notes
    recent_notes = db.query(ShiftNote).options(
        joinedload(ShiftNote.staff)
    ).filter(
        ShiftNote.client_id == client.id
    ).order_by(desc(ShiftNote.created_at)).limit(5).all()

    recent_shift_notes = [
        {
            "id": str(note.id),
            "note_preview": note.narrative[:100] + "..." if note.narrative and len(note.narrative) > 100 else (note.narrative or ""),
            "logged_by": f"{note.staff.first_name} {note.staff.last_name}" if note.staff else "Unknown",
            "logged_at": note.created_at.isoformat(),
        }
        for note in recent_notes
    ]

    return ClientDashboardData(
        client_info=client_info,
        today_schedule=today_schedule,
        recent_vitals=recent_vitals,
        meal_summary=meal_summary,
        upcoming_appointments=upcoming_appointments,
        recent_shift_notes=recent_shift_notes,
        last_updated=datetime.now(timezone.utc).replace(tzinfo=None),
    )


@router.get("/profile", response_model=ClientProfileResponse)
async def get_client_profile(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db)
):
    """Get client profile information"""
    from datetime import date

    age = None
    if client.date_of_birth:
        today = date.today()
        age = today.year - client.date_of_birth.year - ((today.month, today.day) < (client.date_of_birth.month, client.date_of_birth.day))

    return ClientProfileResponse(
        id=client.id,
        client_id=client.client_id,
        full_name=client.full_name,
        preferred_name=client.preferred_name,
        date_of_birth=client.date_of_birth,
        age=age or 0,
        gender=client.gender,
        email=client.user.email if client.user else "",
        photo_url=client.photo_url,
        location_name=None,
        location_address=None,
        admission_date=client.admission_date,
        primary_diagnosis=client.primary_diagnosis,
        secondary_diagnoses=client.secondary_diagnoses or [],
        allergies=client.allergies or [],
        dietary_restrictions=client.dietary_restrictions or [],
        emergency_contacts=[],
    )


@router.get("/vitals/summary")
async def get_vitals_summary(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db)
):
    """Get vitals summary with trends"""
    # Get latest reading
    latest = db.query(VitalsLog).filter(
        VitalsLog.client_id == client.id
    ).order_by(desc(VitalsLog.recorded_at)).first()

    # Get previous reading for trend comparison
    previous = db.query(VitalsLog).filter(
        VitalsLog.client_id == client.id,
        VitalsLog.id != latest.id if latest else None
    ).order_by(desc(VitalsLog.recorded_at)).first() if latest else None

    # Calculate trends
    trends = {
        "temperature": "stable",
        "blood_pressure": "stable",
        "heart_rate": "stable",
        "weight": "stable",
    }

    if latest and previous:
        if latest.temperature and previous.temperature:
            trends["temperature"] = "up" if latest.temperature > previous.temperature else ("down" if latest.temperature < previous.temperature else "stable")
        if latest.heart_rate and previous.heart_rate:
            trends["heart_rate"] = "up" if latest.heart_rate > previous.heart_rate else ("down" if latest.heart_rate < previous.heart_rate else "stable")
        if latest.weight and previous.weight:
            trends["weight"] = "up" if latest.weight > previous.weight else ("down" if latest.weight < previous.weight else "stable")

    # Count logs this month
    first_of_month = date.today().replace(day=1)
    total_logs_this_month = db.query(VitalsLog).filter(
        VitalsLog.client_id == client.id,
        func.date(VitalsLog.recorded_at) >= first_of_month
    ).count()

    latest_reading = None
    if latest:
        latest_reading = {
            "temperature": latest.temperature,
            "blood_pressure": f"{latest.blood_pressure_systolic}/{latest.blood_pressure_diastolic}" if latest.blood_pressure_systolic else None,
            "heart_rate": latest.heart_rate,
            "weight": latest.weight,
        }

    return {
        "latest_reading": latest_reading,
        "trends": trends,
        "total_logs_this_month": total_logs_this_month,
    }


@router.get("/vitals")
async def get_client_vitals(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db),
    limit: int = 100
):
    """Get client vitals history"""
    vitals = db.query(VitalsLog).options(
        joinedload(VitalsLog.staff)
    ).filter(
        VitalsLog.client_id == client.id
    ).order_by(desc(VitalsLog.recorded_at)).limit(limit).all()

    return [
        {
            "id": str(v.id),
            "recorded_at": v.recorded_at.isoformat(),
            "temperature": v.temperature,
            "blood_pressure_systolic": v.blood_pressure_systolic,
            "blood_pressure_diastolic": v.blood_pressure_diastolic,
            "heart_rate": v.heart_rate,
            "oxygen_saturation": v.oxygen_saturation,
            "blood_sugar": v.blood_sugar,
            "weight": v.weight,
            "notes": v.notes,
            "logged_by_name": f"{v.staff.first_name} {v.staff.last_name}" if v.staff else "Unknown",
            "status": "normal",
        }
        for v in vitals
    ]


@router.get("/meals/summary")
async def get_meals_summary(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db)
):
    """Get meals summary"""
    week_ago = date.today() - timedelta(days=7)

    meals_this_week = db.query(MealLog).filter(
        MealLog.client_id == client.id,
        func.date(MealLog.meal_date) >= week_ago
    ).all()

    completed = sum(1 for m in meals_this_week if not m.refusals and m.intake_amount and m.intake_amount.value != "none")
    missed = sum(1 for m in meals_this_week if m.refusals or (m.intake_amount and m.intake_amount.value == "none"))

    # Calculate average intake
    intakes = [m.percentage_consumed for m in meals_this_week if m.percentage_consumed is not None]
    avg_intake = sum(intakes) / len(intakes) if intakes else 0

    return {
        "total_meals_this_week": len(meals_this_week),
        "meals_completed": completed,
        "meals_missed": missed,
        "average_intake_percentage": round(avg_intake, 1),
    }


@router.get("/meals")
async def get_client_meals(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db),
    limit: int = 100
):
    """Get client meal logs"""
    meals = db.query(MealLog).options(
        joinedload(MealLog.staff)
    ).filter(
        MealLog.client_id == client.id
    ).order_by(desc(MealLog.meal_date)).limit(limit).all()

    return [
        {
            "id": str(m.id),
            "meal_type": m.meal_type.value if m.meal_type else "snack",
            "meal_time": m.meal_time or "",
            "meal_date": m.meal_date.isoformat() if m.meal_date else None,
            "items_consumed": m.food_items or [],
            "intake_amount": m.intake_amount.value if m.intake_amount else "none",
            "intake_percentage": m.percentage_consumed,
            "dietary_notes": m.notes,
            "logged_by_name": f"{m.staff.first_name} {m.staff.last_name}" if m.staff else "Unknown",
            "logged_at": m.created_at.isoformat() if m.created_at else None,
            "status": "completed" if (not m.refusals and m.intake_amount and m.intake_amount.value != "none") else "missed",
        }
        for m in meals
    ]


@router.get("/activities/summary")
async def get_activities_summary(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db)
):
    """Get activities summary"""
    week_ago = date.today() - timedelta(days=7)

    activities_this_week = db.query(ActivityLog).filter(
        ActivityLog.client_id == client.id,
        func.date(ActivityLog.activity_date) >= week_ago
    ).all()

    completed = sum(1 for a in activities_this_week if a.activity_completed == True)
    pending = sum(1 for a in activities_this_week if a.activity_completed == False)

    # Calculate participation rate
    participation_levels = [a.participation_level for a in activities_this_week if a.participation_level and a.activity_completed == True]
    participation_map = {"full": 100, "partial": 66, "minimal": 33, "refused": 0, "unable": 0}
    participation_scores = [participation_map.get(p.value if hasattr(p, 'value') else str(p), 0) for p in participation_levels]
    avg_participation = sum(participation_scores) / len(participation_scores) if participation_scores else 0

    return {
        "total_activities_this_week": len(activities_this_week),
        "activities_completed": completed,
        "activities_pending": pending,
        "participation_rate": round(avg_participation, 1),
    }


@router.get("/activities")
async def get_client_activities(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db),
    limit: int = 100
):
    """Get client activity logs"""
    activities = db.query(ActivityLog).options(
        joinedload(ActivityLog.staff)
    ).filter(
        ActivityLog.client_id == client.id
    ).order_by(desc(ActivityLog.activity_date)).limit(limit).all()

    return [
        {
            "id": str(a.id),
            "activity_type": a.activity_type.value if a.activity_type else "other",
            "activity_name": a.activity_name,
            "activity_date": a.activity_date.isoformat() if a.activity_date else None,
            "start_time": a.start_time,
            "end_time": a.end_time,
            "duration_minutes": a.duration_minutes,
            "location": a.location,
            "description": a.activity_description,
            "participation_level": a.participation_level.value if a.participation_level else None,
            "behavior_notes": a.behavior_observations,
            "logged_by_name": f"{a.staff.first_name} {a.staff.last_name}" if a.staff else "Unknown",
            "status": "completed" if a.activity_completed else "pending",
        }
        for a in activities
    ]


@router.get("/shift-notes/summary")
async def get_shift_notes_summary(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db)
):
    """Get shift notes summary"""
    month_ago = date.today() - timedelta(days=30)

    notes_this_month = db.query(ShiftNote).filter(
        ShiftNote.client_id == client.id,
        func.date(ShiftNote.shift_date) >= month_ago
    ).all()

    # Count positive notes (no challenges mentioned)
    positive = sum(1 for n in notes_this_month if not n.challenges_faced or len(n.challenges_faced.strip()) == 0)

    # Count concerns (challenges mentioned)
    concerns = sum(1 for n in notes_this_month if n.challenges_faced and len(n.challenges_faced.strip()) > 0)

    return {
        "total_notes_this_month": len(notes_this_month),
        "positive_notes": positive,
        "concerns_noted": concerns,
    }


@router.get("/shift-notes")
async def get_client_shift_notes(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db),
    limit: int = 100
):
    """Get client shift notes"""
    notes = db.query(ShiftNote).options(
        joinedload(ShiftNote.staff)
    ).filter(
        ShiftNote.client_id == client.id
    ).order_by(desc(ShiftNote.shift_date), desc(ShiftNote.created_at)).limit(limit).all()

    return [
        {
            "id": str(n.id),
            "shift_date": n.shift_date.isoformat(),
            "shift_time": n.shift_time,
            "note_type": "routine",
            "note_content": n.narrative,
            "mood_rating": None,
            "behavior_notes": n.observations,
            "medical_notes": None,
            "activities_completed": [],
            "challenges_faced": n.challenges_faced,
            "support_required": n.support_required,
            "concerns": n.challenges_faced,
            "logged_by_name": f"{n.staff.first_name} {n.staff.last_name}" if n.staff else "Unknown",
            "logged_at": n.created_at.isoformat(),
        }
        for n in notes
    ]


@router.post("/help-requests", response_model=HelpRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_help_request(
    request_data: HelpRequestCreate,
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db)
):
    """Create a new help request"""
    from app.models.task import Task, TaskPriorityEnum, TaskStatusEnum

    # Convert string priority to enum
    priority_mapping = {
        "low": TaskPriorityEnum.LOW,
        "normal": TaskPriorityEnum.MEDIUM,
        "medium": TaskPriorityEnum.MEDIUM,
        "high": TaskPriorityEnum.HIGH,
        "urgent": TaskPriorityEnum.URGENT,
    }
    task_priority = priority_mapping.get(request_data.priority.lower(), TaskPriorityEnum.MEDIUM)

    # Create a task for the help request
    task = Task(
        organization_id=client.organization_id,
        client_id=client.id,
        title=request_data.title,
        description=request_data.description,
        task_type="help_request",
        priority=task_priority,
        status=TaskStatusEnum.PENDING,
        due_date=request_data.preferred_time.date() if request_data.preferred_time else None,
        created_by=client.user_id,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return HelpRequestResponse(
        id=task.id,
        request_type=request_data.request_type,
        priority=task.priority.value if task.priority else "medium",
        title=task.title,
        description=task.description,
        preferred_time=request_data.preferred_time,
        status=task.status.value if task.status else "pending",
        created_at=task.created_at,
        resolved_at=task.completed_at,
        response=None,
    )


@router.get("/help-requests", response_model=List[HelpRequestResponse])
async def get_help_requests(
    client: Client = Depends(get_client_user),
    db: Session = Depends(get_db),
    limit: int = 50
):
    """Get client's help requests"""
    from app.models.task import Task

    tasks = db.query(Task).filter(
        Task.client_id == client.id,
        Task.task_type == "help_request"
    ).order_by(desc(Task.created_at)).limit(limit).all()

    return [
        HelpRequestResponse(
            id=t.id,
            request_type="other",
            priority=t.priority.value if t.priority else "medium",
            title=t.title,
            description=t.description,
            preferred_time=None,
            status=t.status.value if t.status else "pending",
            created_at=t.created_at,
            resolved_at=t.completed_at,
            response=t.notes,
        )
        for t in tasks
    ]
