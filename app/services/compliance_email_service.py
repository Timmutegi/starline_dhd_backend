"""
Compliance Email Service for Audit Alerts and Reports
Handles sending HIPAA-compliant email notifications for security and compliance events
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from app.services.email_service import EmailService
from app.core.config import settings
from app.models.audit_log import AuditLog, ComplianceViolation
import logging

logger = logging.getLogger(__name__)


class ComplianceEmailService:
    """Service for sending compliance and security related emails"""

    def __init__(self):
        self.email_service = EmailService()

    def send_weekly_compliance_summary(
        self,
        organization_name: str,
        summary_data: Dict[str, Any],
        recipient_emails: Optional[List[str]] = None
    ) -> bool:
        """Send weekly compliance summary report"""
        try:
            # Use configured compliance report emails if none provided
            emails = recipient_emails or settings.COMPLIANCE_REPORT_EMAILS.split(',')

            for email in emails:
                success = self.email_service.send_email(
                    to_email=email.strip(),
                    subject=f"Weekly Compliance Report - {organization_name}",
                    template_name="compliance_summary.html",
                    template_data={
                        "organization_name": organization_name,
                        "start_date": summary_data.get("start_date", ""),
                        "end_date": summary_data.get("end_date", ""),
                        "total_activities": summary_data.get("total_activities", 0),
                        "phi_accesses": summary_data.get("phi_accesses", 0),
                        "unique_users": summary_data.get("unique_users", 0),
                        "failed_attempts": summary_data.get("failed_attempts", 0),
                        "violations_count": summary_data.get("violations_count", 0),
                        "recent_violations": summary_data.get("recent_violations", []),
                        "top_users": summary_data.get("top_users", []),
                        "compliance_dashboard_url": f"{settings.FRONTEND_URL}/admin/compliance",
                        "download_report_url": f"{settings.FRONTEND_URL}/admin/compliance/download",
                        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                        "next_report_date": (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)).strftime("%Y-%m-%d"),
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    }
                )

                if not success:
                    logger.error(f"Failed to send compliance summary to {email}")
                    return False

            logger.info(f"Weekly compliance summary sent to {len(emails)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send weekly compliance summary: {e}")
            return False

    def send_phi_access_notification(
        self,
        audit_log: AuditLog,
        user_info: Optional[Dict[str, str]] = None,
        recipient_emails: Optional[List[str]] = None
    ) -> bool:
        """Send PHI access notification"""
        try:
            emails = recipient_emails or settings.AUDIT_ALERT_EMAIL.split(',')
            user_info = user_info or {}

            for email in emails:
                success = self.email_service.send_email(
                    to_email=email.strip(),
                    subject="PHI Access Notification - Starline",
                    template_name="phi_access_alert.html",
                    template_data={
                        "client_id": audit_log.resource_id,
                        "client_name": audit_log.resource_name or "Unknown",
                        "data_type": audit_log.resource_type,
                        "access_time": audit_log.created_at.isoformat(),
                        "user_id": audit_log.user_id,
                        "user_name": user_info.get("name", "Unknown User"),
                        "user_email": user_info.get("email", "unknown@example.com"),
                        "user_role": user_info.get("role", "Staff"),
                        "ip_address": audit_log.ip_address or "Unknown",
                        "purpose": audit_log.new_values.get("purpose", "System access") if audit_log.new_values else "System access",
                        "consent_status": "Verified" if audit_log.consent_verified else "Not Verified",
                        "audit_log_id": str(audit_log.id),
                        "session_id": str(audit_log.session_id) if audit_log.session_id else "N/A",
                        "phi_audit_url": f"{settings.FRONTEND_URL}/admin/audit/phi",
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    }
                )

                if not success:
                    logger.error(f"Failed to send PHI access alert to {email}")
                    return False

            logger.info(f"PHI access notification sent for user {audit_log.user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send PHI access notification: {e}")
            return False

    def send_security_breach_alert(
        self,
        violation: ComplianceViolation,
        audit_log: AuditLog,
        user_info: Optional[Dict[str, str]] = None,
        recipient_emails: Optional[List[str]] = None
    ) -> bool:
        """Send immediate security breach alert"""
        try:
            emails = recipient_emails or settings.SECURITY_ALERT_EMAILS.split(',')
            user_info = user_info or {}

            for email in emails:
                success = self.email_service.send_email(
                    to_email=email.strip(),
                    subject=f"🚨 SECURITY BREACH ALERT - {violation.severity.upper()} - Starline",
                    template_name="security_breach_alert.html",
                    template_data={
                        "violation_type": violation.violation_type,
                        "severity": violation.severity.upper(),
                        "detected_at": violation.detected_at.isoformat(),
                        "resource_type": audit_log.resource_type,
                        "resource_id": str(audit_log.resource_id) if audit_log.resource_id else "N/A",
                        "user_id": str(audit_log.user_id) if audit_log.user_id else "Unknown",
                        "user_name": user_info.get("name", "Unknown User"),
                        "ip_address": audit_log.ip_address or "Unknown",
                        "description": violation.description,
                        "immediate_action": "Account access restricted pending investigation",
                        "violation_id": str(violation.id),
                        "audit_log_id": str(audit_log.id),
                        "audit_dashboard_url": f"{settings.FRONTEND_URL}/admin/audit",
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    }
                )

                if not success:
                    logger.error(f"Failed to send breach alert to {email}")
                    return False

            logger.critical(f"Security breach alert sent: {violation.violation_type} - {violation.severity}")
            return True

        except Exception as e:
            logger.error(f"Failed to send security breach alert: {e}")
            return False

    def send_failed_login_alert(
        self,
        audit_log: AuditLog,
        attempt_details: Dict[str, Any],
        recipient_emails: Optional[List[str]] = None
    ) -> bool:
        """Send failed login attempt alert"""
        try:
            emails = recipient_emails or settings.SECURITY_ALERT_EMAILS.split(',')

            for email in emails:
                success = self.email_service.send_email(
                    to_email=email.strip(),
                    subject="⚠️ Failed Login Alert - Starline Security",
                    template_name="failed_login_alert.html",
                    template_data={
                        "target_email": attempt_details.get("target_email", "Unknown"),
                        "attempt_count": attempt_details.get("attempt_count", 1),
                        "time_window": attempt_details.get("time_window", 15),
                        "ip_address": audit_log.ip_address or "Unknown",
                        "location": attempt_details.get("location", "Unknown"),
                        "user_agent": audit_log.user_agent or "Unknown",
                        "first_attempt_time": attempt_details.get("first_attempt_time", audit_log.created_at.isoformat()),
                        "last_attempt_time": audit_log.created_at.isoformat(),
                        "account_locked": attempt_details.get("account_locked", False),
                        "lockout_duration": attempt_details.get("lockout_duration", 30),
                        "similar_attempts": attempt_details.get("similar_attempts", 0),
                        "alert_id": str(audit_log.id),
                        "audit_log_ids": str(audit_log.id),
                        "security_dashboard_url": f"{settings.FRONTEND_URL}/admin/security",
                        "unlock_account_url": f"{settings.FRONTEND_URL}/admin/users/unlock",
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    }
                )

                if not success:
                    logger.error(f"Failed to send failed login alert to {email}")
                    return False

            logger.warning(f"Failed login alert sent for IP {audit_log.ip_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to send failed login alert: {e}")
            return False

    def send_account_lockout_notification(
        self,
        user_email: str,
        lockout_reason: str,
        lockout_duration_minutes: int,
        unlock_url: str,
        recipient_emails: Optional[List[str]] = None
    ) -> bool:
        """Send account lockout notification"""
        try:
            emails = recipient_emails or settings.SECURITY_ALERT_EMAILS.split(',')

            for email in emails:
                success = self.email_service.send_email(
                    to_email=email.strip(),
                    subject=f"🔒 Account Lockout Notification - {user_email}",
                    template_name="account_locked.html",
                    template_data={
                        "user_email": user_email,
                        "lockout_reason": lockout_reason,
                        "lockout_duration": lockout_duration_minutes,
                        "unlock_url": unlock_url,
                        "contact_email": settings.FROM_EMAIL,
                        "frontend_url": settings.FRONTEND_URL
                    }
                )

                if not success:
                    logger.error(f"Failed to send lockout notification to {email}")
                    return False

            logger.info(f"Account lockout notification sent for {user_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send account lockout notification: {e}")
            return False

    def get_configured_alert_emails(self) -> Dict[str, List[str]]:
        """Get all configured alert email addresses"""
        return {
            "audit_alerts": settings.AUDIT_ALERT_EMAIL.split(','),
            "security_alerts": settings.SECURITY_ALERT_EMAILS.split(','),
            "compliance_reports": settings.COMPLIANCE_REPORT_EMAILS.split(',')
        }

    def test_email_configuration(self) -> Dict[str, bool]:
        """Test email configuration by sending test emails"""
        test_results = {}

        try:
            # Test audit alert email
            audit_emails = settings.AUDIT_ALERT_EMAIL.split(',')
            for email in audit_emails:
                success = self.email_service.send_email(
                    to_email=email.strip(),
                    subject="Test: Audit Alert Email Configuration",
                    template_name="email_verification.html",  # Use existing template
                    template_data={
                        "otp": "123456",
                        "verification_link": f"{settings.FRONTEND_URL}/test",
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    }
                )
                test_results[f"audit_alert_{email.strip()}"] = success

            # Test security alert email
            security_emails = settings.SECURITY_ALERT_EMAILS.split(',')
            for email in security_emails:
                success = self.email_service.send_email(
                    to_email=email.strip(),
                    subject="Test: Security Alert Email Configuration",
                    template_name="email_verification.html",
                    template_data={
                        "otp": "654321",
                        "verification_link": f"{settings.FRONTEND_URL}/test",
                        "frontend_url": settings.FRONTEND_URL,
                        "contact_email": settings.FROM_EMAIL
                    }
                )
                test_results[f"security_alert_{email.strip()}"] = success

            logger.info("Email configuration test completed")
            return test_results

        except Exception as e:
            logger.error(f"Email configuration test failed: {e}")
            return {"error": False}