from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from datetime import datetime, date, timedelta
from typing import Optional, List
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.client import Client
from app.models.staff import Staff
from app.models.scheduling import Appointment
from app.schemas.dashboard import (
    DashboardOverview,
    QuickStats,
    RecentActivity,
    ActivityItem,
    ClientAssignment,
    TaskSummary
)

router = APIRouter()

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

        # Get clients assigned today for current user
        clients_assigned_query = db.query(Client).join(
            # This would need proper assignment table - simplified for now
            text("SELECT client_id FROM client_assignments WHERE staff_id = :staff_id AND date(assignment_date) = :target_date")
        ).params(staff_id=current_user.id, target_date=target_date)

        clients_assigned = clients_assigned_query.count()

        # Get appointments today
        appointments_today = db.query(Appointment).filter(
            and_(
                Appointment.staff_id == current_user.id,
                func.date(Appointment.start_time) == target_date,
                Appointment.status.in_(['scheduled', 'in_progress'])
            )
        ).count()

        # Get completed tasks (simplified - would need proper task model)
        tasks_completed = 0  # Placeholder until task system is implemented

        # Get incidents reported today (placeholder)
        incidents_reported = 0  # Placeholder until incident system is implemented

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

        # This would need proper assignment/scheduling model - simplified for now
        # For now, we'll return clients based on appointments
        appointments = db.query(Appointment).filter(
            and_(
                Appointment.staff_id == current_user.id,
                func.date(Appointment.start_time) == target_date
            )
        ).all()

        client_assignments = []
        for apt in appointments:
            if apt.client:
                client_assignments.append(ClientAssignment(
                    client_id=str(apt.client.id),
                    client_name=f"{apt.client.first_name} {apt.client.last_name}",
                    client_code=apt.client.client_id,
                    location=apt.client.address or "No address",
                    shift_time=f"{apt.start_time.strftime('%H:%M')} - {apt.end_time.strftime('%H:%M')}" if apt.end_time else apt.start_time.strftime('%H:%M'),
                    status=apt.status,
                    time_in=apt.start_time if apt.status == 'completed' else None,
                    time_out=apt.end_time if apt.status == 'completed' else None
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

        # Placeholder implementation - would need proper task model
        total_tasks = 0
        completed_tasks = 0
        pending_tasks = 0
        overdue_tasks = 0

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