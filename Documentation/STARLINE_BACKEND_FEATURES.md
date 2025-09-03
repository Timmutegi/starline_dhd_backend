# Starline Backend - Comprehensive Feature Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [User Management & Authentication](#1-user-management--authentication)
3. [Client Management](#2-client-management)
4. [Staff Management](#3-staff-management)
5. [Scheduling & Calendar](#4-scheduling--calendar)
6. [Documentation & Forms](#5-documentation--forms)
7. [Billing & Invoicing](#6-billing--invoicing)
8. [Reporting & Analytics](#7-reporting--analytics)
9. [Compliance & Audit](#8-compliance--audit)
10. [Communication & Notifications](#9-communication--notifications)
11. [White Labeling](#10-white-labeling)
12. [File Management](#11-file-management)
13. [API Specifications](#api-specifications)
14. [Technology Stack](#technology-stack)

## System Overview

Starline is a comprehensive backend system designed for domestic service providers managing client care, documentation, billing, and compliance. Built with Python FastAPI, PostgreSQL, and AWS infrastructure, it provides a secure, scalable, and compliant platform supporting white-label deployments.

### Core Technology Stack
- **Backend**: Python 3.11+ with FastAPI
- **Database**: PostgreSQL 15+ with Redis for caching
- **Infrastructure**: AWS (EC2, RDS, S3, CloudFront, ElastiCache)
- **Email Service**: Resend for notifications
- **Authentication**: JWT with 2FA support
- **File Storage**: AWS S3 with CloudFront CDN

### Architecture Highlights
- Multi-tenant white-label ready
- HIPAA compliant design
- Event-driven microservices
- Real-time notifications
- Comprehensive audit trails

---

## 1. User Management & Authentication

### Core Features
- **Multi-tenant user management** with organization isolation
- **Role-based access control** (RBAC) with granular permissions
- **JWT authentication** with refresh tokens
- **Two-factor authentication** (TOTP-based)
- **Session management** with concurrent session limits
- **Password policies** with complexity requirements
- **Organization-specific branding** and configurations

### User Roles
```json
{
  "roles": {
    "super_admin": "Full system access across organizations",
    "organization_admin": "Manage organization users and settings", 
    "program_manager": "Manage programs and staff assignments",
    "support_staff": "Client care and documentation",
    "billing_admin": "Financial operations and billing",
    "auditor": "Read-only compliance access",
    "client": "Limited personal data access"
  }
}
```

### Key API Endpoints
```
POST /api/v1/auth/login              - User authentication
POST /api/v1/auth/logout             - Session termination
POST /api/v1/auth/refresh            - Token refresh
POST /api/v1/auth/forgot-password    - Password reset
POST /api/v1/auth/2fa/enable         - Enable 2FA
GET  /api/v1/users                   - List users (paginated)
POST /api/v1/users                   - Create user
GET  /api/v1/users/{id}              - Get user profile
PUT  /api/v1/users/{id}              - Update user
```

### Security Features
- Bcrypt password hashing (12 rounds)
- Account lockout after 5 failed attempts
- IP-based rate limiting
- Session timeout (configurable)
- Audit logging for all authentication events

---

## 2. Client Management

### Core Features
- **Comprehensive client profiles** with demographics and contacts
- **Care plan management** with goal tracking
- **Health records integration** with medication tracking
- **Insurance and authorization** management
- **Document storage** with version control
- **Client assignments** to staff and locations
- **Progress tracking** with outcome measurements

### Client Profile Structure
```json
{
  "client": {
    "personal_info": {
      "client_id": "CL-2024-001",
      "first_name": "John",
      "last_name": "Doe", 
      "date_of_birth": "1985-03-15",
      "ssn_encrypted": "***-**-1234",
      "preferred_name": "Johnny",
      "photo_url": "https://cdn.starline.com/photos/client-123.jpg"
    },
    "health_info": {
      "primary_diagnosis": "Developmental disability",
      "allergies": ["Penicillin", "Shellfish"],
      "medications": [
        {
          "name": "Lisinopril",
          "dosage": "10mg",
          "frequency": "Daily"
        }
      ]
    },
    "care_team": {
      "primary_staff": "user-456",
      "backup_staff": ["user-789"],
      "case_manager": "user-012"
    }
  }
}
```

### Key API Endpoints
```
GET  /api/v1/clients                 - List clients (paginated, filterable)
POST /api/v1/clients                 - Create client
GET  /api/v1/clients/{id}            - Get client details
PUT  /api/v1/clients/{id}            - Update client
GET  /api/v1/clients/{id}/timeline   - Activity timeline
GET  /api/v1/clients/{id}/care-plans - Care plans
GET  /api/v1/clients/{id}/medications- Medication list
GET  /api/v1/clients/{id}/documents  - Client documents
```

---

## 3. Staff Management

### Core Features
- **Employee lifecycle management** from hire to termination
- **Training and certification tracking** with expiry alerts
- **Performance review system** with goal setting
- **Background check management** with renewal tracking
- **Skills and competency assessment** with validation
- **Time off management** with approval workflows
- **Payroll integration** with hours tracking

### Staff Profile Structure
```json
{
  "staff": {
    "employee_info": {
      "employee_id": "EMP-001",
      "first_name": "Jane",
      "last_name": "Smith",
      "hire_date": "2023-01-15",
      "job_title": "Direct Support Professional",
      "department": "Residential Services",
      "status": "active"
    },
    "certifications": [
      {
        "name": "CPR Certification",
        "issuer": "American Red Cross",
        "issue_date": "2024-01-01",
        "expiry_date": "2025-01-01",
        "status": "active"
      }
    ],
    "assignments": [
      {
        "client_id": "CL-2024-001",
        "location_id": "LOC-001",
        "assignment_type": "primary"
      }
    ]
  }
}
```

### Key API Endpoints
```
GET  /api/v1/staff                   - List staff members
POST /api/v1/staff                   - Create staff member
GET  /api/v1/staff/{id}              - Get staff profile
PUT  /api/v1/staff/{id}              - Update staff
GET  /api/v1/staff/{id}/training     - Training records
GET  /api/v1/staff/{id}/certifications- Certifications
GET  /api/v1/staff/{id}/performance  - Performance reviews
POST /api/v1/staff/{id}/time-off     - Request time off
```

---

## 4. Scheduling & Calendar

### Core Features
- **Advanced shift scheduling** with auto-assignment
- **Staff availability management** with preferences
- **Appointment scheduling** with reminders
- **Time clock integration** with GPS verification
- **Overtime tracking** and compliance
- **Shift coverage requests** and swapping
- **Calendar integration** with external systems

### Scheduling Structure
```json
{
  "shift": {
    "shift_id": "SH-2024-001",
    "staff_id": "EMP-001",
    "location_id": "LOC-001",
    "shift_date": "2024-01-15",
    "start_time": "08:00:00",
    "end_time": "16:00:00",
    "break_duration": 30,
    "client_assignments": [
      {
        "client_id": "CL-2024-001",
        "services": ["Personal care", "Community activities"]
      }
    ],
    "status": "scheduled"
  }
}
```

### Key API Endpoints
```
GET  /api/v1/schedules               - List schedules
POST /api/v1/schedules               - Create schedule
GET  /api/v1/shifts                  - List shifts
POST /api/v1/shifts                  - Create shift
POST /api/v1/time-clock/clock-in     - Clock in
POST /api/v1/time-clock/clock-out    - Clock out
GET  /api/v1/appointments            - List appointments
POST /api/v1/appointments            - Schedule appointment
```

---

## 5. Documentation & Forms

### Core Features
- **Dynamic form builder** with drag-and-drop interface
- **Mobile-optimized forms** with offline capability
- **Electronic signatures** with legal compliance
- **Progress note templates** with structured data
- **Incident reporting** with photo attachments
- **Form versioning** and approval workflows
- **Auto-save functionality** with draft management

### Form Structure
```json
{
  "form_template": {
    "template_id": "FT-001",
    "name": "Daily Progress Note",
    "category": "Documentation",
    "fields": [
      {
        "field_id": "client_mood",
        "type": "select",
        "label": "Client Mood",
        "options": ["Happy", "Neutral", "Sad", "Anxious"],
        "required": true
      },
      {
        "field_id": "activities",
        "type": "checkbox",
        "label": "Activities Completed",
        "options": ["Personal Care", "Meals", "Recreation", "Community"]
      }
    ],
    "validation_rules": {
      "required_signatures": ["staff", "supervisor"]
    }
  }
}
```

### Key API Endpoints
```
GET  /api/v1/forms/templates         - List form templates
POST /api/v1/forms/templates         - Create template
GET  /api/v1/forms/submissions       - List submissions
POST /api/v1/forms/submissions       - Submit form
POST /api/v1/signatures              - Capture signature
GET  /api/v1/progress-notes          - List progress notes
POST /api/v1/progress-notes          - Create progress note
```

---

## 6. Billing & Invoicing

### Core Features
- **Service authorization tracking** with unit limits
- **Automated claim generation** (CMS-1500, UB-04)
- **Electronic claim submission** (837 EDI)
- **Payment reconciliation** with ERA processing
- **Multiple payer support** with different rate tables
- **Revenue reporting** and analytics
- **Aging reports** and collections management

### Billing Structure
```json
{
  "billable_service": {
    "service_id": "BS-2024-001",
    "client_id": "CL-2024-001",
    "staff_id": "EMP-001",
    "service_date": "2024-01-15",
    "service_code": "T2021",
    "units": 4.0,
    "rate": 25.50,
    "total_amount": 102.00,
    "authorization_id": "AUTH-12345",
    "payer": "Medicaid",
    "status": "billable"
  }
}
```

### Key API Endpoints
```
GET  /api/v1/billing/services        - List billable services
POST /api/v1/billing/services        - Create service entry
GET  /api/v1/billing/claims          - List claims
POST /api/v1/billing/claims/generate - Generate claims
GET  /api/v1/billing/payments        - Payment history
POST /api/v1/billing/reconcile       - Reconcile payments
```

---

## 7. Reporting & Analytics

### Core Features
- **Drag-and-drop report builder** with custom queries
- **Real-time dashboards** with KPI widgets
- **Scheduled report delivery** via email
- **Data visualization** with charts and graphs
- **Compliance reporting** templates
- **Performance analytics** with trend analysis
- **Predictive insights** using ML algorithms

### Dashboard Structure
```json
{
  "dashboard": {
    "widgets": [
      {
        "widget_id": "client-census",
        "type": "metric",
        "title": "Active Clients",
        "value": 150,
        "trend": "+5%"
      },
      {
        "widget_id": "service-hours",
        "type": "chart",
        "title": "Service Hours This Month",
        "chart_type": "line",
        "data": {
          "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
          "values": [320, 340, 358, 372]
        }
      }
    ]
  }
}
```

### Key API Endpoints
```
GET  /api/v1/reports/templates       - List report templates
POST /api/v1/reports/generate        - Generate report
GET  /api/v1/analytics/dashboard     - Dashboard data
GET  /api/v1/analytics/kpis          - KPI metrics
POST /api/v1/reports/schedule        - Schedule report
```

---

## 8. Compliance & Audit

### Core Features
- **Comprehensive audit trail** for all system activities
- **Real-time compliance monitoring** with violation detection
- **Risk assessment tools** with scoring
- **Regulatory reporting** (HIPAA, CMS, state requirements)
- **Policy enforcement** with automated checks
- **Corrective action tracking** with deadlines
- **Evidence management** for audits

### Audit Log Structure
```json
{
  "audit_log": {
    "log_id": "AL-2024-001",
    "user_id": "user-123",
    "action": "UPDATE_CLIENT_RECORD",
    "resource_type": "client",
    "resource_id": "CL-2024-001",
    "timestamp": "2024-01-15T14:30:00Z",
    "ip_address": "192.168.1.100",
    "changes": {
      "field": "emergency_contact_phone",
      "old_value": "555-0123",
      "new_value": "555-0124"
    },
    "success": true
  }
}
```

### Key API Endpoints
```
GET  /api/v1/audit/logs              - Get audit trail
GET  /api/v1/compliance/rules        - List compliance rules
GET  /api/v1/compliance/violations   - List violations
POST /api/v1/compliance/assess       - Run compliance check
GET  /api/v1/compliance/dashboard    - Compliance metrics
```

---

## 9. Communication & Notifications

### Core Features
- **Multi-channel notifications** (Email, SMS, Push, In-app)
- **Smart routing** based on urgency and preferences
- **Message templates** with variable substitution
- **Delivery tracking** and read receipts
- **Escalation workflows** for critical alerts
- **Group messaging** and broadcasts
- **Integration with Resend** for email delivery

### Notification Structure
```json
{
  "notification": {
    "notification_id": "NOT-2024-001",
    "user_id": "user-123",
    "type": "medication_reminder",
    "title": "Medication Due",
    "message": "Client John Doe has medication due at 2:00 PM",
    "priority": "high",
    "channels": ["email", "sms", "push"],
    "status": "delivered",
    "sent_at": "2024-01-15T13:45:00Z"
  }
}
```

### Key API Endpoints
```
POST /api/v1/notifications/send      - Send notification
GET  /api/v1/notifications           - List user notifications
PUT  /api/v1/notifications/{id}/read - Mark as read
GET  /api/v1/messages                - List messages
POST /api/v1/messages                - Send message
PUT  /api/v1/communication/preferences - Update preferences
```

---

## 10. White Labeling

### Core Features
- **Multi-tenant architecture** with complete data isolation
- **Custom branding** (logos, colors, fonts, themes)
- **Subdomain routing** (org1.starline.com)
- **Custom domain support** with SSL auto-provisioning
- **Organization-specific email templates**
- **Feature toggles** per organization
- **Billing isolation** and configuration

### Organization Structure
```json
{
  "organization": {
    "org_id": "ORG-001",
    "name": "Acme Healthcare Services",
    "subdomain": "acme",
    "custom_domain": "portal.acmehealthcare.com",
    "branding": {
      "logo_url": "https://cdn.starline.com/orgs/acme/logo.png",
      "primary_color": "#2563eb",
      "secondary_color": "#64748b",
      "font_family": "Inter"
    },
    "features": {
      "advanced_reporting": true,
      "mobile_app": true,
      "api_access": true
    }
  }
}
```

### Key API Endpoints
```
GET  /api/v1/organizations/{id}/branding - Get branding config
PUT  /api/v1/organizations/{id}/branding - Update branding
GET  /api/v1/organizations/{id}/themes   - List themes
POST /api/v1/organizations/{id}/themes   - Create theme
GET  /api/v1/organizations/{id}/features - Feature configuration
```

---

## 11. File Management

### Core Features
- **Secure file upload** to AWS S3 with encryption
- **Virus scanning** and malware detection
- **File versioning** with rollback capability
- **Role-based access permissions** with audit trails
- **CDN delivery** via CloudFront for global performance
- **Image optimization** and thumbnail generation
- **Bulk operations** for multiple files

### File Structure
```json
{
  "file": {
    "file_id": "FILE-2024-001",
    "original_filename": "care_plan_v2.pdf",
    "stored_filename": "encrypted_file_hash.pdf",
    "file_size": 2048576,
    "mime_type": "application/pdf",
    "uploaded_by": "user-123",
    "uploaded_at": "2024-01-15T10:30:00Z",
    "access_permissions": [
      {
        "user_id": "user-456",
        "permission": "read"
      }
    ],
    "is_encrypted": true
  }
}
```

### Key API Endpoints
```
POST /api/v1/files/upload            - Upload file
GET  /api/v1/files/{id}/download     - Download file
GET  /api/v1/files                   - List files
DELETE /api/v1/files/{id}            - Delete file
POST /api/v1/files/{id}/share        - Share file
GET  /api/v1/files/{id}/versions     - File versions
```

---

## API Specifications

### Base Configuration
```
Base URL: https://api.starline.com/v1
Authentication: Bearer JWT Token
Rate Limiting: 1000 requests/hour per user
Response Format: JSON with consistent error handling
```

### Standard Response Format
```json
{
  "success": true,
  "data": { 
    /* Response data */
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req-12345"
  },
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8
  }
}
```

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Valid email address required"
      }
    ]
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req-12345"
  }
}
```

---

## Technology Stack

### Backend Technologies
- **Runtime**: Python 3.11+
- **Framework**: FastAPI with Pydantic validation
- **Database**: PostgreSQL 15+ with SQLAlchemy ORM
- **Caching**: Redis 7+ for session and data caching
- **Task Queue**: Celery with Redis broker
- **Migration**: Alembic for database migrations

### Infrastructure & Deployment
- **Cloud Provider**: AWS
- **Compute**: EC2 instances with Docker containers
- **Database**: RDS PostgreSQL with automated backups
- **Caching**: ElastiCache Redis cluster
- **File Storage**: S3 with server-side encryption
- **CDN**: CloudFront for global content delivery
- **Load Balancing**: Application Load Balancer
- **Monitoring**: CloudWatch with custom metrics

### Security & Compliance
- **Authentication**: JWT with RS256 signing
- **Encryption**: AES-256 at rest, TLS 1.3 in transit
- **Secrets**: AWS Secrets Manager
- **Compliance**: HIPAA, SOC 2 Type II ready
- **Vulnerability Scanning**: Automated security scans
- **Access Control**: IAM roles and policies

### Development & Operations
- **Version Control**: Git with GitHub
- **CI/CD**: GitHub Actions with automated testing
- **Code Quality**: Black, flake8, mypy, pytest
- **Documentation**: Automatic OpenAPI generation
- **Error Tracking**: Sentry integration
- **Performance Monitoring**: APM tools integration

This comprehensive feature documentation provides the foundation for implementing a production-ready domestic service provider management system that rivals existing solutions while maintaining modern architecture and security standards.