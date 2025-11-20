from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from datetime import datetime, timezone, date, timedelta
from typing import Optional, List
import pytz
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.client import Client, ClientAssignment as ClientAssignmentModel
from app.models.staff import Staff, StaffAssignment
from app.models.scheduling import Appointment, AppointmentStatus
from app.models.task import Task, TaskStatusEnum
from app.models.incident_report import IncidentReport
from app.schemas.dashboard import (
    DashboardOverview,
    QuickStats,
    RecentActivity,
    ActivityItem,
    ClientAssignment,
    TaskSummary
)

router = APIRouter()

def make_aware(dt):
    """Convert timezone-naive datetime to timezone-aware UTC datetime"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        return pytz.UTC.localize(dt)
    return dt

@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    date_filter: Optional[date] = Query(None, description="Filter by specific date, defaults to today")
):
    """
    Get dashboard overview with key metrics for the current user
    """
    try:
        target_date = date_filter or date.today()

        # Get staff record for current user
        staff = db.query(Staff).filter(Staff.user_id == current_user.id).first()

        # Get clients assigned today for current user via StaffAssignment
        clients_assigned = 0
        if staff:
            clients_assigned = db.query(StaffAssignment).filter(
                and_(
                    StaffAssignment.staff_id == staff.id,
                    StaffAssignment.is_active == True
                )
            ).count()

        # Get appointments today
        appointments_today = db.query(Appointment).filter(
            and_(
                Appointment.staff_id == staff.id if staff else None,
                func.date(Appointment.start_datetime) == target_date,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.IN_PROGRESS])
            )
        ).count() if staff else 0

        # Get completed tasks for today
        tasks_completed = db.query(Task).filter(
            and_(
                Task.assigned_to == current_user.id,
                Task.status == TaskStatusEnum.COMPLETED,
                func.date(Task.completed_at) == target_date
            )
        ).count()

        # Get incidents reported today
        incidents_reported = db.query(IncidentReport).filter(
            and_(
                IncidentReport.staff_id == current_user.id,
                func.date(IncidentReport.created_at) == target_date
            )
        ).count()

        quick_stats = QuickStats(
            clients_assigned_today=clients_assigned,
            tasks_completed=tasks_completed,
            incidents_reported=incidents_reported,
            appointments_today=appointments_today
        )

        # Get recent activity (simplified)
        recent_activities = []

        # Get recent appointments
        recent_appointments = db.query(Appointment).filter(
            Appointment.staff_id == current_user.id
        ).order_by(Appointment.created_at.desc()).limit(5).all()

        for apt in recent_appointments:
            recent_activities.append(ActivityItem(
                id=str(apt.id),
                type="appointment",
                title=f"Appointment with {apt.client.first_name} {apt.client.last_name}" if apt.client else "Appointment",
                description=apt.notes or "No notes",
                timestamp=apt.created_at,
                status=apt.status
            ))

        recent_activity = RecentActivity(items=recent_activities[:10])

        return DashboardOverview(
            user_name=f"{current_user.first_name} {current_user.last_name}",
            organization_name=current_user.organization.name if current_user.organization else "Starline",
            quick_stats=quick_stats,
            recent_activity=recent_activity,
            current_date=target_date
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve dashboard overview: {str(e)}"
        )

@router.get("/clients-assigned", response_model=List[ClientAssignment])
async def get_clients_assigned_today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    date_filter: Optional[date] = Query(None, description="Filter by specific date, defaults to today")
):
    """
    Get detailed list of clients assigned to current user for specified date
    """
    try:
        target_date = date_filter or date.today()

        # Get staff record for current user
        staff = db.query(Staff).filter(Staff.user_id == current_user.id).first()

        if not staff:
            return []

        # Get clients via staff assignments
        assignments = db.query(StaffAssignment).filter(
            and_(
                StaffAssignment.staff_id == staff.id,
                StaffAssignment.is_active == True
            )
        ).all()

        client_assignments = []
        for assignment in assignments:
            if assignment.client:
                # Get last interaction - simplified to avoid complex queries in loop
                # For now, just return None and can be enhanced later with a separate query
                client_assignments.append(ClientAssignment(
                    client_id=str(assignment.client.id),
                    client_name=f"{assignment.client.first_name} {assignment.client.last_name}",
                    client_code=assignment.client.client_id,
                    location="Primary Assignment",
                    shift_time="See Schedule",
                    status="assigned",
                    time_in=None,
                    time_out=None,
                    last_interaction=None
                ))

        return client_assignments

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve client assignments: {str(e)}"
        )

@router.get("/tasks-summary", response_model=TaskSummary)
async def get_tasks_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    date_filter: Optional[date] = Query(None, description="Filter by specific date, defaults to today")
):
    """
    Get summary of tasks for the current user
    """
    try:
        target_date = date_filter or date.today()

        # Get tasks for the current user
        base_query = db.query(Task).filter(
            Task.assigned_to == current_user.id
        )

        total_tasks = base_query.count()
        completed_tasks = base_query.filter(Task.status == TaskStatusEnum.COMPLETED).count()
        pending_tasks = base_query.filter(Task.status == TaskStatusEnum.PENDING).count()

        # Overdue tasks (pending or in-progress with due date in the past)
        overdue_tasks = base_query.filter(
            and_(
                Task.due_date < datetime.now(timezone.utc),
                Task.status.in_([TaskStatusEnum.PENDING, TaskStatusEnum.IN_PROGRESS])
            )
        ).count()

        return TaskSummary(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            pending_tasks=pending_tasks,
            overdue_tasks=overdue_tasks,
            completion_rate=0.0 if total_tasks == 0 else (completed_tasks / total_tasks) * 100
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve tasks summary: {str(e)}"
        )

@router.get("/quick-actions")
async def get_quick_actions(
    current_user: User = Depends(get_current_user)
):
    """
    Get available quick actions for the dashboard
    """
    try:
        # Define quick actions based on user role and permissions
        quick_actions = [
            {
                "id": "add_vitals",
                "title": "Add Vitals Log",
                "description": "Log blood pressure, glucose, etc.",
                "icon": "heart",
                "url": "/documentation/vitals"
            },
            {
                "id": "add_shift_note",
                "title": "Add Shift Note",
                "description": "Start a new shift narrative",
                "icon": "note",
                "url": "/documentation/shift-notes"
            },
            {
                "id": "upload_incident",
                "title": "Upload Incident",
                "description": "Attach to IR form",
                "icon": "camera",
                "url": "/documentation/incidents"
            },
            {
                "id": "record_meal",
                "title": "Record Meal Intake",
                "description": "Log breakfast/lunch/dinner",
                "icon": "utensils",
                "url": "/documentation/meals"
            },
            {
                "id": "view_schedule",
                "title": "View Full Schedule",
                "description": "Calendar for week",
                "icon": "calendar",
                "url": "/scheduling/calendar"
            }
        ]

        return {"quick_actions": quick_actions}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve quick actions: {str(e)}"
        )

@router.get("/recent-entries")
async def get_recent_entries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50, description="Number of recent entries to return")
):
    """
    Get recent documentation entries (vitals, shift notes, meals, incidents, activities) for the current DSP user
    """
    try:
        from app.models.vitals_log import VitalsLog
        from app.models.shift_note import ShiftNote
        from app.models.meal_log import MealLog
        from app.models.activity_log import ActivityLog
        from app.models.incident_report import IncidentReport as IncidentReportDoc
        from app.models.client import ClientLocation, ClientAssignment as ClientAssignmentModel

        recent_entries = []

        # Get staff record for current user
        staff = db.query(Staff).filter(Staff.user_id == current_user.id).first()

        if not staff:
            return {"entries": []}

        # Helper function to get client location - accepts client object to avoid duplicate queries
        def get_client_location(client):
            from app.models.location import Location

            if not client:
                return "Unknown Location"

            # First priority: Check client's direct location_id
            if client.location_id:
                location = db.query(Location).filter(
                    Location.id == client.location_id
                ).first()
                if location:
                    return location.name

            # Second priority: Check client assignment (legacy)
            assignment = db.query(ClientAssignmentModel).filter(
                ClientAssignmentModel.client_id == client.id,
                ClientAssignmentModel.is_current == True
            ).first()

            if assignment and assignment.location_id:
                location = db.query(ClientLocation).filter(
                    ClientLocation.id == assignment.location_id
                ).first()
                return location.name if location else "Unknown Location"

            return "Unknown Location"

        # Get recent vitals logs
        vitals = db.query(VitalsLog).filter(
            VitalsLog.staff_id == current_user.id
        ).order_by(VitalsLog.recorded_at.desc()).limit(limit).all()

        for vital in vitals:
            client = db.query(Client).filter(Client.id == vital.client_id).first()
            recorded_at = vital.recorded_at if vital.recorded_at else datetime.now()

            recent_entries.append({
                "date": recorded_at.strftime("%a, %b %d"),
                "time_in_kenya": recorded_at.strftime("%I:%M %p"),
                "client_name": client.full_name if client else "Unknown",
                "location": get_client_location(client),
                "activity_type": "Vitals Log",
                "status": "Completed",
                "created_at": make_aware(recorded_at)
            })

        # Get recent shift notes
        shift_notes = db.query(ShiftNote).filter(
            ShiftNote.staff_id == current_user.id
        ).order_by(ShiftNote.created_at.desc()).limit(limit).all()

        for note in shift_notes:
            client = db.query(Client).filter(Client.id == note.client_id).first()
            created_at = note.created_at if note.created_at else datetime.now()

            recent_entries.append({
                "date": created_at.strftime("%a, %b %d"),
                "time_in_kenya": created_at.strftime("%I:%M %p"),
                "client_name": client.full_name if client else "Unknown",
                "location": get_client_location(client),
                "activity_type": "Shift Note",
                "status": "Completed",
                "created_at": make_aware(created_at)
            })

        # Get recent meal logs
        meals = db.query(MealLog).filter(
            MealLog.staff_id == current_user.id
        ).order_by(MealLog.created_at.desc()).limit(limit).all()

        for meal in meals:
            client = db.query(Client).filter(Client.id == meal.client_id).first()
            created_at = meal.created_at if meal.created_at else datetime.now()

            recent_entries.append({
                "date": created_at.strftime("%a, %b %d"),
                "time_in_kenya": created_at.strftime("%I:%M %p"),
                "client_name": client.full_name if client else "Unknown",
                "location": get_client_location(client),
                "activity_type": "Meal Intake",
                "status": "Completed",
                "created_at": make_aware(created_at)
            })

        # Get recent activity logs
        activities = db.query(ActivityLog).filter(
            ActivityLog.staff_id == current_user.id
        ).order_by(ActivityLog.created_at.desc()).limit(limit).all()

        for activity in activities:
            client = db.query(Client).filter(Client.id == activity.client_id).first()
            created_at = activity.created_at if activity.created_at else datetime.now()

            recent_entries.append({
                "date": created_at.strftime("%a, %b %d"),
                "time_in_kenya": created_at.strftime("%I:%M %p"),
                "client_name": client.full_name if client else "Unknown",
                "location": get_client_location(client),
                "activity_type": "Activity Log",
                "status": "Completed",
                "created_at": make_aware(created_at)
            })

        # Get recent incident reports
        incidents = db.query(IncidentReportDoc).filter(
            IncidentReportDoc.staff_id == current_user.id
        ).order_by(IncidentReportDoc.created_at.desc()).limit(limit).all()

        for incident in incidents:
            client = db.query(Client).filter(Client.id == incident.client_id).first()
            created_at = incident.created_at if incident.created_at else datetime.now()

            # Get severity value - handle both enum and string
            severity_value = incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity).lower()

            status = "Completed" if severity_value in ["low", "LOW"] else "Urgent" if severity_value in ["high", "critical", "HIGH", "CRITICAL"] else "Pending"

            recent_entries.append({
                "date": created_at.strftime("%a, %b %d"),
                "time_in_kenya": created_at.strftime("%I:%M %p"),
                "client_name": client.full_name if client else "Unknown",
                "location": get_client_location(client),
                "activity_type": "Incident Report",
                "status": status,
                "created_at": make_aware(created_at)
            })

        # Sort by created_at and limit to requested count
        recent_entries.sort(key=lambda x: x["created_at"], reverse=True)
        recent_entries = recent_entries[:limit]

        # Remove created_at from response (used only for sorting)
        for entry in recent_entries:
            del entry["created_at"]

        return {"entries": recent_entries}

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving recent entries: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve recent entries: {str(e)}"
        )