# Starline Backend - API Documentation

## Overview

This document provides comprehensive API documentation for the Starline Backend system, designed for domestic service providers managing client care, documentation, billing, and compliance.

### Base Configuration
- **Base URL**: `https://api.starline.com/v1`
- **Authentication**: Bearer JWT Token
- **Rate Limiting**: 1000 requests/hour per user
- **Response Format**: JSON with consistent error handling
- **API Version**: v1

## Authentication

### Authentication Flow

```javascript
// Login
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "securePassword123"
}

// Response
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 900,
    "user": {
      "id": "user-123",
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "role": "support_staff"
    }
  }
}
```

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | User login |
| POST | `/auth/logout` | User logout |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/forgot-password` | Request password reset |
| POST | `/auth/reset-password` | Reset password with token |
| POST | `/auth/verify-email` | Verify email address |
| POST | `/auth/2fa/enable` | Enable 2FA |
| POST | `/auth/2fa/disable` | Disable 2FA |
| POST | `/auth/2fa/verify` | Verify 2FA code |

## Standard Response Format

### Success Response
```json
{
  "success": true,
  "data": {
    // Response data
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req-12345",
    "version": "v1"
  },
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8
  }
}
```

### Error Response
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

## Core API Endpoints

### 1. User Management

```javascript
// List users
GET /api/v1/users?page=1&limit=20&search=john&status=active

// Create user
POST /api/v1/users
{
  "email": "new@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "role_id": "role-123",
  "organization_id": "org-456"
}

// Get user profile
GET /api/v1/users/user-123

// Update user
PUT /api/v1/users/user-123
{
  "first_name": "Updated Name",
  "phone": "555-0123"
}
```

### 2. Client Management

```javascript
// List clients with filters
GET /api/v1/clients?page=1&limit=20&status=active&location=loc-123

// Create client
POST /api/v1/clients
{
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "1985-03-15",
  "primary_diagnosis": "Developmental disability",
  "admission_date": "2024-01-01"
}

// Get client details
GET /api/v1/clients/client-123

// Get client timeline
GET /api/v1/clients/client-123/timeline

// Add client contact
POST /api/v1/clients/client-123/contacts
{
  "contact_type": "emergency",
  "first_name": "Mary",
  "last_name": "Doe",
  "relationship": "Mother",
  "phone_primary": "555-0124"
}
```

### 3. Staff Management

```javascript
// List staff members
GET /api/v1/staff?department=residential&status=active

// Create staff member
POST /api/v1/staff
{
  "employee_id": "EMP-001",
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane.smith@example.com",
  "hire_date": "2024-01-15",
  "job_title": "Direct Support Professional"
}

// Get staff training records
GET /api/v1/staff/staff-123/training

// Add certification
POST /api/v1/staff/staff-123/certifications
{
  "certification_name": "CPR Certification",
  "issuing_organization": "American Red Cross",
  "issue_date": "2024-01-01",
  "expiry_date": "2025-01-01"
}
```

### 4. Scheduling & Calendar

```javascript
// List schedules
GET /api/v1/schedules?start_date=2024-01-01&end_date=2024-01-31

// Create schedule
POST /api/v1/schedules
{
  "schedule_name": "Weekly Schedule - Jan 2024",
  "schedule_type": "weekly",
  "start_date": "2024-01-01",
  "end_date": "2024-01-07"
}

// Create shift
POST /api/v1/shifts
{
  "staff_id": "staff-123",
  "location_id": "loc-456",
  "shift_date": "2024-01-15",
  "start_time": "08:00:00",
  "end_time": "16:00:00"
}

// Clock in
POST /api/v1/time-clock/clock-in
{
  "shift_id": "shift-789",
  "location": {
    "latitude": 40.7128,
    "longitude": -74.0060
  }
}

// Schedule appointment
POST /api/v1/appointments
{
  "client_id": "client-123",
  "staff_id": "staff-456",
  "title": "Medical Appointment",
  "start_datetime": "2024-01-15T14:00:00Z",
  "end_datetime": "2024-01-15T15:00:00Z",
  "appointment_type": "medical"
}
```

### 5. Documentation & Forms

```javascript
// List form templates
GET /api/v1/forms/templates?category=documentation

// Create form template
POST /api/v1/forms/templates
{
  "template_name": "Daily Progress Note",
  "category": "documentation",
  "form_structure": {
    "fields": [
      {
        "field_id": "client_mood",
        "type": "select",
        "label": "Client Mood",
        "options": ["Happy", "Neutral", "Sad"],
        "required": true
      }
    ]
  }
}

// Submit form
POST /api/v1/forms/submissions
{
  "form_template_id": "template-123",
  "client_id": "client-456",
  "submission_data": {
    "client_mood": "Happy",
    "activities_completed": ["Personal Care", "Meals"]
  }
}

// Capture signature
POST /api/v1/signatures
{
  "form_submission_id": "submission-789",
  "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."
}
```

### 6. Billing & Invoicing

```javascript
// Create billable service
POST /api/v1/billing/services
{
  "client_id": "client-123",
  "staff_id": "staff-456",
  "service_id": "service-789",
  "service_date": "2024-01-15",
  "units": 4.0,
  "rate": 25.50
}

// Generate claims
POST /api/v1/billing/claims/generate
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "payer_id": "payer-123"
}

// List claims
GET /api/v1/billing/claims?status=submitted&payer=medicaid

// Record payment
POST /api/v1/billing/payments
{
  "claim_id": "claim-456",
  "amount": 1250.00,
  "payment_date": "2024-01-20",
  "reference_number": "PMT-789"
}
```

### 7. Reporting & Analytics

```javascript
// List report templates
GET /api/v1/reports/templates?category=compliance

// Generate report
POST /api/v1/reports/generate
{
  "template_id": "template-123",
  "parameters": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "client_ids": ["client-123", "client-456"]
  },
  "format": "pdf"
}

// Get dashboard data
GET /api/v1/analytics/dashboard

// Get KPIs
GET /api/v1/analytics/kpis?period=monthly&year=2024

// Schedule report
POST /api/v1/reports/schedule
{
  "template_id": "template-456",
  "schedule_pattern": "0 9 1 * *",
  "recipients": ["manager@example.com"]
}
```

### 8. File Management

```javascript
// Upload file
POST /api/v1/files/upload
Content-Type: multipart/form-data
{
  "file": <binary data>,
  "client_id": "client-123",
  "category": "medical_records"
}

// List files
GET /api/v1/files?client_id=client-123&category=medical_records

// Download file
GET /api/v1/files/file-456/download

// Share file
POST /api/v1/files/file-456/share
{
  "user_ids": ["user-123", "user-789"],
  "permission": "read",
  "expires_at": "2024-02-15T00:00:00Z"
}
```

### 9. Communication & Notifications

```javascript
// Send notification
POST /api/v1/notifications/send
{
  "user_id": "user-123",
  "type": "medication_reminder",
  "title": "Medication Due",
  "message": "Client John Doe has medication due at 2:00 PM",
  "priority": "high",
  "channels": ["email", "sms", "push"]
}

// List user notifications
GET /api/v1/notifications?status=unread&priority=high

// Mark notification as read
PUT /api/v1/notifications/notification-456/read

// Send message
POST /api/v1/messages
{
  "recipient_id": "user-789",
  "subject": "Schedule Update",
  "body": "Your schedule for tomorrow has been updated.",
  "priority": "normal"
}
```

### 10. Compliance & Audit

```javascript
// Get audit logs
GET /api/v1/audit/logs?user_id=user-123&start_date=2024-01-01

// List compliance violations
GET /api/v1/compliance/violations?severity=high&status=open

// Run compliance assessment
POST /api/v1/compliance/assess
{
  "assessment_type": "hipaa_privacy",
  "scope": "organization"
}

// Get compliance dashboard
GET /api/v1/compliance/dashboard
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `AUTHENTICATION_FAILED` | 401 | Invalid credentials |
| `AUTHORIZATION_FAILED` | 403 | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | 404 | Resource does not exist |
| `RESOURCE_CONFLICT` | 409 | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_SERVER_ERROR` | 500 | Server error |

## Rate Limiting

- **Default**: 1000 requests per hour per user
- **Burst**: Up to 100 requests per minute
- **Headers**: 
  - `X-RateLimit-Limit`: Request limit
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Reset time (Unix timestamp)

## Pagination

All list endpoints support pagination with consistent parameters:

```javascript
GET /api/v1/endpoint?page=1&limit=20&sort=created_at&order=desc
```

- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20, max: 100)
- `sort`: Sort field
- `order`: Sort order (`asc` or `desc`)

## Filtering & Search

Most list endpoints support filtering and search:

```javascript
// Filtering
GET /api/v1/clients?status=active&location=loc-123

// Search
GET /api/v1/clients?search=john+doe

// Date ranges
GET /api/v1/appointments?start_date=2024-01-01&end_date=2024-01-31
```

## Webhooks

Starline supports webhooks for real-time event notifications:

```javascript
// Configure webhook
POST /api/v1/webhooks
{
  "url": "https://your-app.com/webhook",
  "events": ["client.created", "appointment.scheduled"],
  "secret": "your-webhook-secret"
}

// Webhook payload example
{
  "event": "client.created",
  "data": {
    "client": {
      "id": "client-123",
      "first_name": "John",
      "last_name": "Doe"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## SDKs and Libraries

### JavaScript/TypeScript
```bash
npm install @starline/api-client
```

```javascript
import { StarlineClient } from '@starline/api-client';

const client = new StarlineClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.starline.com/v1'
});

const clients = await client.clients.list({ status: 'active' });
```

### Python
```bash
pip install starline-api
```

```python
from starline import StarlineClient

client = StarlineClient(api_key='your-api-key')
clients = client.clients.list(status='active')
```

This comprehensive API documentation provides developers with all the information needed to integrate with the Starline backend system effectively.