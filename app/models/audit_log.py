"""
Comprehensive Audit Logging Models for HIPAA Compliance
Tracks all system activities, PHI access, and maintains compliance trails
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, Enum, Index, CheckConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.core.database import Base


class DataClassification(enum.Enum):
    """Classification of data being accessed/modified"""
    PHI = "phi"  # Protected Health Information
    PII = "pii"  # Personally Identifiable Information
    FINANCIAL = "financial"  # Financial/billing data
    ADMINISTRATIVE = "administrative"  # Admin operations
    GENERAL = "general"  # General system data


class AuditAction(enum.Enum):
    """Types of audit actions"""
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


class AuditLog(Base):
    """Main audit log table for all system activities"""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Action details
    action = Column(Enum(AuditAction), nullable=False)
    resource_type = Column(String(100), nullable=False)  # e.g., "client", "vitals", "medication"
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    resource_name = Column(String(255), nullable=True)  # Human-readable identifier

    # Data changes
    old_values = Column(JSONB, nullable=True)  # Previous state (for updates)
    new_values = Column(JSONB, nullable=True)  # New state
    changes_summary = Column(Text, nullable=True)  # Human-readable summary

    # Classification and compliance
    data_classification = Column(Enum(DataClassification), nullable=False, default=DataClassification.GENERAL)
    phi_accessed = Column(Boolean, default=False)
    consent_verified = Column(Boolean, default=True)

    # Request context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    request_id = Column(UUID(as_uuid=True), nullable=True)
    http_method = Column(String(10), nullable=True)
    endpoint = Column(String(255), nullable=True)

    # Response context
    response_status = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="audit_activities")
    organization = relationship("Organization", foreign_keys=[organization_id], backref="audit_logs")

    # Indexes for performance
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_org_created", "organization_id", "created_at"),
        Index("ix_audit_logs_classification", "data_classification", "phi_accessed"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
    )


class AuditExport(Base):
    """Track audit log exports for compliance"""
    __tablename__ = "audit_exports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    exported_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    # Export details
    export_format = Column(String(20), nullable=False)  # csv, json, pdf
    date_from = Column(DateTime, nullable=False)
    date_to = Column(DateTime, nullable=False)
    filters_applied = Column(JSONB, nullable=True)
    record_count = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Compliance tracking
    purpose = Column(Text, nullable=True)
    authorized_by = Column(String(255), nullable=True)
    external_audit_ref = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[exported_by])
    organization = relationship("Organization", foreign_keys=[organization_id])


class AuditSetting(Base):
    """Configuration for audit logging behavior"""
    __tablename__ = "audit_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True)

    # Retention settings
    retention_days = Column(Integer, default=2555, nullable=False)  # 7 years for HIPAA
    archive_after_days = Column(Integer, default=90)

    # Performance settings
    enable_async_logging = Column(Boolean, default=True)
    batch_size = Column(Integer, default=100)
    sampling_rate = Column(Integer, default=100)  # Percentage (100 = log everything)

    # Alert settings
    alert_on_phi_access = Column(Boolean, default=True)
    alert_on_breach = Column(Boolean, default=True)
    alert_on_failed_login = Column(Boolean, default=True)
    alert_email_addresses = Column(JSONB, default=list)

    # Compliance settings
    require_consent_verification = Column(Boolean, default=True)
    mask_sensitive_data = Column(Boolean, default=True)
    enable_integrity_check = Column(Boolean, default=True)

    # Feature flags
    log_read_operations = Column(Boolean, default=True)
    log_administrative_actions = Column(Boolean, default=True)
    log_api_responses = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id], backref="audit_setting")

    # Constraints
    __table_args__ = (
        CheckConstraint("retention_days >= 2555", name="check_min_retention"),  # HIPAA minimum
        CheckConstraint("sampling_rate >= 0 AND sampling_rate <= 100", name="check_sampling_rate"),
    )


class ComplianceViolation(Base):
    """Track and manage compliance violations detected by audit system"""
    __tablename__ = "compliance_violations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    audit_log_id = Column(UUID(as_uuid=True), ForeignKey("audit_logs.id", ondelete="CASCADE"))

    # Violation details
    violation_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=False)
    regulation_reference = Column(String(100))  # e.g., "HIPAA 164.312(a)(1)"

    # Status tracking
    status = Column(String(20), default="open")  # open, investigating, resolved, false_positive
    detected_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Resolution details
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resolution_notes = Column(Text, nullable=True)
    corrective_action = Column(Text, nullable=True)

    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id])
    audit_log = relationship("AuditLog", foreign_keys=[audit_log_id])
    acknowledger = relationship("User", foreign_keys=[acknowledged_by])

    # Indexes
    __table_args__ = (
        Index("ix_violations_org_status", "organization_id", "status"),
        Index("ix_violations_severity", "severity", "status"),
    )