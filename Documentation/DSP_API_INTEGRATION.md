# DSP (Direct Support Professional) API Integration Guide

## Overview

This document provides comprehensive API integration guidance for the Direct Support Professional (DSP) UI based on the Figma designs. All endpoints require authentication using Bearer tokens obtained from the login endpoint.

## Table of Contents

1. [Authentication](#authentication)
2. [Base URLs & Headers](#base-urls--headers)
3. [UI Screen to Endpoint Mapping](#ui-screen-to-endpoint-mapping)
4. [Endpoint Reference](#endpoint-reference)
5. [Common Schemas](#common-schemas)
6. [Error Handling](#error-handling)
7. [Testing](#testing)

---

## Authentication

### Login
**POST** `/api/v1/auth/login`

```json
{
  "email": "tim@kaziflex.com",
  "password": "**********"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "tim@kaziflex.com",
    "first_name": "Timothy",
    "last_name": "Williams",
    "role": {
      "name": "Support Staff",
      "permissions": [...]
    }
  }
}
```

**Important:** Store the `access_token` securely and include it in all subsequent requests.

---

## Base URLs & Headers

### Base URL
- **Development:** `http://localhost:8000/api/v1`
- **Production:** `https://api.starline.com/api/v1`

### Required Headers
```http
Authorization: Bearer {access_token}
Content-Type: application/json
```

---

## UI Screen to Endpoint Mapping

### 1. Home Dashboard (Page 0)
**Purpose:** Overview of DSP's daily activities

| UI Element | Endpoint | Method | Notes |
|------------|----------|--------|-------|
| Dashboard Overview | `/dashboard/overview` | GET | Returns stats, notifications, quick actions |
| Clients Assigned Today | `/dashboard/clients-assigned` | GET | Filter by date (default: today) |
| Tasks Summary | `/dashboard/tasks-summary` | GET | Task statistics |
| Quick Actions | `/dashboard/quick-actions` | GET | Available actions for DSP |
| Notifications Badge | `/notifications?is_read=false` | GET | Unread notifications count |

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/overview" \
  -H "Authorization: Bearer {token}"
```

**Response:**
```json
{
  "user_name": "Timothy Williams",
  "organization_name": "Kaziflex Care",
  "quick_stats": {
    "clients_assigned_today": 3,
    "tasks_completed": 5,
    "incidents_reported": 1,
    "appointments_today": 2
  },
  "recent_activity": {
    "items": [...]
  },
  "current_date": "2025-10-02"
}
```

---

### 2. Clients Assigned Today (Page 1)
**Purpose:** List of clients assigned to DSP for the selected date

| UI Element | Endpoint | Method | Notes |
|------------|----------|--------|-------|
| Client List | `/dashboard/clients-assigned?date_filter=2025-10-02` | GET | Filter by date |
| Client Card | `/clients/{client_id}` | GET | Individual client details |
| Time In/Out | `/scheduling/time-clock/clock-in` | POST | Clock in for shift |
| | `/scheduling/time-clock/clock-out` | POST | Clock out from shift |

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/clients-assigned?date_filter=2025-10-02" \
  -H "Authorization: Bearer {token}"
```

**Response:**
```json
[
  {
    "client_id": "uuid",
    "client_name": "Cynthia Wanza",
    "client_code": "CL12345",
    "location": "123 Main St, Apartment 4B",
    "shift_time": "08:00 - 16:00",
    "status": "scheduled",
    "time_in": null,
    "time_out": null
  }
]
```

---

### 3. Tasks Management (Page 2)
**Purpose:** View and manage assigned tasks

| UI Element | Endpoint | Method | Notes |
|------------|----------|--------|-------|
| Task List (All) | `/tasks?assigned_to={staff_id}` | GET | All tasks for DSP |
| Task List (Overdue) | `/tasks?assigned_to={staff_id}&overdue_only=true` | GET | Overdue tasks only |
| Task Details | `/tasks/{task_id}` | GET | Single task details |
| Create Task | `/tasks` | POST | Create new task |
| Update Task | `/tasks/{task_id}` | PUT | Update task status/details |
| Task Summary Stats | `/tasks/summary/stats?assigned_to={staff_id}` | GET | Task statistics |

**Example - Get Tasks:**
```bash
curl -X GET "http://localhost:8000/api/v1/tasks?assigned_to={staff_id}&status=pending" \
  -H "Authorization: Bearer {token}"
```

**Example - Update Task:**
```bash
curl -X PUT "http://localhost:8000/api/v1/tasks/{task_id}" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "notes": "Task completed successfully"
  }'
```

---

### 4. Incident Reports (Page 3)
**Purpose:** View and create incident reports

| UI Element | Endpoint | Method | Notes |
|------------|----------|--------|-------|
| Incident List | `/documentation/incidents` | GET | All incidents |
| Incident Details | `/documentation/incidents/{incident_id}` | GET | Single incident |
| Create Incident | `/documentation/incidents` | POST | With file upload support |
| Download Attachment | `/documentation/incidents/{incident_id}/files/{file_id}` | GET | Download file |

**Example - Create Incident:**
```bash
curl -X POST "http://localhost:8000/api/v1/documentation/incidents" \
  -H "Authorization: Bearer {token}" \
  -F "client_id=uuid" \
  -F "incident_type=fall" \
  -F "description=Client tripped on carpet" \
  -F "action_taken=Assisted client, checked for injuries" \
  -F "severity=medium" \
  -F "incident_date=2025-10-02" \
  -F "incident_time=14:30" \
  -F "location=Living room" \
  -F "follow_up_required=true" \
  -F "files=@incident_photo.jpg"
```

---

### 5. Appointments Today (Page 4)
**Purpose:** View daily appointment schedule

| UI Element | Endpoint | Method | Notes |
|------------|----------|--------|-------|
| Appointments List | `/scheduling/appointments?date={date}` | GET | Filter by date |
| Appointment Details | `/scheduling/appointments/{appointment_id}` | GET | Single appointment |
| Update Appointment | `/scheduling/appointments/{appointment_id}` | PUT | Update status |

---

### 6. Add Vitals Log (Page 5)
**Purpose:** Record client vitals (BP, glucose, temp, etc.)

**Endpoint:** `/documentation/vitals`
**Method:** POST

**Request Body:**
```json
{
  "client_id": "uuid",
  "temperature": 98.6,
  "blood_pressure_systolic": 120,
  "blood_pressure_diastolic": 80,
  "blood_sugar": 95.0,
  "weight": 165.5,
  "heart_rate": 72,
  "oxygen_saturation": 98.0,
  "notes": "All vitals within normal range",
  "recorded_at": "2025-10-02T08:30:00Z"
}
```

**Validation:**
- Diastolic must be less than systolic
- Temperature: 90-110°F
- BP Systolic: 60-300 mmHg
- BP Diastolic: 40-200 mmHg
- O2 Saturation: 0-100%

---

### 7. Add Shift Note (Page 6)
**Purpose:** Document shift narratives and observations

**Endpoint:** `/documentation/shift-notes`
**Method:** POST

**Request Body:**
```json
{
  "client_id": "uuid",
  "shift_date": "2025-10-02",
  "shift_time": "8:00 AM - 4:00 PM",
  "narrative": "Client was cooperative throughout the shift...",
  "challenges_faced": "Some difficulty with medication compliance",
  "support_required": "Reminders for medication schedule",
  "observations": "Overall good mood and engagement"
}
```

---

### 8. Upload Incident Photo (Page 7)
**Purpose:** Attach photos to incident reports

Handled in the incident creation endpoint (see Page 3).
Use `multipart/form-data` encoding with `files` parameter.

---

### 9. Record Meal Intake (Page 8)
**Purpose:** Log meals and nutritional intake

**Endpoint:** `/documentation/meals`
**Method:** POST

**Request Body:**
```json
{
  "client_id": "uuid",
  "meal_type": "breakfast",
  "meal_date": "2025-10-02T08:00:00Z",
  "meal_time": "08:00 AM",
  "food_items": ["Oatmeal", "Orange juice", "Toast"],
  "intake_amount": "most",
  "percentage_consumed": 80,
  "calories": 450,
  "water_intake_ml": 240,
  "appetite_level": "good",
  "dietary_preferences_followed": true,
  "dietary_restrictions_followed": true,
  "assistance_required": false,
  "notes": "Client enjoyed breakfast"
}
```

**Meal Types:** `breakfast`, `lunch`, `dinner`, `snack`
**Intake Amounts:** `none`, `minimal`, `partial`, `most`, `all`

---

### 10. View Full Schedule (Page 9)
**Purpose:** Weekly calendar view of shifts

| UI Element | Endpoint | Method | Notes |
|------------|----------|--------|-------|
| Weekly Schedule | `/scheduling/calendar?start_date={date}&end_date={date}` | GET | Get shifts for date range |
| Shift Details | `/scheduling/shifts/{shift_id}` | GET | Individual shift |
| Available Shifts | `/scheduling/shifts?status=open` | GET | Open shifts for pickup |

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/scheduling/calendar?start_date=2025-10-01&end_date=2025-10-07" \
  -H "Authorization: Bearer {token}"
```

---

### 11. My Clients (Page 10)
**Purpose:** View all assigned clients organized by location

**Endpoint:** `/clients?staff_id={current_user_id}&status=active`
**Method:** GET

**Query Parameters:**
- `search` - Search by name or client ID
- `location_id` - Filter by location
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 20)

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "client_id": "CL12345",
      "full_name": "Cynthia Wanza",
      "email": "cynthia@example.com",
      "date_of_birth": "1985-05-15",
      "status": "active",
      "photo_url": "https://...",
      "primary_diagnosis": "...",
      "location": "Apartment 4B"
    }
  ],
  "pagination": {
    "total": 10,
    "page": 1,
    "page_size": 20,
    "pages": 1
  }
}
```

---

### 12. Client Detail View (Page 11)
**Purpose:** Comprehensive client information dashboard

| Section | Endpoint | Method | Notes |
|---------|----------|--------|-------|
| Client Info | `/clients/{client_id}` | GET | Full client profile |
| Recent Vitals | `/documentation/vitals?client_id={id}&limit=5` | GET | Last 5 vitals |
| Recent Meals | `/documentation/meals?client_id={id}&limit=5` | GET | Last 5 meals |
| Recent Incidents | `/documentation/incidents?client_id={id}&limit=5` | GET | Recent incidents |
| Recent Activities | `/documentation/activities?client_id={id}&limit=5` | GET | Recent activities |
| Shift Notes | `/documentation/shift-notes?client_id={id}` | GET | Shift notes |
| Care Plans | Included in client details | - | Part of client response |
| Medications | Included in client details | - | Part of client response |
| Contacts | `/clients/{client_id}/contacts` | GET | Emergency contacts |

**Example - Client Details:**
```bash
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}" \
  -H "Authorization: Bearer {token}"
```

**Response includes:**
- Personal information
- Medical information (diagnosis, allergies)
- Care plans
- Medications
- Dietary restrictions
- Emergency contacts
- Assignments

---

### 13-15. Documentation Forms (Pages 12-14)
**Purpose:** Various documentation entry forms

All use the documentation endpoints:
- `/documentation/vitals` - Health metrics
- `/documentation/shift-notes` - Shift narratives
- `/documentation/incidents` - Incident reports
- `/documentation/meals` - Meal logs
- `/documentation/activities` - Activity logs

---

### 16-19. Health & Vitals, Meals, Activities (Pages 15-18)
**Purpose:** Specialized logging interfaces

| Category | Endpoint | Method | Notes |
|----------|----------|--------|-------|
| Vitals Log | `/documentation/vitals` | POST | Blood pressure, glucose, temp |
| Meal Log | `/documentation/meals` | POST | Nutrition and intake tracking |
| Activity Log | `/documentation/activities` | POST | Activities and engagement |
| View Logs | `/documentation/{type}?client_id={id}` | GET | Filtered by type and client |

---

### 20. Reports & Summaries (Page 19)
**Purpose:** Generate and view reports

| Report Type | Endpoint | Method | Notes |
|-------------|----------|--------|-------|
| Weekly Summary | `/reports/weekly?client_id={id}&week_start={date}` | GET | Weekly client summary |
| Monthly Report | `/reports/monthly?staff_id={id}&month={date}` | GET | Monthly DSP report |
| Custom Report | `/reports/custom` | POST | Custom date range/filters |

**Example - Weekly Summary:**
```bash
curl -X GET "http://localhost:8000/api/v1/reports/weekly?client_id={uuid}&week_start=2025-10-01" \
  -H "Authorization: Bearer {token}"
```

---

### 21. Training & Notices (Page 20-21)
**Purpose:** Staff training records and notices

| UI Element | Endpoint | Method | Notes |
|------------|----------|--------|-------|
| Notices List | `/notifications?category=announcement` | GET | Organization announcements |
| Training Records | `/staff/training` | GET | DSP training history |
| Required Training | `/staff/training/required` | GET | Pending required training |

---

## Endpoint Reference

### Complete Endpoint List

#### Authentication
- `POST /auth/login` - Login
- `POST /auth/logout` - Logout
- `POST /auth/refresh` - Refresh token
- `POST /auth/change-password` - Change password

#### Dashboard
- `GET /dashboard/overview` - Dashboard overview
- `GET /dashboard/clients-assigned` - Daily client assignments
- `GET /dashboard/tasks-summary` - Task statistics
- `GET /dashboard/quick-actions` - Available quick actions

#### Clients
- `GET /clients` - List clients (filterable)
- `GET /clients/{id}` - Get client details
- `PUT /clients/{id}` - Update client (admin only)
- `GET /clients/{id}/contacts` - Get client contacts

#### Documentation
- **Vitals:**
  - `POST /documentation/vitals` - Create vitals log
  - `GET /documentation/vitals` - List vitals logs
  - `GET /documentation/vitals?client_id={id}` - Client vitals

- **Shift Notes:**
  - `POST /documentation/shift-notes` - Create shift note
  - `GET /documentation/shift-notes` - List shift notes
  - `GET /documentation/shift-notes?client_id={id}` - Client shift notes

- **Incidents:**
  - `POST /documentation/incidents` - Create incident report (multipart)
  - `GET /documentation/incidents` - List incidents
  - `GET /documentation/incidents/{id}/files/{file_id}` - Download file

- **Meals:**
  - `POST /documentation/meals` - Create meal log
  - `GET /documentation/meals` - List meal logs
  - `GET /documentation/meals/{id}` - Get meal log
  - `PUT /documentation/meals/{id}` - Update meal log
  - `DELETE /documentation/meals/{id}` - Delete meal log

- **Activities:**
  - `POST /documentation/activities` - Create activity log
  - `GET /documentation/activities` - List activity logs
  - `GET /documentation/activities/{id}` - Get activity log
  - `PUT /documentation/activities/{id}` - Update activity log
  - `DELETE /documentation/activities/{id}` - Delete activity log

#### Tasks
- `POST /tasks` - Create task
- `GET /tasks` - List tasks (filterable)
- `GET /tasks/{id}` - Get task details
- `PUT /tasks/{id}` - Update task
- `DELETE /tasks/{id}` - Delete task
- `GET /tasks/summary/stats` - Task statistics

#### Scheduling
- `GET /scheduling/schedules` - List schedules
- `GET /scheduling/shifts` - List shifts (filterable)
- `GET /scheduling/shifts/{id}` - Get shift details
- `GET /scheduling/calendar` - Calendar view
- `POST /scheduling/time-clock/clock-in` - Clock in
- `POST /scheduling/time-clock/clock-out` - Clock out
- `POST /scheduling/time-clock/break-start` - Start break
- `POST /scheduling/time-clock/break-end` - End break

#### Notifications
- `GET /notifications` - List notifications
- `GET /notifications/stats` - Notification statistics
- `POST /notifications/{id}/read` - Mark as read
- `POST /notifications/mark-all-read` - Mark all as read

---

## Common Schemas

### Pagination
Most list endpoints support pagination:

**Query Parameters:**
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 20, max: 100)
- `offset` - Alternative to page (for offset-based pagination)
- `limit` - Alternative to page_size

**Response Format:**
```json
{
  "data": [...],
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "pages": 5
  }
}
```

### Date Filtering
Date filters accept ISO 8601 format:

**Query Parameters:**
- `date_from` - Start date (YYYY-MM-DD)
- `date_to` - End date (YYYY-MM-DD)
- `date_filter` - Specific date (YYYY-MM-DD)

**Examples:**
```
?date_from=2025-10-01&date_to=2025-10-07
?date_filter=2025-10-02
```

### Enumerations

**Meal Types:**
- `breakfast`, `lunch`, `dinner`, `snack`

**Intake Amounts:**
- `none`, `minimal`, `partial`, `most`, `all`

**Activity Types:**
- `recreation`, `exercise`, `social`, `educational`, `vocational`, `therapeutic`, `community`, `personal_care`, `other`

**Participation Levels:**
- `full`, `partial`, `minimal`, `refused`, `unable`

**Moods:**
- `happy`, `content`, `neutral`, `anxious`, `irritable`, `sad`, `angry`

**Task Status:**
- `pending`, `in_progress`, `completed`, `cancelled`, `overdue`

**Task Priority:**
- `low`, `medium`, `high`, `urgent`

**Incident Severity:**
- `low`, `medium`, `high`, `critical`

**Incident Types:**
- `fall`, `medication_error`, `injury`, `behavioral`, `emergency`, `property_damage`, `other`

---

## Error Handling

### Standard Error Response
```json
{
  "detail": "Error message description"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Success |
| 201 | Created | Resource created successfully |
| 204 | No Content | Success with no response body |
| 400 | Bad Request | Invalid request data, validation errors |
| 401 | Unauthorized | Missing or invalid token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 422 | Unprocessable Entity | Validation error |
| 500 | Internal Server Error | Server error |

### Common Error Scenarios

**Authentication Errors:**
```json
{
  "detail": "Invalid authentication credentials"
}
```

**Permission Errors:**
```json
{
  "detail": "Permission denied: clients:read"
}
```

**Validation Errors:**
```json
{
  "detail": [
    {
      "loc": ["body", "temperature"],
      "msg": "ensure this value is greater than or equal to 90.0",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

**Not Found Errors:**
```json
{
  "detail": "Client not found"
}
```

---

## Testing

### Using Test Credentials

```bash
# Login as DSP
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "timothy.williams",
    "password": "YVF0#Fk#4P#5"
  }'

# Save the access_token from the response
export TOKEN="eyJhbGc..."

# Test dashboard endpoint
curl -X GET "http://localhost:8000/api/v1/dashboard/overview" \
  -H "Authorization: Bearer $TOKEN"
```

### DSP Test Credentials

| Name | Username | Password | Emp ID |
|------|----------|----------|--------|
| Timothy Williams | timothy.williams | YVF0#Fk#4P#5 | SP001 |
| David Mateo | david.mateo | UXjKQfu$gI0L | SP002 |
| Mat Anderson | mat.anderson | #O@p#NeA4DRv | SP003 |
| Alfred Taylor | alfred.taylor | zv2UGa5M03tJ | SP004 |
| Otto Brown | otto.brown | sJ46$B3NB0ao | SP005 |

### Testing with Docker

```bash
# Start the application
./deploy.sh dev

# Application will be available at:
# API: http://localhost:8000/api/v1
# Docs: http://localhost:8000/api/v1/docs
```

### Interactive API Documentation

Visit `http://localhost:8000/api/v1/docs` for interactive Swagger documentation where you can:
1. Authorize with your Bearer token
2. Test endpoints directly
3. View request/response schemas
4. See validation requirements

---

## Best Practices

### 1. Token Management
- Store tokens securely (use secure storage, not localStorage for sensitive apps)
- Refresh tokens before they expire
- Handle 401 errors by redirecting to login
- Clear tokens on logout

### 2. Error Handling
```javascript
async function apiCall(endpoint, options) {
  try {
    const response = await fetch(endpoint, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    if (response.status === 401) {
      // Token expired or invalid
      redirectToLogin();
      return;
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}
```

### 3. Data Validation
- Validate data on the frontend before sending
- Handle validation errors gracefully
- Display user-friendly error messages
- Use enum values exactly as specified

### 4. Performance
- Implement pagination for lists
- Cache frequently accessed data
- Use appropriate page sizes
- Implement infinite scroll or load-more patterns

### 5. Date Handling
- Always send dates in ISO 8601 format
- Convert to user's timezone for display
- Use UTC for storage and transmission

### 6. File Uploads
- Use multipart/form-data for file uploads
- Validate file types and sizes on frontend
- Show upload progress
- Handle upload errors gracefully

---

## Support & Resources

### API Documentation
- **Interactive Docs:** http://localhost:8000/api/v1/docs
- **Alternative Docs:** http://localhost:8000/api/v1/redoc

### Database Reset
```bash
# Stop containers and remove volumes
docker compose down -v

# Restart with fresh database
./deploy.sh dev
```

### Common Issues

**Issue: 401 Unauthorized**
- Check if token is included in Authorization header
- Verify token hasn't expired
- Ensure token format is: `Bearer {token}`

**Issue: 403 Forbidden**
- User doesn't have required permissions
- Check role and permission assignments
- Some endpoints require specific roles

**Issue: 404 Not Found**
- Verify the client/resource exists
- Check organization_id matches
- Ensure resource belongs to user's organization

**Issue: 422 Validation Error**
- Check request body format
- Verify all required fields are provided
- Ensure enum values match exactly
- Check data type constraints

---

## Changelog

### Version 1.0.0 (2025-10-02)
- Initial API documentation
- Added meal logging endpoints
- Added activity logging endpoints
- Fixed authentication on client endpoints
- Updated permission-based access control

---

## Contact

For issues or questions:
- GitHub Issues: https://github.com/yourusername/starline-backend/issues
- Email: support@starline.com

---

**Note:** This documentation covers the DSP-specific UI endpoints. For administrative endpoints or additional features, refer to the complete API documentation at `/api/v1/docs`.
