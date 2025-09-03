# Staff Management - Design Document

## Overview
The Staff Management system provides comprehensive employee lifecycle management for domestic service providers, including hiring, training, scheduling, performance tracking, and compliance monitoring. It serves as the central hub for all staff-related operations and regulatory requirements.

## Architecture

### Database Schema

```sql
-- Staff/Employees
staff:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - employee_id: VARCHAR(50) UNIQUE
  - first_name: VARCHAR(100)
  - last_name: VARCHAR(100)
  - middle_name: VARCHAR(100)
  - preferred_name: VARCHAR(100)
  - email: VARCHAR(255) UNIQUE
  - phone: VARCHAR(20)
  - mobile_phone: VARCHAR(20)
  - date_of_birth: DATE
  - ssn_encrypted: VARCHAR(255)
  - address: TEXT
  - city: VARCHAR(100)
  - state: VARCHAR(50)
  - zip_code: VARCHAR(20)
  - hire_date: DATE
  - termination_date: DATE
  - employment_status: ENUM('active', 'inactive', 'terminated', 'on_leave', 'suspended')
  - department: VARCHAR(100)
  - job_title: VARCHAR(100)
  - supervisor_id: UUID (FK)
  - hourly_rate: DECIMAL(10,2)
  - salary: DECIMAL(12,2)
  - pay_type: ENUM('hourly', 'salary', 'contract')
  - fte_percentage: DECIMAL(5,2)
  - profile_picture_url: TEXT
  - notes: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP
  - created_by: UUID (FK)

-- Emergency Contacts
staff_emergency_contacts:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - contact_name: VARCHAR(255)
  - relationship: VARCHAR(100)
  - phone_primary: VARCHAR(20)
  - phone_secondary: VARCHAR(20)
  - email: VARCHAR(255)
  - address: TEXT
  - is_primary: BOOLEAN
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Background Checks
background_checks:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - check_type: ENUM('criminal', 'reference', 'education', 'employment', 'drug_screen', 'physical')
  - provider: VARCHAR(255)
  - requested_date: DATE
  - completed_date: DATE
  - expiry_date: DATE
  - status: ENUM('pending', 'in_progress', 'completed', 'failed', 'expired')
  - result: ENUM('clear', 'flag', 'fail')
  - notes: TEXT
  - document_url: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Certifications
staff_certifications:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - certification_type: VARCHAR(255)
  - certification_name: VARCHAR(255)
  - issuing_organization: VARCHAR(255)
  - certification_number: VARCHAR(100)
  - issue_date: DATE
  - expiry_date: DATE
  - renewal_required: BOOLEAN
  - renewal_period_months: INTEGER
  - status: ENUM('active', 'expired', 'pending_renewal', 'suspended')
  - document_url: TEXT
  - verification_url: TEXT
  - reminder_days_before: INTEGER
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Training Programs
training_programs:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - program_name: VARCHAR(255)
  - description: TEXT
  - category: VARCHAR(100)
  - is_mandatory: BOOLEAN
  - frequency_months: INTEGER
  - duration_hours: DECIMAL(5,2)
  - delivery_method: ENUM('online', 'classroom', 'on_job', 'blended')
  - prerequisites: JSONB
  - materials_url: TEXT
  - test_required: BOOLEAN
  - passing_score: DECIMAL(5,2)
  - is_active: BOOLEAN
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Training Records
training_records:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - training_program_id: UUID (FK)
  - enrollment_date: DATE
  - start_date: DATE
  - completion_date: DATE
  - due_date: DATE
  - status: ENUM('not_started', 'in_progress', 'completed', 'overdue', 'exempted')
  - score: DECIMAL(5,2)
  - attempts: INTEGER
  - instructor: VARCHAR(255)
  - location: VARCHAR(255)
  - notes: TEXT
  - certificate_url: TEXT
  - next_due_date: DATE
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Skills & Competencies
staff_skills:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - skill_name: VARCHAR(255)
  - skill_category: VARCHAR(100)
  - proficiency_level: ENUM('beginner', 'intermediate', 'advanced', 'expert')
  - validated: BOOLEAN
  - validated_by: UUID (FK)
  - validated_date: DATE
  - expiry_date: DATE
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Performance Reviews
performance_reviews:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - reviewer_id: UUID (FK)
  - review_period_start: DATE
  - review_period_end: DATE
  - review_type: ENUM('annual', 'probationary', '90_day', 'special')
  - overall_rating: DECIMAL(3,2)
  - goals_met: BOOLEAN
  - strengths: TEXT
  - areas_for_improvement: TEXT
  - goals_next_period: TEXT
  - development_plan: TEXT
  - employee_comments: TEXT
  - status: ENUM('draft', 'completed', 'acknowledged')
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP
  - acknowledged_date: TIMESTAMP

-- Disciplinary Actions
disciplinary_actions:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - action_type: ENUM('verbal_warning', 'written_warning', 'suspension', 'termination', 'coaching')
  - reason: TEXT
  - description: TEXT
  - action_date: DATE
  - issued_by: UUID (FK)
  - hr_reviewed: BOOLEAN
  - hr_reviewer: UUID (FK)
  - hr_review_date: DATE
  - employee_acknowledged: BOOLEAN
  - employee_ack_date: DATE
  - follow_up_required: BOOLEAN
  - follow_up_date: DATE
  - document_url: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Staff Assignments
staff_assignments:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - client_id: UUID (FK)
  - location_id: UUID (FK)
  - assignment_type: ENUM('primary', 'secondary', 'backup', 'relief')
  - start_date: DATE
  - end_date: DATE
  - is_active: BOOLEAN
  - notes: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Time Off Requests
time_off_requests:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - request_type: ENUM('vacation', 'sick', 'personal', 'bereavement', 'jury_duty', 'fmla')
  - start_date: DATE
  - end_date: DATE
  - total_hours: DECIMAL(5,2)
  - reason: TEXT
  - status: ENUM('pending', 'approved', 'denied', 'cancelled')
  - requested_date: TIMESTAMP
  - approved_by: UUID (FK)
  - approved_date: TIMESTAMP
  - denial_reason: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Payroll Information
staff_payroll:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - tax_id: VARCHAR(20)
  - bank_account_encrypted: VARCHAR(255)
  - routing_number_encrypted: VARCHAR(255)
  - direct_deposit: BOOLEAN
  - tax_withholdings: JSONB
  - deductions: JSONB
  - benefits: JSONB
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP
```

### API Endpoints

#### Staff Management
- `GET /api/v1/staff` - List all staff (paginated, filterable)
- `GET /api/v1/staff/{id}` - Get staff details
- `POST /api/v1/staff` - Create new staff member
- `PUT /api/v1/staff/{id}` - Update staff information
- `DELETE /api/v1/staff/{id}` - Deactivate staff
- `POST /api/v1/staff/{id}/terminate` - Terminate employment
- `POST /api/v1/staff/{id}/reactivate` - Reactivate staff
- `GET /api/v1/staff/{id}/profile` - Get complete staff profile

#### Emergency Contacts
- `GET /api/v1/staff/{id}/emergency-contacts` - List emergency contacts
- `POST /api/v1/staff/{id}/emergency-contacts` - Add contact
- `PUT /api/v1/staff/{id}/emergency-contacts/{contact_id}` - Update contact
- `DELETE /api/v1/staff/{id}/emergency-contacts/{contact_id}` - Remove contact

#### Background Checks
- `GET /api/v1/staff/{id}/background-checks` - List background checks
- `POST /api/v1/staff/{id}/background-checks` - Request background check
- `PUT /api/v1/background-checks/{id}` - Update check status
- `GET /api/v1/background-checks/expiring` - Get expiring checks

#### Certifications
- `GET /api/v1/staff/{id}/certifications` - List staff certifications
- `POST /api/v1/staff/{id}/certifications` - Add certification
- `PUT /api/v1/certifications/{id}` - Update certification
- `DELETE /api/v1/certifications/{id}` - Remove certification
- `GET /api/v1/certifications/expiring` - Get expiring certifications
- `POST /api/v1/certifications/{id}/renew` - Renew certification

#### Training Management
- `GET /api/v1/training/programs` - List training programs
- `POST /api/v1/training/programs` - Create training program
- `GET /api/v1/staff/{id}/training` - Get staff training records
- `POST /api/v1/staff/{id}/training/{program_id}/enroll` - Enroll in training
- `PUT /api/v1/training/records/{id}` - Update training record
- `POST /api/v1/training/records/{id}/complete` - Mark training complete
- `GET /api/v1/training/overdue` - Get overdue training

#### Skills & Competencies
- `GET /api/v1/staff/{id}/skills` - List staff skills
- `POST /api/v1/staff/{id}/skills` - Add skill
- `PUT /api/v1/staff/skills/{id}` - Update skill
- `POST /api/v1/staff/skills/{id}/validate` - Validate skill

#### Performance Management
- `GET /api/v1/staff/{id}/performance-reviews` - List reviews
- `POST /api/v1/staff/{id}/performance-reviews` - Create review
- `PUT /api/v1/performance-reviews/{id}` - Update review
- `POST /api/v1/performance-reviews/{id}/acknowledge` - Acknowledge review

#### Disciplinary Actions
- `GET /api/v1/staff/{id}/disciplinary-actions` - List actions
- `POST /api/v1/staff/{id}/disciplinary-actions` - Create action
- `PUT /api/v1/disciplinary-actions/{id}` - Update action

#### Assignments
- `GET /api/v1/staff/{id}/assignments` - List staff assignments
- `POST /api/v1/staff/{id}/assignments` - Create assignment
- `PUT /api/v1/assignments/{id}` - Update assignment
- `DELETE /api/v1/assignments/{id}` - Remove assignment

#### Time Off
- `GET /api/v1/staff/{id}/time-off` - List time off requests
- `POST /api/v1/staff/{id}/time-off` - Request time off
- `PUT /api/v1/time-off/{id}` - Update request
- `POST /api/v1/time-off/{id}/approve` - Approve request
- `POST /api/v1/time-off/{id}/deny` - Deny request

#### Payroll
- `GET /api/v1/staff/{id}/payroll` - Get payroll information
- `PUT /api/v1/staff/{id}/payroll` - Update payroll info

### Security & Compliance

#### Data Protection
- SSN and financial data encrypted at rest
- RBAC for sensitive information
- Audit trail for all changes
- Secure document storage

#### Employment Law Compliance
- EEOC compliance tracking
- FLSA overtime calculations
- FMLA tracking
- Workers compensation

#### Background Check Integration
- Third-party provider APIs
- Automated status updates
- Compliance reporting
- Document management

### Integration Points

#### HR Systems
- HRIS integration
- Payroll system sync
- Benefits administration
- Time tracking systems

#### Training Platforms
- LMS integration
- Compliance tracking
- Certificate management
- Progress monitoring

#### Scheduling System
- Staff availability
- Skill-based assignments
- Coverage requirements
- Overtime tracking

### Performance Optimization

#### Database
- Indexes on frequently queried fields
- Partitioning for large datasets
- Read replicas for reporting
- Connection pooling

#### Caching
- Staff profiles (5 minutes)
- Training programs (1 hour)
- Certification data (30 minutes)
- Performance metrics (15 minutes)

#### File Storage
- S3 for documents
- CloudFront for delivery
- Document compression
- Thumbnail generation

### Reporting Features

#### Standard Reports
- Staff roster
- Training compliance
- Certification status
- Performance summaries
- Time off calendars
- Payroll reports

#### Analytics
- Staff turnover rates
- Training completion rates
- Performance trends
- Compliance metrics
- Cost analysis

### Compliance Features

#### Audit Trail
- All staff data changes
- Training completions
- Performance reviews
- Disciplinary actions
- System access logs

#### Regulatory Compliance
- Background check requirements
- Training mandates
- Certification tracking
- Performance documentation
- Equal opportunity monitoring

### Mobile Features

#### Staff Self-Service
- Profile updates
- Time off requests
- Training access
- Schedule viewing
- Document access

#### Manager Tools
- Team overview
- Approval workflows
- Performance tracking
- Schedule management
- Communication tools

### Automation Features

#### Reminders & Alerts
- Certification expiry
- Training due dates
- Performance review dates
- Background check renewals
- Birthday notifications

#### Workflow Automation
- New hire onboarding
- Training assignments
- Document routing
- Approval processes
- Termination procedures

### Bulk Operations

#### Import/Export
- Staff data import
- Training records bulk update
- Certification uploads
- Performance data export
- Compliance reports