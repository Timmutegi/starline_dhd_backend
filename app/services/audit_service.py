"""
Audit Service for HIPAA-Compliant Logging
Centralized service for managing audit logs, compliance monitoring, and breach detection
"""
import json
import uuid
import asyncio
import hashlib
import enum
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from app.models.audit_log import (
    AuditLog, AuditExport, AuditSetting, ComplianceViolation,
    DataClassification, AuditAction
)
from app.models.user import User
from app.core.database import get_db
from app.core.config import settings
from app.services.email_service import EmailService
import logging

logger = logging.getLogger(__name__)


def serialize_for_json(obj: Any) -> Any:
    """Recursively serialize objects to JSON-compatible types"""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, enum.Enum):
        return obj.value
    else:
        return obj


class AuditService:
    """Centralized audit logging service with HIPAA compliance features"""

    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    def log_action(
        self,
        action: AuditAction,
        resource_type: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        http_method: Optional[str] = None,
        endpoint: Optional[str] = None,
        response_status: Optional[int] = None,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AuditLog]:
        """
        Create comprehensive audit log entry

        Args:
            action: Type of action performed
            resource_type: Type of resource being acted upon
            user_id: ID of user performing action
            organization_id: Organization context
            resource_id: ID of specific resource
            resource_name: Human-readable resource identifier
            old_values: Previous state (for updates)
            new_values: New state
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: User session ID
            request_id: Unique request identifier
            http_method: HTTP method used
            endpoint: API endpoint accessed
            response_status: HTTP response status
            duration_ms: Request duration in milliseconds
            error_message: Error message if applicable
            metadata: Additional context data

        Returns:
            Created audit log entry or None if logging disabled
        """
        try:
            # Check if audit logging is enabled for this organization
            if not self._should_log_action(organization_id, action, resource_type):
                return None

            # Determine data classification
            data_classification = self._classify_data(resource_type, new_values, old_values)
            phi_accessed = data_classification == DataClassification.PHI

            # Mask sensitive data if required
            if self._should_mask_data(organization_id):
                old_values = self._mask_sensitive_data(old_values)
                new_values = self._mask_sensitive_data(new_values)

            # Serialize UUID objects and other non-JSON types
            old_values = serialize_for_json(old_values)
            new_values = serialize_for_json(new_values)

            # Generate change summary
            changes_summary = self._generate_changes_summary(old_values, new_values, action)

            # Verify consent if accessing PHI
            consent_verified = True
            if phi_accessed and resource_type in ['client', 'vitals', 'medication', 'incident_report']:
                consent_verified = self._verify_consent(user_id, resource_id, action)

            # Create audit log entry
            audit_log = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                old_values=old_values,
                new_values=new_values,
                changes_summary=changes_summary,
                data_classification=data_classification,
                phi_accessed=phi_accessed,
                consent_verified=consent_verified,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                request_id=request_id,
                http_method=http_method,
                endpoint=endpoint,
                response_status=response_status,
                error_message=error_message,
                duration_ms=duration_ms,
                created_at=datetime.utcnow()
            )

            self.db.add(audit_log)
            self.db.commit()

            # Check for compliance violations
            self._check_compliance_violations(audit_log)

            # Send alerts if necessary
            self._send_alerts_if_needed(audit_log)

            return audit_log

        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            self.db.rollback()
            return None

    def log_phi_access(
        self,
        user_id: str,
        client_id: str,
        data_type: str,
        purpose: str,
        organization_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Optional[AuditLog]:
        """Log PHI access with specific compliance requirements"""
        return self.log_action(
            action=AuditAction.READ,
            resource_type="phi_access",
            user_id=user_id,
            organization_id=organization_id,
            resource_id=client_id,
            resource_name=f"Client PHI - {data_type}",
            new_values={"data_type": data_type, "purpose": purpose},
            ip_address=ip_address
        )

    def log_breach_attempt(
        self,
        user_id: Optional[str],
        resource_type: str,
        resource_id: Optional[str],
        violation_type: str,
        description: str,
        severity: str = "high",
        organization_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log potential security breach and create violation record"""
        # Create audit log for breach attempt
        audit_log = self.log_action(
            action=AuditAction.BREACH_DETECTED,
            resource_type=resource_type,
            user_id=user_id,
            organization_id=organization_id,
            resource_id=resource_id,
            error_message=description,
            ip_address=ip_address
        )

        if audit_log:
            # Create compliance violation
            violation = ComplianceViolation(
                organization_id=organization_id,
                audit_log_id=audit_log.id,
                violation_type=violation_type,
                severity=severity,
                description=description,
                detected_at=datetime.utcnow(),
                status="open"
            )
            self.db.add(violation)
            self.db.commit()

            # Send immediate alert
            self._send_breach_alert(violation, audit_log)

    def get_user_activity(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        organization_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get user activity history with optional date filtering"""
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)

        if organization_id:
            query = query.filter(AuditLog.organization_id == organization_id)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return query.order_by(desc(AuditLog.created_at)).limit(limit).all()

    def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        organization_id: Optional[str] = None
    ) -> List[AuditLog]:
        """Get complete change history for a specific resource"""
        query = self.db.query(AuditLog).filter(
            and_(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id
            )
        )

        if organization_id:
            query = query.filter(AuditLog.organization_id == organization_id)

        return query.order_by(desc(AuditLog.created_at)).all()

    def get_phi_access_logs(
        self,
        client_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        organization_id: Optional[str] = None
    ) -> List[AuditLog]:
        """Get PHI access logs for compliance reporting"""
        query = self.db.query(AuditLog).filter(AuditLog.phi_accessed == True)

        if client_id:
            query = query.filter(AuditLog.resource_id == client_id)

        if organization_id:
            query = query.filter(AuditLog.organization_id == organization_id)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return query.order_by(desc(AuditLog.created_at)).all()

    def generate_compliance_report(
        self,
        organization_id: str,
        start_date: datetime,
        end_date: datetime,
        report_type: str = "hipaa"
    ) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        base_query = self.db.query(AuditLog).filter(
            and_(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date
            )
        )

        # Get summary statistics
        total_activities = base_query.count()
        phi_accesses = base_query.filter(AuditLog.phi_accessed == True).count()
        failed_attempts = base_query.filter(AuditLog.response_status >= 400).count()

        # Get user activity breakdown
        user_activity = self.db.query(
            AuditLog.user_id,
            func.count(AuditLog.id).label('activity_count'),
            func.count(func.nullif(AuditLog.phi_accessed, False)).label('phi_access_count')
        ).filter(
            and_(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date
            )
        ).group_by(AuditLog.user_id).all()

        # Get violations
        violations = self.db.query(ComplianceViolation).filter(
            and_(
                ComplianceViolation.organization_id == organization_id,
                ComplianceViolation.detected_at >= start_date,
                ComplianceViolation.detected_at <= end_date
            )
        ).all()

        return {
            "report_type": report_type,
            "organization_id": organization_id,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_activities": total_activities,
                "phi_accesses": phi_accesses,
                "failed_attempts": failed_attempts,
                "violations_count": len(violations)
            },
            "user_activity": [
                {
                    "user_id": str(activity.user_id),
                    "total_activities": activity.activity_count,
                    "phi_accesses": activity.phi_access_count or 0
                }
                for activity in user_activity
            ],
            "violations": [
                {
                    "id": str(violation.id),
                    "type": violation.violation_type,
                    "severity": violation.severity,
                    "status": violation.status,
                    "detected_at": violation.detected_at.isoformat()
                }
                for violation in violations
            ],
            "generated_at": datetime.utcnow().isoformat()
        }

    def _should_log_action(self, organization_id: Optional[str], action: AuditAction, resource_type: str) -> bool:
        """Determine if action should be logged based on audit settings"""
        if not organization_id:
            return True  # Log everything for system-level actions

        settings = self._get_audit_settings(organization_id)
        if not settings:
            return True  # Default to logging if no settings

        # Check sampling rate
        if settings.sampling_rate < 100:
            import random
            if random.randint(1, 100) > settings.sampling_rate:
                return False

        # Check specific feature flags
        if action == AuditAction.READ and not settings.log_read_operations:
            return False

        return True

    def _classify_data(self, resource_type: str, new_values: Optional[Dict], old_values: Optional[Dict]) -> DataClassification:
        """Classify data based on resource type and content"""
        phi_resources = ['client', 'vitals', 'medication', 'incident_report', 'health_record']
        pii_resources = ['user', 'staff', 'contact']
        financial_resources = ['billing', 'payment', 'invoice']

        if resource_type in phi_resources:
            return DataClassification.PHI
        elif resource_type in pii_resources:
            return DataClassification.PII
        elif resource_type in financial_resources:
            return DataClassification.FINANCIAL
        elif resource_type in ['organization', 'role', 'permission']:
            return DataClassification.ADMINISTRATIVE
        else:
            return DataClassification.GENERAL

    def _mask_sensitive_data(self, data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Mask sensitive fields in audit data"""
        if not data:
            return data

        sensitive_fields = ['password', 'ssn', 'credit_card', 'bank_account', 'api_key', 'token']
        masked_data = data.copy()

        for field in sensitive_fields:
            if field in masked_data:
                masked_data[field] = "***MASKED***"

        return masked_data

    def _generate_changes_summary(self, old_values: Optional[Dict], new_values: Optional[Dict], action: AuditAction) -> str:
        """Generate human-readable summary of changes"""
        if action == AuditAction.CREATE:
            return "Record created"
        elif action == AuditAction.DELETE:
            return "Record deleted"
        elif action == AuditAction.UPDATE and old_values and new_values:
            changes = []
            for key, new_value in new_values.items():
                old_value = old_values.get(key)
                if old_value != new_value:
                    changes.append(f"{key}: {old_value} → {new_value}")
            return "; ".join(changes) if changes else "No changes detected"
        else:
            return f"Performed {action.value} action"

    def _verify_consent(self, user_id: Optional[str], resource_id: Optional[str], action: AuditAction) -> bool:
        """Verify user has consent to access PHI (placeholder implementation)"""
        # This would implement actual consent verification logic
        # For now, return True but log the consent check
        return True

    def _check_compliance_violations(self, audit_log: AuditLog) -> None:
        """Check for potential compliance violations"""
        # Check for unusual access patterns
        if audit_log.phi_accessed:
            self._check_unusual_phi_access(audit_log)

        # Check for access outside business hours
        if audit_log.created_at.hour < 6 or audit_log.created_at.hour > 22:
            self._flag_after_hours_access(audit_log)

        # Check for multiple failed attempts
        if audit_log.response_status and audit_log.response_status >= 400:
            self._check_failed_attempts(audit_log)

    def _check_unusual_phi_access(self, audit_log: AuditLog) -> None:
        """Check for unusual PHI access patterns"""
        if not audit_log.user_id:
            return

        # Check access volume in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_access_count = self.db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == audit_log.user_id,
                AuditLog.phi_accessed == True,
                AuditLog.created_at >= one_hour_ago
            )
        ).count()

        if recent_access_count > 50:  # Configurable threshold
            self.log_breach_attempt(
                user_id=audit_log.user_id,
                resource_type="phi_access",
                resource_id=audit_log.resource_id,
                violation_type="excessive_phi_access",
                description=f"User accessed PHI {recent_access_count} times in the last hour",
                severity="medium",
                organization_id=audit_log.organization_id
            )

    def _flag_after_hours_access(self, audit_log: AuditLog) -> None:
        """Flag potential after-hours PHI access"""
        if audit_log.phi_accessed:
            violation = ComplianceViolation(
                organization_id=audit_log.organization_id,
                audit_log_id=audit_log.id,
                violation_type="after_hours_phi_access",
                severity="low",
                description=f"PHI accessed outside business hours at {audit_log.created_at}",
                detected_at=datetime.utcnow(),
                status="open"
            )
            self.db.add(violation)

    def _check_failed_attempts(self, audit_log: AuditLog) -> None:
        """Check for multiple failed access attempts"""
        if not audit_log.user_id:
            return

        # Check failed attempts in last 15 minutes
        fifteen_min_ago = datetime.utcnow() - timedelta(minutes=15)
        failed_count = self.db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == audit_log.user_id,
                AuditLog.response_status >= 400,
                AuditLog.created_at >= fifteen_min_ago
            )
        ).count()

        if failed_count > 5:  # Configurable threshold
            self.log_breach_attempt(
                user_id=audit_log.user_id,
                resource_type="authentication",
                violation_type="multiple_failed_attempts",
                description=f"User had {failed_count} failed attempts in 15 minutes",
                severity="high",
                organization_id=audit_log.organization_id,
                ip_address=audit_log.ip_address
            )

    def _get_audit_settings(self, organization_id: str) -> Optional[AuditSetting]:
        """Get audit settings for organization"""
        return self.db.query(AuditSetting).filter(
            AuditSetting.organization_id == organization_id
        ).first()

    def _should_mask_data(self, organization_id: Optional[str]) -> bool:
        """Check if sensitive data should be masked"""
        if not organization_id:
            return True

        settings = self._get_audit_settings(organization_id)
        return settings.mask_sensitive_data if settings else True

    def _send_alerts_if_needed(self, audit_log: AuditLog) -> None:
        """Send alerts based on audit activity"""
        if not audit_log.organization_id:
            return

        settings = self._get_audit_settings(audit_log.organization_id)
        if not settings:
            return

        # Send PHI access alerts
        if audit_log.phi_accessed and settings.alert_on_phi_access:
            self._send_phi_access_alert(audit_log)

        # Send failed login alerts
        if (audit_log.action == AuditAction.LOGIN and
            audit_log.response_status and audit_log.response_status >= 400 and
            settings.alert_on_failed_login):
            self._send_failed_login_alert(audit_log)

    def _send_phi_access_alert(self, audit_log: AuditLog) -> None:
        """Send PHI access notification"""
        try:
            # Get alert email addresses from settings
            alert_emails = settings.AUDIT_ALERT_EMAIL.split(',')

            # Send PHI access alert email asynchronously
            for email in alert_emails:
                asyncio.create_task(
                    self.email_service.send_email(
                        to=email.strip(),
                        subject="PHI Access Alert - Starline",
                        template_name="phi_access_alert.html",
                        context={
                        "client_id": audit_log.resource_id,
                        "client_name": audit_log.resource_name or "Unknown",
                        "data_type": audit_log.resource_type,
                        "access_time": audit_log.created_at.isoformat(),
                        "user_id": audit_log.user_id,
                        "user_name": "User",  # Would be populated from user lookup
                        "user_email": "user@example.com",  # Would be populated from user lookup
                        "user_role": "Staff",  # Would be populated from user lookup
                        "ip_address": audit_log.ip_address,
                        "purpose": "System access",
                        "consent_status": "Verified" if audit_log.consent_verified else "Not Verified",
                        "audit_log_id": str(audit_log.id),
                        "session_id": str(audit_log.session_id) if audit_log.session_id else "N/A",
                        "phi_audit_url": f"{settings.FRONTEND_URL}/admin/audit/phi",
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    })
                )
            logger.info(f"PHI access alert sent for user {audit_log.user_id} accessing resource {audit_log.resource_id}")
        except Exception as e:
            logger.error(f"Failed to send PHI access alert: {e}")

    def _send_failed_login_alert(self, audit_log: AuditLog) -> None:
        """Send failed login notification"""
        try:
            # Get security alert email addresses
            alert_emails = settings.SECURITY_ALERT_EMAILS.split(',')

            for email in alert_emails:
                asyncio.create_task(
                    self.email_service.send_email(
                        to=email.strip(),
                        subject="Failed Login Alert - Starline Security",
                        template_name="failed_login_alert.html",
                        context={
                        "target_email": audit_log.new_values.get("email", "Unknown") if audit_log.new_values else "Unknown",
                        "attempt_count": 5,  # Would be calculated from recent attempts
                        "time_window": 15,
                        "ip_address": audit_log.ip_address,
                        "location": "Unknown",  # Would be populated from IP geolocation
                        "user_agent": audit_log.user_agent,
                        "first_attempt_time": audit_log.created_at.isoformat(),
                        "last_attempt_time": audit_log.created_at.isoformat(),
                        "account_locked": False,  # Would be determined from user status
                        "lockout_duration": 30,
                        "similar_attempts": 0,  # Would be calculated
                        "alert_id": str(audit_log.id),
                        "audit_log_ids": str(audit_log.id),
                        "security_dashboard_url": f"{settings.FRONTEND_URL}/admin/security",
                        "unlock_account_url": f"{settings.FRONTEND_URL}/admin/users/unlock",
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    })
                )
            logger.warning(f"Failed login alert sent for attempt from {audit_log.ip_address}")
        except Exception as e:
            logger.error(f"Failed to send failed login alert: {e}")

    def _send_breach_alert(self, violation: ComplianceViolation, audit_log: AuditLog) -> None:
        """Send immediate breach alert"""
        try:
            # Get security alert email addresses
            alert_emails = settings.SECURITY_ALERT_EMAILS.split(',')

            for email in alert_emails:
                asyncio.create_task(
                    self.email_service.send_email(
                        to=email.strip(),
                        subject=f"SECURITY BREACH ALERT - {violation.severity.upper()} - Starline",
                        template_name="security_breach_alert.html",
                        context={
                        "violation_type": violation.violation_type,
                        "severity": violation.severity.upper(),
                        "detected_at": violation.detected_at.isoformat(),
                        "resource_type": audit_log.resource_type,
                        "resource_id": str(audit_log.resource_id) if audit_log.resource_id else "N/A",
                        "user_id": str(audit_log.user_id) if audit_log.user_id else "Unknown",
                        "user_name": "Unknown User",  # Would be populated from user lookup
                        "ip_address": audit_log.ip_address or "Unknown",
                        "description": violation.description,
                        "immediate_action": "Account temporarily restricted pending investigation",
                        "violation_id": str(violation.id),
                        "audit_log_id": str(audit_log.id),
                        "audit_dashboard_url": f"{settings.FRONTEND_URL}/admin/audit",
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    })
                )
            logger.critical(f"Security breach alert sent: {violation.violation_type} - {violation.severity}")
        except Exception as e:
            logger.error(f"Failed to send breach alert: {e}")