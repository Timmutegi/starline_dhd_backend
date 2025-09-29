# Starline Backend Audit System Documentation

## Overview

The Starline Backend implements a comprehensive HIPAA-compliant audit logging system designed to track all user activities, monitor PHI access, detect security breaches, and maintain regulatory compliance. This system provides complete transparency and accountability for all actions performed within the healthcare management platform.

## Features

### 🔒 HIPAA Compliance
- **Complete Audit Trail**: Every action is logged with tamper-proof records
- **PHI Access Monitoring**: Special tracking for Protected Health Information
- **7+ Year Retention**: Meets HIPAA record retention requirements
- **Encrypted Storage**: All audit logs are encrypted at rest and in transit
- **Role-Based Access**: Audit logs are only accessible to authorized personnel

### 🚨 Security Monitoring
- **Real-time Breach Detection**: Automatic identification of suspicious activities
- **Failed Login Tracking**: Monitor and alert on repeated failed login attempts
- **After-hours Access Alerts**: Flag unusual access patterns
- **IP Address Monitoring**: Track access from different locations
- **Session Management**: Complete session lifecycle tracking

### 📊 Compliance Reporting
- **Automated Reports**: Weekly and monthly compliance summaries
- **Export Capabilities**: CSV, JSON, and PDF export options
- **Violation Management**: Track and resolve compliance violations
- **User Activity Reports**: Detailed activity tracking by user
- **PHI Access Reports**: Specialized reports for PHI data access

## Architecture

### Core Components

1. **Audit Models** (`app/models/audit_log.py`)
   - `AuditLog`: Main audit log table
   - `AuditSetting`: Organization-specific audit configurations
   - `AuditExport`: Track audit log exports
   - `ComplianceViolation`: Manage compliance violations

2. **Audit Service** (`app/services/audit_service.py`)
   - Centralized audit logging service
   - Automatic compliance monitoring
   - Breach detection and alerting
   - Report generation

3. **Audit Middleware** (`app/middleware/audit_middleware.py`)
   - Automatic request/response logging
   - Performance monitoring
   - Error tracking
   - User context extraction

4. **Audit Mixins** (`app/core/audit_mixins.py`)
   - Model-level audit triggers
   - PHI data classification
   - Automatic change tracking

5. **Audit API** (`app/api/v1/audit.py`)
   - RESTful audit log access
   - Compliance reporting endpoints
   - Export functionality
   - Settings management

## Data Classification

The system automatically classifies data based on sensitivity:

- **PHI**: Protected Health Information (medical records, vitals, etc.)
- **PII**: Personally Identifiable Information (names, addresses, etc.)
- **Financial**: Billing and payment information
- **Administrative**: System configuration and user management
- **General**: Non-sensitive system data

## API Endpoints

### Audit Log Management
- `GET /api/v1/audit/logs` - Retrieve audit logs with filtering
- `GET /api/v1/audit/logs/{log_id}` - Get specific audit log
- `GET /api/v1/audit/user/{user_id}/activity` - User activity history
- `GET /api/v1/audit/resource/{type}/{id}/history` - Resource change history

### PHI Access Monitoring
- `GET /api/v1/audit/phi-access` - PHI access logs
- `POST /api/v1/audit/phi-access` - Log PHI access manually

### Compliance Reporting
- `GET /api/v1/audit/compliance/report` - Generate compliance reports
- `GET /api/v1/audit/violations` - List compliance violations
- `PATCH /api/v1/audit/violations/{id}/acknowledge` - Acknowledge violations

### Settings & Export
- `GET /api/v1/audit/settings` - Get audit settings
- `PUT /api/v1/audit/settings` - Update audit settings
- `POST /api/v1/audit/export` - Export audit logs
- `GET /api/v1/audit/export/{id}/download` - Download exports

## Configuration

### Audit Settings

Organizations can configure audit behavior through the `AuditSetting` model:

```python
{
    "retention_days": 2555,  # 7 years for HIPAA
    "archive_after_days": 90,
    "enable_async_logging": True,
    "batch_size": 100,
    "sampling_rate": 100,  # 100% = log everything
    "alert_on_phi_access": True,
    "alert_on_breach": True,
    "alert_on_failed_login": True,
    "alert_email_addresses": ["admin@example.com"],
    "require_consent_verification": True,
    "mask_sensitive_data": True,
    "enable_integrity_check": True,
    "log_read_operations": True,
    "log_administrative_actions": True,
    "log_api_responses": False
}
```

### Environment Variables

Add to your `.env` file:
```bash
# Audit settings
AUDIT_LOG_LEVEL=INFO
AUDIT_ASYNC_LOGGING=true
AUDIT_RETENTION_DAYS=2555
```

## Model Integration

### Adding Audit to Models

For PHI data models:
```python
from app.core.audit_mixins import PHIAuditMixin

class VitalsLog(PHIAuditMixin, Base):
    __tablename__ = "vitals_logs"

    # Audit configuration
    __audit_resource_type__ = "vitals"
    __audit_phi_fields__ = ["temperature", "blood_pressure", "notes"]
    __audit_exclude_fields__ = ["created_at", "updated_at"]

    # ... model fields
```

For regular data models:
```python
from app.core.audit_mixins import AuditMixin

class User(AuditMixin, Base):
    __tablename__ = "users"

    # Audit configuration
    __audit_resource_type__ = "user"
    __audit_phi_fields__ = ["email", "phone_number"]
    __audit_exclude_fields__ = ["password_hash", "created_at", "updated_at"]

    # ... model fields
```

### Manual PHI Access Logging

For read operations:
```python
from app.core.audit_mixins import log_phi_access

# When accessing PHI data
client = db.query(Client).filter(Client.id == client_id).first()
log_phi_access(client, user_id="user123", purpose="Care planning review")
```

## Email Notifications

The system includes HIPAA-compliant email templates:

1. **Security Breach Alert** (`security_breach_alert.html`)
   - Immediate notification of security violations
   - Detailed breach information
   - Required actions and recommendations

2. **PHI Access Alert** (`phi_access_alert.html`)
   - Notification of PHI data access
   - User and purpose tracking
   - Consent verification status

3. **Failed Login Alert** (`failed_login_alert.html`)
   - Multiple failed login attempt warnings
   - IP address and location tracking
   - Account lockout notifications

4. **Compliance Summary** (`compliance_summary.html`)
   - Weekly compliance reports
   - Activity summaries and metrics
   - Violation status updates

## Compliance Features

### HIPAA Requirements Met

✅ **Administrative Safeguards**
- Access management and authorization
- Information system activity review
- Security awareness and training tracking

✅ **Physical Safeguards**
- Facility access controls (through IP monitoring)
- Workstation use monitoring
- Device and media controls

✅ **Technical Safeguards**
- Access control and unique user identification
- Audit controls and integrity
- Person or entity authentication
- Transmission security

### Regulatory Compliance

- **HIPAA**: Complete audit trail for PHI access
- **SOX**: Financial data access tracking
- **GDPR**: User consent and data access logging
- **State Regulations**: Customizable compliance rules

## Security Features

### Tamper-Proof Logs
- Cryptographic checksums for log integrity
- Immutable audit trail
- Detection of unauthorized modifications

### Access Controls
- Role-based access to audit logs
- Principle of least privilege
- Multi-factor authentication support

### Data Protection
- Encryption at rest and in transit
- Secure API endpoints
- Rate limiting and DDoS protection

## Performance Considerations

### Optimization Strategies
- **Asynchronous Logging**: Non-blocking audit operations
- **Batch Processing**: Efficient bulk operations
- **Database Partitioning**: Monthly table partitioning
- **Archival System**: Automatic old data archiving
- **Caching**: Redis caching for frequent queries

### Monitoring
- Performance metrics tracking
- Alert system for performance degradation
- Automated health checks
- Resource usage monitoring

## Troubleshooting

### Common Issues

1. **High Database Load**
   - Enable async logging
   - Increase batch size
   - Implement sampling for high-volume operations

2. **Storage Space**
   - Configure automatic archiving
   - Set appropriate retention periods
   - Monitor disk usage regularly

3. **Performance Impact**
   - Use database indexes effectively
   - Optimize audit queries
   - Consider read replicas for reporting

### Debug Mode

Enable detailed audit logging:
```python
import logging
logging.getLogger('app.services.audit_service').setLevel(logging.DEBUG)
```

## Testing

### Running Tests

```bash
# Test with Docker (recommended)
./deploy.sh dev --build

# Check health
curl http://localhost:8000/health

# Test audit endpoints (requires authentication)
curl http://localhost:8000/api/v1/audit/logs
```

### Integration Testing

The audit system is automatically tested when you:
1. Make any API calls (middleware testing)
2. Create/update models (trigger testing)
3. Access PHI data (compliance testing)

## Maintenance

### Regular Tasks

1. **Weekly**: Review compliance violations
2. **Monthly**: Generate compliance reports
3. **Quarterly**: Test backup and recovery
4. **Annually**: Security audit and penetration testing

### Database Maintenance

```sql
-- Check audit log volume
SELECT COUNT(*) FROM audit_logs;

-- Archive old logs (example)
INSERT INTO audit_logs_archive
SELECT * FROM audit_logs
WHERE created_at < NOW() - INTERVAL '1 year';

-- Clean up violations
DELETE FROM compliance_violations
WHERE status = 'resolved' AND resolved_at < NOW() - INTERVAL '6 months';
```

## Support

For issues with the audit system:

1. Check application logs: `docker compose logs backend`
2. Review audit settings in the admin panel
3. Contact the development team with specific error messages
4. Include audit log IDs when reporting issues

## Best Practices

### For Developers
- Always use audit mixins for sensitive models
- Log PHI access manually for read operations
- Handle audit failures gracefully
- Test audit functionality thoroughly

### For Administrators
- Monitor compliance dashboards regularly
- Set up email alerts for security events
- Review user access patterns monthly
- Maintain proper backup procedures

### For Compliance Officers
- Generate regular compliance reports
- Investigate violations promptly
- Document resolution procedures
- Maintain audit trail documentation

## Conclusion

The Starline audit system provides comprehensive HIPAA-compliant logging and monitoring capabilities essential for healthcare applications. It ensures data security, regulatory compliance, and provides the transparency required for healthcare operations while maintaining system performance and usability.