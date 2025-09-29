# Email Alert Configuration for Starline Audit System

## Overview

This document describes the email alert configuration for the Starline audit system. All security alerts, PHI access notifications, and compliance reports are now configured to be sent to **mamafairapp@gmail.com**.

## Environment Variables

The following environment variables have been added to the `.env` file:

```bash
# Audit & Security Alert Settings
AUDIT_ALERT_EMAIL=mamafairapp@gmail.com
SECURITY_ALERT_EMAILS=mamafairapp@gmail.com
COMPLIANCE_REPORT_EMAILS=mamafairapp@gmail.com
```

### Variable Descriptions

- **AUDIT_ALERT_EMAIL**: Primary email for audit-related notifications (PHI access, compliance events)
- **SECURITY_ALERT_EMAILS**: Email(s) for security alerts (breach attempts, failed logins, account lockouts)
- **COMPLIANCE_REPORT_EMAILS**: Email(s) for weekly/monthly compliance summary reports

**Note**: You can specify multiple email addresses by separating them with commas:
```bash
SECURITY_ALERT_EMAILS=mamafairapp@gmail.com,admin@starline.com,security@starline.com
```

## Email Alert Types

### 1. PHI Access Notifications
**Trigger**: When Protected Health Information is accessed
**Recipients**: `AUDIT_ALERT_EMAIL`
**Template**: `phi_access_alert.html`
**Contents**:
- Client information
- Data type accessed
- User details and role
- Access time and purpose
- IP address and session info
- Consent verification status

### 2. Security Breach Alerts
**Trigger**: When security violations are detected
**Recipients**: `SECURITY_ALERT_EMAILS`
**Template**: `security_breach_alert.html`
**Contents**:
- Violation type and severity
- Affected resource details
- User and IP information
- Immediate actions taken
- Investigation links

### 3. Failed Login Alerts
**Trigger**: Multiple failed login attempts detected
**Recipients**: `SECURITY_ALERT_EMAILS`
**Template**: `failed_login_alert.html`
**Contents**:
- Target account information
- Number of failed attempts
- IP address and location
- Account lockout status
- Recommended actions

### 4. Weekly Compliance Summary
**Trigger**: Scheduled weekly reports
**Recipients**: `COMPLIANCE_REPORT_EMAILS`
**Template**: `compliance_summary.html`
**Contents**:
- System activity overview
- PHI access statistics
- Compliance violations summary
- User activity metrics
- Action items and recommendations

## Configuration Files Updated

### 1. Environment Configuration (`.env`)
```bash
# New variables added:
AUDIT_ALERT_EMAIL=mamafairapp@gmail.com
SECURITY_ALERT_EMAILS=mamafairapp@gmail.com
COMPLIANCE_REPORT_EMAILS=mamafairapp@gmail.com
```

### 2. Settings Configuration (`app/core/config.py`)
```python
# New settings added:
AUDIT_ALERT_EMAIL: str = os.getenv("AUDIT_ALERT_EMAIL", "support@starline.com")
SECURITY_ALERT_EMAILS: str = os.getenv("SECURITY_ALERT_EMAILS", "support@starline.com")
COMPLIANCE_REPORT_EMAILS: str = os.getenv("COMPLIANCE_REPORT_EMAILS", "support@starline.com")
```

### 3. Database Initialization (`app/init_db.py`)
- Updated default audit settings to use `settings.AUDIT_ALERT_EMAIL`
- New organizations will automatically use the configured email for alerts

### 4. Audit Service (`app/services/audit_service.py`)
- Enhanced alert methods to use configured email addresses
- Improved error handling for email sending failures
- Added template data for better email content

## New Compliance Email Service

Created `app/services/compliance_email_service.py` with the following features:

### Methods Available:
- `send_weekly_compliance_summary()`: Weekly compliance reports
- `send_phi_access_notification()`: PHI access alerts
- `send_security_breach_alert()`: Security breach notifications
- `send_failed_login_alert()`: Failed login attempt alerts
- `send_account_lockout_notification()`: Account lockout notifications
- `test_email_configuration()`: Test email setup
- `get_configured_alert_emails()`: Get all configured emails

### Usage Example:
```python
from app.services.compliance_email_service import ComplianceEmailService

email_service = ComplianceEmailService()

# Send a test email
results = email_service.test_email_configuration()

# Send compliance summary
email_service.send_weekly_compliance_summary(
    organization_name="Starline Healthcare",
    summary_data={
        "total_activities": 1250,
        "phi_accesses": 45,
        "violations_count": 2
    }
)
```

## Testing Email Configuration

### 1. Manual Testing
You can test the email configuration using the compliance email service:

```python
# In Django shell or test script
from app.services.compliance_email_service import ComplianceEmailService

service = ComplianceEmailService()
test_results = service.test_email_configuration()
print(test_results)
```

### 2. API Testing
Use the audit endpoints to trigger alerts:
- Access PHI data → PHI access alert
- Multiple failed logins → Failed login alert
- Security violations → Breach alert

### 3. Configuration Verification
Check current email configuration:
```python
service = ComplianceEmailService()
emails = service.get_configured_alert_emails()
print(emails)
```

## Email Templates

All email templates are located in `app/emails/templates/` and follow the Starline branding:

- **security_breach_alert.html**: Red alert theme for security breaches
- **phi_access_alert.html**: Green theme for PHI access notifications
- **failed_login_alert.html**: Orange theme for login security alerts
- **compliance_summary.html**: Blue theme for compliance reports

### Template Features:
- Responsive design for mobile and desktop
- Professional Starline branding
- Clear action buttons and links
- Comprehensive information display
- HIPAA-compliant content structure

## Security Considerations

### 1. Email Security
- All emails are sent via encrypted SMTP (Resend service)
- No sensitive data (passwords, SSNs) included in email content
- Links point to secure authenticated areas
- Email addresses are validated before sending

### 2. Content Security
- PHI data is minimized in email content
- User identifiers used instead of full personal information
- Links require authentication to access full details
- Audit trail maintained for all email notifications

### 3. Privacy Compliance
- Email content complies with HIPAA requirements
- Minimal necessary information principle applied
- Secure delivery mechanisms used
- Recipient verification recommended

## Troubleshooting

### Common Issues:

1. **Emails Not Received**
   - Check spam/junk folders
   - Verify email address spelling in `.env`
   - Check Resend API key configuration
   - Review backend logs for email sending errors

2. **Template Errors**
   - Ensure all email templates exist in `app/emails/templates/`
   - Check template variable names match service calls
   - Verify template syntax is valid HTML

3. **Configuration Issues**
   - Restart backend after `.env` changes
   - Verify environment variables are loaded correctly
   - Check settings import in audit service

### Debug Commands:

```bash
# Check backend logs for email errors
docker compose -f docker-compose-dev.yml logs backend | grep -i email

# Test email service directly
docker compose -f docker-compose-dev.yml exec backend python -c "
from app.services.compliance_email_service import ComplianceEmailService
service = ComplianceEmailService()
print(service.test_email_configuration())
"

# Verify environment variables
docker compose -f docker-compose-dev.yml exec backend python -c "
from app.core.config import settings
print(f'Audit Email: {settings.AUDIT_ALERT_EMAIL}')
print(f'Security Emails: {settings.SECURITY_ALERT_EMAILS}')
print(f'Compliance Emails: {settings.COMPLIANCE_REPORT_EMAILS}')
"
```

## Maintenance

### Regular Tasks:
1. **Weekly**: Verify compliance summary emails are received
2. **Monthly**: Review email delivery logs
3. **Quarterly**: Test all alert types manually
4. **Annually**: Update email templates and review recipients

### Email Address Updates:
To change email recipients:
1. Update the `.env` file
2. Restart the backend service
3. Update audit settings in the database if needed
4. Test the new configuration

## Next Steps

1. **Set up email filtering**: Create rules in mamafairapp@gmail.com to organize Starline alerts
2. **Monitor email delivery**: Set up delivery confirmations and bounce handling
3. **Create email distribution lists**: For multiple recipients per alert type
4. **Implement email scheduling**: For non-urgent compliance reports
5. **Add email analytics**: Track open rates and engagement with alerts

The email alert system is now fully configured and operational. All audit events, security alerts, and compliance notifications will be sent to **mamafairapp@gmail.com** as specified.