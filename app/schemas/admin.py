from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

class SystemStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNHEALTHY = "unhealthy"

class BulkAction(str, Enum):
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    SUSPEND = "suspend"
    DELETE = "delete"
    RESET_PASSWORD = "reset_password"

class SystemStats(BaseModel):
    total_organizations: int = Field(..., description="Total number of organizations")
    total_users: int = Field(..., description="Total number of users")
    total_clients: int = Field(..., description="Total number of clients")
    total_staff: int = Field(..., description="Total number of staff members")
    active_users_24h: int = Field(..., description="Users active in last 24 hours")
    appointments_today: int = Field(..., description="Appointments scheduled for today")

class SystemHealth(BaseModel):
    database_status: SystemStatus = Field(..., description="Database health status")
    api_status: SystemStatus = Field(..., description="API health status")
    storage_status: SystemStatus = Field(..., description="File storage health status")
    email_service_status: SystemStatus = Field(..., description="Email service health status")
    last_checked: Optional[datetime] = Field(None, description="When health was last checked")

class OrganizationSummary(BaseModel):
    id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    subdomain: str = Field(..., description="Organization subdomain")
    users_count: int = Field(..., description="Number of users in organization")
    clients_count: int = Field(..., description="Number of clients in organization")
    is_active: bool = Field(..., description="Whether organization is active")
    created_at: datetime = Field(..., description="When organization was created")

class UserActivitySummary(BaseModel):
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name")
    organization_name: str = Field(..., description="Organization name")
    role_name: Optional[str] = Field(None, description="Role name")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    days_since_login: Optional[int] = Field(None, description="Days since last login")
    login_count_period: int = Field(..., description="Login count in specified period")
    actions_count_period: int = Field(..., description="Actions performed in specified period")
    is_active: bool = Field(..., description="Whether user is active")

class RecentActivity(BaseModel):
    id: str = Field(..., description="Activity ID")
    user_id: str = Field(..., description="User who performed the action")
    user_name: str = Field(..., description="Name of user who performed the action")
    action: str = Field(..., description="Action performed")
    resource: str = Field(..., description="Resource affected")
    resource_id: Optional[str] = Field(None, description="ID of affected resource")
    timestamp: datetime = Field(..., description="When action was performed")
    ip_address: Optional[str] = Field(None, description="IP address of user")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional action metadata")

class AdminDashboardOverview(BaseModel):
    system_stats: SystemStats = Field(..., description="System-wide statistics")
    system_health: SystemHealth = Field(..., description="System health status")
    organizations: List[OrganizationSummary] = Field(..., description="Organization summaries")
    recent_activity: Optional[List[RecentActivity]] = Field(None, description="Recent system activity")
    last_updated: datetime = Field(..., description="When dashboard was last updated")

class AdminNotificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Notification title")
    message: str = Field(..., min_length=1, max_length=1000, description="Notification message")
    type: str = Field(default="info", description="Notification type")
    category: str = Field(default="system", description="Notification category")
    action_url: Optional[str] = Field(None, max_length=500, description="Action URL")
    action_text: Optional[str] = Field(None, max_length=100, description="Action button text")
    expires_at: Optional[datetime] = Field(None, description="When notification expires")

    # Targeting options
    target_organization_id: Optional[str] = Field(None, description="Target specific organization")
    target_role: Optional[str] = Field(None, description="Target specific role")
    target_user_ids: Optional[List[str]] = Field(None, description="Target specific users")

class BulkActionRequest(BaseModel):
    action: BulkAction = Field(..., description="Action to perform")
    target_ids: List[str] = Field(..., min_items=1, description="Target user/entity IDs")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for bulk action")

class AuditLogEntry(BaseModel):
    id: str = Field(..., description="Audit log entry ID")
    user_id: str = Field(..., description="User who performed the action")
    user_name: str = Field(..., description="Name of user who performed the action")
    organization_id: str = Field(..., description="Organization context")
    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[str] = Field(None, description="ID of affected resource")
    old_values: Optional[Dict[str, Any]] = Field(None, description="Previous values")
    new_values: Optional[Dict[str, Any]] = Field(None, description="New values")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    timestamp: datetime = Field(..., description="When action was performed")

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    subdomain: str = Field(..., min_length=3, max_length=100, description="Subdomain")
    contact_email: str = Field(..., description="Contact email")
    contact_phone: Optional[str] = Field(None, description="Contact phone")
    address: Optional[str] = Field(None, description="Organization address")
    timezone: str = Field(default="UTC", description="Organization timezone")

    @validator('subdomain')
    def validate_subdomain(cls, v):
        if not v.isalnum():
            raise ValueError('Subdomain must be alphanumeric')
        return v.lower()

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None

class AdminUserCreate(BaseModel):
    email: str = Field(..., description="User email")
    username: str = Field(..., min_length=3, max_length=100, description="Username")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    organization_id: str = Field(..., description="Organization ID")
    role_id: str = Field(..., description="Role ID")
    is_super_admin: bool = Field(default=False, description="Super admin status")
    send_welcome_email: bool = Field(default=True, description="Send welcome email")

class SystemConfiguration(BaseModel):
    smtp_enabled: bool = Field(..., description="SMTP email enabled")
    file_upload_max_size: int = Field(..., description="Max file upload size in MB")
    session_timeout: int = Field(..., description="Session timeout in minutes")
    password_min_length: int = Field(..., description="Minimum password length")
    two_factor_required: bool = Field(..., description="2FA required for all users")
    maintenance_mode: bool = Field(..., description="System maintenance mode")

class UsageMetrics(BaseModel):
    period_start: date = Field(..., description="Metrics period start")
    period_end: date = Field(..., description="Metrics period end")
    total_logins: int = Field(..., description="Total logins in period")
    unique_users: int = Field(..., description="Unique users in period")
    total_api_calls: int = Field(..., description="Total API calls in period")
    storage_used_gb: float = Field(..., description="Storage used in GB")
    average_session_duration: int = Field(..., description="Average session duration in minutes")