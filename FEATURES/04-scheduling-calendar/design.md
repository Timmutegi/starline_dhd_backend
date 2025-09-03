# Scheduling & Calendar - Design Document

## Overview
The Scheduling & Calendar system provides comprehensive workforce management capabilities including shift scheduling, appointment management, resource allocation, and calendar integration. It optimizes staff coverage while ensuring client service requirements are met.

## Architecture

### Database Schema

```sql
-- Shift Templates
shift_templates:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - template_name: VARCHAR(255)
  - start_time: TIME
  - end_time: TIME
  - duration_minutes: INTEGER
  - break_duration_minutes: INTEGER
  - meal_break_minutes: INTEGER
  - days_of_week: INTEGER[] -- [1,2,3,4,5] for Mon-Fri
  - is_active: BOOLEAN
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Schedules
schedules:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - schedule_name: VARCHAR(255)
  - schedule_type: ENUM('weekly', 'monthly', 'custom')
  - start_date: DATE
  - end_date: DATE
  - status: ENUM('draft', 'published', 'locked', 'archived')
  - created_by: UUID (FK)
  - approved_by: UUID (FK)
  - approved_at: TIMESTAMP
  - notes: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Shifts
shifts:
  - id: UUID (PK)
  - schedule_id: UUID (FK)
  - staff_id: UUID (FK)
  - location_id: UUID (FK)
  - shift_date: DATE
  - start_time: TIME
  - end_time: TIME
  - break_start: TIME
  - break_end: TIME
  - meal_start: TIME
  - meal_end: TIME
  - status: ENUM('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show')
  - shift_type: ENUM('regular', 'overtime', 'holiday', 'on_call', 'split')
  - is_mandatory: BOOLEAN
  - notes: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Shift Assignments (Client-specific)
shift_assignments:
  - id: UUID (PK)
  - shift_id: UUID (FK)
  - client_id: UUID (FK)
  - assignment_type: ENUM('primary', 'backup', 'relief')
  - start_time: TIME
  - end_time: TIME
  - services_provided: JSONB
  - notes: TEXT
  - created_at: TIMESTAMP

-- Staff Availability
staff_availability:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - day_of_week: INTEGER -- 0=Sunday, 6=Saturday
  - start_time: TIME
  - end_time: TIME
  - availability_type: ENUM('available', 'preferred', 'unavailable')
  - effective_date: DATE
  - expiry_date: DATE
  - notes: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Time Off (affects scheduling)
time_off_scheduling:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - start_datetime: TIMESTAMP
  - end_datetime: TIMESTAMP
  - time_off_type: ENUM('vacation', 'sick', 'personal', 'bereavement', 'jury_duty', 'fmla')
  - status: ENUM('approved', 'pending', 'denied')
  - affects_scheduling: BOOLEAN
  - replacement_required: BOOLEAN
  - notes: TEXT

-- Shift Coverage Requests
coverage_requests:
  - id: UUID (PK)
  - original_shift_id: UUID (FK)
  - requesting_staff_id: UUID (FK)
  - reason: TEXT
  - request_type: ENUM('swap', 'pickup', 'drop')
  - status: ENUM('pending', 'approved', 'denied', 'cancelled')
  - requested_at: TIMESTAMP
  - responded_at: TIMESTAMP
  - responded_by: UUID (FK)
  - notes: TEXT

-- Shift Swaps
shift_swaps:
  - id: UUID (PK)
  - coverage_request_id: UUID (FK)
  - shift_a_id: UUID (FK)
  - shift_b_id: UUID (FK)
  - staff_a_id: UUID (FK)
  - staff_b_id: UUID (FK)
  - swap_date: DATE
  - status: ENUM('pending', 'approved', 'completed', 'cancelled')
  - approved_by: UUID (FK)
  - approved_at: TIMESTAMP

-- Appointments
appointments:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - client_id: UUID (FK)
  - staff_id: UUID (FK)
  - appointment_type: ENUM('medical', 'therapy', 'social', 'legal', 'family_visit', 'outing')
  - title: VARCHAR(255)
  - description: TEXT
  - location: TEXT
  - start_datetime: TIMESTAMP
  - end_datetime: TIMESTAMP
  - status: ENUM('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show')
  - requires_transport: BOOLEAN
  - transport_staff_id: UUID (FK)
  - reminder_sent: BOOLEAN
  - notes: TEXT
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Recurring Appointments
recurring_appointments:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - client_id: UUID (FK)
  - staff_id: UUID (FK)
  - appointment_type: VARCHAR(100)
  - title: VARCHAR(255)
  - description: TEXT
  - location: TEXT
  - start_time: TIME
  - duration_minutes: INTEGER
  - recurrence_pattern: ENUM('daily', 'weekly', 'monthly', 'custom')
  - recurrence_days: INTEGER[] -- for weekly: [1,3,5]
  - start_date: DATE
  - end_date: DATE
  - max_occurrences: INTEGER
  - is_active: BOOLEAN
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Time Clock
time_clock_entries:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - shift_id: UUID (FK)
  - entry_type: ENUM('clock_in', 'clock_out', 'break_start', 'break_end', 'meal_start', 'meal_end')
  - entry_datetime: TIMESTAMP
  - location_verified: BOOLEAN
  - geolocation: POINT
  - ip_address: VARCHAR(45)
  - device_info: JSONB
  - photo_url: TEXT
  - notes: TEXT
  - created_at: TIMESTAMP

-- Overtime Tracking
overtime_tracking:
  - id: UUID (PK)
  - staff_id: UUID (FK)
  - shift_id: UUID (FK)
  - week_start_date: DATE
  - regular_hours: DECIMAL(5,2)
  - overtime_hours: DECIMAL(5,2)
  - double_time_hours: DECIMAL(5,2)
  - holiday_hours: DECIMAL(5,2)
  - total_hours: DECIMAL(5,2)
  - approved: BOOLEAN
  - approved_by: UUID (FK)
  - approved_at: TIMESTAMP

-- Schedule Conflicts
schedule_conflicts:
  - id: UUID (PK)
  - conflict_type: ENUM('double_booking', 'overtime_violation', 'availability_conflict', 'skill_mismatch')
  - shift_id: UUID (FK)
  - staff_id: UUID (FK)
  - conflict_description: TEXT
  - severity: ENUM('low', 'medium', 'high', 'critical')
  - resolved: BOOLEAN
  - resolved_by: UUID (FK)
  - resolved_at: TIMESTAMP
  - resolution_notes: TEXT
  - created_at: TIMESTAMP

-- Calendar Events
calendar_events:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - event_type: ENUM('meeting', 'training', 'holiday', 'maintenance', 'inspection', 'other')
  - title: VARCHAR(255)
  - description: TEXT
  - start_datetime: TIMESTAMP
  - end_datetime: TIMESTAMP
  - location: TEXT
  - all_day: BOOLEAN
  - is_recurring: BOOLEAN
  - recurrence_rule: TEXT
  - attendees: UUID[] -- staff IDs
  - color: VARCHAR(7)
  - visibility: ENUM('public', 'private', 'confidential')
  - created_by: UUID (FK)
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP
```

### API Endpoints

#### Schedule Management
- `GET /api/v1/schedules` - List schedules
- `POST /api/v1/schedules` - Create schedule
- `GET /api/v1/schedules/{id}` - Get schedule details
- `PUT /api/v1/schedules/{id}` - Update schedule
- `DELETE /api/v1/schedules/{id}` - Delete schedule
- `POST /api/v1/schedules/{id}/publish` - Publish schedule
- `POST /api/v1/schedules/{id}/copy` - Copy schedule

#### Shift Management
- `GET /api/v1/shifts` - List shifts (with filters)
- `POST /api/v1/shifts` - Create shift
- `GET /api/v1/shifts/{id}` - Get shift details
- `PUT /api/v1/shifts/{id}` - Update shift
- `DELETE /api/v1/shifts/{id}` - Cancel shift
- `POST /api/v1/shifts/bulk` - Bulk create shifts
- `GET /api/v1/staff/{id}/shifts` - Get staff shifts

#### Shift Templates
- `GET /api/v1/shift-templates` - List templates
- `POST /api/v1/shift-templates` - Create template
- `PUT /api/v1/shift-templates/{id}` - Update template
- `DELETE /api/v1/shift-templates/{id}` - Delete template

#### Staff Availability
- `GET /api/v1/staff/{id}/availability` - Get availability
- `PUT /api/v1/staff/{id}/availability` - Update availability
- `POST /api/v1/staff/{id}/availability/bulk` - Bulk update

#### Coverage & Swaps
- `GET /api/v1/coverage-requests` - List coverage requests
- `POST /api/v1/coverage-requests` - Create request
- `PUT /api/v1/coverage-requests/{id}` - Update request
- `POST /api/v1/coverage-requests/{id}/approve` - Approve request
- `GET /api/v1/shift-swaps` - List shift swaps
- `POST /api/v1/shift-swaps` - Create swap

#### Appointments
- `GET /api/v1/appointments` - List appointments
- `POST /api/v1/appointments` - Create appointment
- `GET /api/v1/appointments/{id}` - Get appointment
- `PUT /api/v1/appointments/{id}` - Update appointment
- `DELETE /api/v1/appointments/{id}` - Cancel appointment
- `GET /api/v1/clients/{id}/appointments` - Client appointments

#### Recurring Appointments
- `GET /api/v1/recurring-appointments` - List recurring
- `POST /api/v1/recurring-appointments` - Create recurring
- `PUT /api/v1/recurring-appointments/{id}` - Update recurring
- `POST /api/v1/recurring-appointments/{id}/generate` - Generate instances

#### Time Clock
- `POST /api/v1/time-clock/clock-in` - Clock in
- `POST /api/v1/time-clock/clock-out` - Clock out
- `POST /api/v1/time-clock/break-start` - Start break
- `POST /api/v1/time-clock/break-end` - End break
- `GET /api/v1/staff/{id}/time-entries` - Get time entries
- `PUT /api/v1/time-entries/{id}` - Adjust time entry

#### Calendar Integration
- `GET /api/v1/calendar/events` - List calendar events
- `POST /api/v1/calendar/events` - Create event
- `GET /api/v1/calendar/{id}/view` - Get calendar view
- `POST /api/v1/calendar/sync` - Sync external calendar

#### Reporting
- `GET /api/v1/schedules/conflicts` - Get scheduling conflicts
- `GET /api/v1/overtime/report` - Overtime report
- `GET /api/v1/coverage/report` - Coverage analysis
- `GET /api/v1/attendance/report` - Attendance report

### Scheduling Algorithms

#### Auto-Scheduling Engine
```python
class SchedulingEngine:
    def generate_schedule(self, parameters):
        # Input: staff, clients, requirements, constraints
        # Output: optimized schedule
        
        constraints = [
            'staff_availability',
            'skill_requirements',
            'client_preferences',
            'labor_regulations',
            'budget_constraints'
        ]
        
        optimization_goals = [
            'minimize_overtime',
            'maximize_coverage',
            'balance_workload',
            'minimize_gaps'
        ]
```

#### Conflict Detection
```python
class ConflictDetector:
    def detect_conflicts(self, schedule):
        conflicts = []
        
        # Double booking detection
        # Overtime violation checks
        # Skill mismatch identification
        # Availability conflicts
        
        return conflicts
```

### Integration Points

#### External Calendar Systems
- Google Calendar integration
- Outlook calendar sync
- iCal export/import
- CalDAV protocol support

#### Time Tracking Systems
- Biometric time clocks
- Mobile app time tracking
- GPS verification
- Badge/card readers

#### Payroll Integration
- Hours calculation
- Overtime computation
- Holiday pay tracking
- Time-off deductions

### Performance Optimization

#### Database Optimization
- Indexed date ranges for quick queries
- Partitioned tables by date
- Materialized views for common reports
- Read replicas for reporting

#### Caching Strategy
- Schedule data (1 hour)
- Staff availability (30 minutes)
- Recurring patterns (24 hours)
- Calendar events (15 minutes)

#### Real-time Updates
- WebSocket connections for live updates
- Event-driven architecture
- Push notifications for changes
- Conflict detection in real-time

### Mobile Features

#### Staff Mobile App
- View personal schedule
- Clock in/out functionality
- Request coverage
- Swap shifts
- View appointments
- Update availability

#### Manager Mobile Tools
- Approve requests
- Monitor attendance
- Handle conflicts
- Emergency scheduling
- Real-time notifications

### Compliance Features

#### Labor Law Compliance
- FLSA overtime rules
- Break and meal requirements
- Maximum hours limits
- Rest period enforcement
- Holiday pay calculations

#### Regulatory Reporting
- Staff-to-client ratios
- Coverage requirements
- Training compliance
- Incident response times

### Automation Features

#### Smart Scheduling
- AI-powered optimization
- Pattern recognition
- Demand forecasting
- Automatic conflict resolution
- Intelligent shift suggestions

#### Notification System
- Schedule reminders
- Conflict alerts
- Coverage requests
- Appointment reminders
- Overtime warnings

### Advanced Features

#### Predictive Analytics
- Demand forecasting
- Staff utilization trends
- Overtime prediction
- Coverage gap analysis
- Cost optimization

#### Workforce Optimization
- Skill-based scheduling
- Workload balancing
- Travel time optimization
- Resource allocation
- Cost minimization

### Reporting & Analytics

#### Schedule Reports
- Staff utilization
- Coverage analysis
- Overtime summary
- Appointment statistics
- Conflict resolution

#### Performance Metrics
- Schedule adherence
- On-time performance
- Coverage rates
- Staff satisfaction
- Cost per hour

### Emergency Procedures

#### On-Call Management
- On-call scheduling
- Emergency notifications
- Response time tracking
- Escalation procedures
- Call-back protocols

#### Crisis Management
- Emergency coverage
- Rapid deployment
- Communication protocols
- Resource reallocation
- Incident coordination