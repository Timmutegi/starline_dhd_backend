"""
Pydantic Schemas for Audit API Endpoints
Defines request/response models for audit logging and compliance management
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


class AuditActionEnum(str, Enum):
    """Audit action types"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    PRINT = "print"
    SHARE = "share"
    CONSENT_CHANGE = "consent_change"
    ACCESS_DENIED = "access_denied"
    CONFIGURATION_CHANGE = "configuration_change"
    BREACH_DETECTED = "breach_detected"


class DataClassificationEnum(str, Enum):
    """Data classification types"""
    PHI = "phi"
    PII = "pii"
    FINANCIAL = "financial"
    ADMINISTRATIVE = "administrative"
    GENERAL = "general"


class UserSummary(BaseModel):
    """Minimal user information for audit logs"""
    id: str
    username: Optional[str]
    full_name: Optional[str]
    email: Optional[str]

    class Config:
        from_attributes = True


class OrganizationSummary(BaseModel):
    """Minimal organization information for audit logs"""
    id: str
    name: str

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Audit log response model"""
    id: str
    organization_id: Optional[str]
    user_id: Optional[str]
    action: AuditActionEnum
    resource_type: str
    resource_id: Optional[str]
    resource_name: Optional[str]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    changes_summary: Optional[str]
    data_classification: DataClassificationEnum
    phi_accessed: bool
    consent_verified: bool
    ip_address: Optional[str]
    user_agent: Optional[str]
    session_id: Optional[str]
    request_id: Optional[str]
    http_method: Optional[str]
    endpoint: Optional[str]
    response_status: Optional[int]
    error_message: Optional[str]
    duration_ms: Optional[int]
    created_at: datetime
    user: Optional[UserSummary]
    organization: Optional[OrganizationSummary]

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response"""
    logs: List[AuditLogResponse]
    total: int
    skip: int
    limit: int


class ComplianceViolationResponse(BaseModel):
    """Compliance violation response model"""
    id: str
    organization_id: str
    audit_log_id: str
    violation_type: str
    severity: str
    description: str
    regulation_reference: Optional[str]
    status: str
    detected_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    acknowledged_by: Optional[str]
    resolution_notes: Optional[str]
    corrective_action: Optional[str]

    class Config:
        from_attributes = True


class UserActivitySummary(BaseModel):
    """User activity summary for compliance reports"""
    user_id: str
    total_activities: int
    phi_accesses: int


class ViolationSummary(BaseModel):
    """Violation summary for compliance reports"""
    id: str
    type: str
    severity: str
    status: str
    detected_at: datetime


class ComplianceReportResponse(BaseModel):
    """Compliance report response model"""
    report_type: str
    organization_id: str
    period: Dict[str, str]
    summary: Dict[str, int]
    user_activity: List[UserActivitySummary]
    violations: List[ViolationSummary]
    generated_at: str


class AuditSettingsResponse(BaseModel):
    """Audit settings response model"""
    id: str
    organization_id: str
    retention_days: int
    archive_after_days: int
    enable_async_logging: bool
    batch_size: int
    sampling_rate: int
    alert_on_phi_access: bool
    alert_on_breach: bool
    alert_on_failed_login: bool
    alert_email_addresses: List[str]
    require_consent_verification: bool
    mask_sensitive_data: bool
    enable_integrity_check: bool
    log_read_operations: bool
    log_administrative_actions: bool
    log_api_responses: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AuditSettingsUpdate(BaseModel):
    """Audit settings update model"""
    retention_days: Optional[int] = Field(None, ge=2555, description="Minimum 7 years for HIPAA")
    archive_after_days: Optional[int] = Field(None, ge=1)
    enable_async_logging: Optional[bool] = None
    batch_size: Optional[int] = Field(None, ge=1, le=1000)
    sampling_rate: Optional[int] = Field(None, ge=0, le=100)
    alert_on_phi_access: Optional[bool] = None
    alert_on_breach: Optional[bool] = None
    alert_on_failed_login: Optional[bool] = None
    alert_email_addresses: Optional[List[str]] = None
    require_consent_verification: Optional[bool] = None
    mask_sensitive_data: Optional[bool] = None
    enable_integrity_check: Optional[bool] = None
    log_read_operations: Optional[bool] = None
    log_administrative_actions: Optional[bool] = None
    log_api_responses: Optional[bool] = None

    @validator('alert_email_addresses')
    def validate_emails(cls, v):
        if v is not None:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            for email in v:
                if not re.match(email_pattern, email):
                    raise ValueError(f'Invalid email address: {email}')
        return v


class AuditFilterParams(BaseModel):
    """Audit log filter parameters"""
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[AuditActionEnum] = None
    data_classification: Optional[DataClassificationEnum] = None
    phi_access_only: Optional[bool] = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ExportFormat(str, Enum):
    """Export format options"""
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"


class AuditExportRequest(BaseModel):
    """Audit export request model"""
    start_date: datetime
    end_date: datetime
    format: ExportFormat
    filters: Optional[AuditFilterParams] = None
    purpose: Optional[str] = Field(None, description="Purpose of the export")
    authorized_by: Optional[str] = Field(None, description="Person who authorized the export")
    audit_reference: Optional[str] = Field(None, description="External audit reference number")

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

    @validator('end_date')
    def validate_date_not_future(cls, v):
        if v > datetime.now():
            raise ValueError('end_date cannot be in the future')
        return v


class AuditExportResponse(BaseModel):
    """Audit export response model"""
    export_id: str
    status: str
    message: str
    created_at: datetime


class PHIAccessRequest(BaseModel):
    """PHI access logging request"""
    client_id: str
    data_type: str = Field(..., description="Type of PHI being accessed")
    purpose: str = Field(..., description="Purpose for accessing PHI")
    consent_verified: bool = Field(True, description="Whether patient consent was verified")


class PHIAccessResponse(BaseModel):
    """PHI access logging response"""
    audit_log_id: str
    message: str
    timestamp: datetime


class BreachReportRequest(BaseModel):
    """Security breach report request"""
    resource_type: str
    resource_id: Optional[str] = None
    violation_type: str
    description: str
    severity: str = Field("high", pattern="^(low|medium|high|critical)$")
    immediate_action_taken: Optional[str] = None


class BreachReportResponse(BaseModel):
    """Security breach report response"""
    violation_id: str
    audit_log_id: str
    status: str
    reported_at: datetime


class AuditStatistics(BaseModel):
    """Audit statistics summary"""
    total_logs: int
    phi_accesses: int
    violations: int
    failed_attempts: int
    unique_users: int
    most_active_user: Optional[str]
    most_accessed_resource: Optional[str]
    period_start: datetime
    period_end: datetime


class AuditDashboardResponse(BaseModel):
    """Audit dashboard data"""
    statistics: AuditStatistics
    recent_violations: List[ComplianceViolationResponse]
    recent_phi_access: List[AuditLogResponse]
    top_users_activity: List[UserActivitySummary]


class ViolationAcknowledgment(BaseModel):
    """Violation acknowledgment request"""
    resolution_notes: str = Field(..., min_length=10, description="Detailed resolution notes")
    corrective_action: Optional[str] = Field(None, description="Corrective action taken")
    follow_up_required: bool = Field(False, description="Whether follow-up is required")


class AuditSearchRequest(BaseModel):
    """Advanced audit search request"""
    query: str = Field(..., min_length=3, description="Search query")
    search_fields: List[str] = Field(default=["resource_name", "changes_summary", "error_message"])
    filters: Optional[AuditFilterParams] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class AuditSearchResponse(BaseModel):
    """Advanced audit search response"""
    results: List[AuditLogResponse]
    total_matches: int
    search_query: str
    execution_time_ms: int


class ComplianceMetrics(BaseModel):
    """Compliance metrics for monitoring"""
    hipaa_compliance_score: float = Field(..., ge=0, le=100)
    audit_coverage_percentage: float = Field(..., ge=0, le=100)
    violation_resolution_rate: float = Field(..., ge=0, le=100)
    average_resolution_time_hours: float = Field(..., ge=0)
    phi_access_control_score: float = Field(..., ge=0, le=100)
    data_integrity_score: float = Field(..., ge=0, le=100)
    last_calculated: datetime


class SystemAuditHealth(BaseModel):
    """System audit health check"""
    audit_logging_enabled: bool
    database_connectivity: bool
    retention_policy_active: bool
    alert_system_functional: bool
    integrity_check_passed: bool
    last_backup: Optional[datetime]
    storage_usage_percentage: float
    performance_metrics: Dict[str, Any]