from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import List, Optional
from enum import Enum

class ActivityType(str, Enum):
    APPOINTMENT = "appointment"
    TASK = "task"
    INCIDENT = "incident"
    VITALS = "vitals"
    SHIFT_NOTE = "shift_note"
    MEDICATION = "medication"

class ActivityStatus(str, Enum):
    COMPLETED = "completed"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CANCELLED = "cancelled"
    DONE = "done"
    SKIPPED = "skipped"
    URGENT = "urgent"

class QuickStats(BaseModel):
    clients_assigned_today: int = Field(..., description="Number of clients assigned today")
    tasks_completed: int = Field(..., description="Number of tasks completed")
    incidents_reported: int = Field(..., description="Number of incidents reported today")
    appointments_today: int = Field(..., description="Number of appointments today")

class ActivityItem(BaseModel):
    id: str = Field(..., description="Unique identifier for the activity")
    type: ActivityType = Field(..., description="Type of activity")
    title: str = Field(..., description="Title of the activity")
    description: Optional[str] = Field(None, description="Description or notes")
    timestamp: datetime = Field(..., description="When the activity occurred")
    status: ActivityStatus = Field(..., description="Current status of the activity")
    client_name: Optional[str] = Field(None, description="Associated client name")

class RecentActivity(BaseModel):
    items: List[ActivityItem] = Field(default=[], description="List of recent activities")

class ClientAssignment(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    client_name: str = Field(..., description="Client full name")
    client_code: str = Field(..., description="Client identification code")
    location: str = Field(..., description="Client location or address")
    shift_time: str = Field(..., description="Scheduled shift time range")
    status: str = Field(..., description="Current status of assignment")
    time_in: Optional[datetime] = Field(None, description="Actual time clocked in")
    time_out: Optional[datetime] = Field(None, description="Actual time clocked out")
    last_interaction: Optional[str] = Field(None, description="Timestamp of last interaction with client")

class TaskSummary(BaseModel):
    total_tasks: int = Field(..., description="Total number of tasks")
    completed_tasks: int = Field(..., description="Number of completed tasks")
    pending_tasks: int = Field(..., description="Number of pending tasks")
    overdue_tasks: int = Field(..., description="Number of overdue tasks")
    completion_rate: float = Field(..., description="Task completion rate as percentage")

class DashboardOverview(BaseModel):
    user_name: str = Field(..., description="Current user's full name")
    organization_name: str = Field(..., description="Organization name")
    quick_stats: QuickStats = Field(..., description="Quick statistics overview")
    recent_activity: RecentActivity = Field(..., description="Recent activity feed")
    current_date: date = Field(..., description="Current date for the dashboard")

class QuickAction(BaseModel):
    id: str = Field(..., description="Unique identifier for the action")
    title: str = Field(..., description="Display title for the action")
    description: str = Field(..., description="Description of what the action does")
    icon: str = Field(..., description="Icon identifier for the action")
    url: str = Field(..., description="URL or route for the action")
    enabled: bool = Field(default=True, description="Whether the action is enabled")

class DashboardQuickActions(BaseModel):
    quick_actions: List[QuickAction] = Field(..., description="List of available quick actions")