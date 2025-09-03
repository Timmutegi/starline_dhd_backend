# Communication & Notifications - Design Document

## Overview
Multi-channel communication system with intelligent notifications, messaging, and alert management integrated with Resend.

## Database Schema
```sql
-- Notification Templates
notification_templates:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - template_name: VARCHAR(255)
  - template_type: ENUM('email', 'sms', 'push', 'in_app')
  - subject: VARCHAR(255)
  - body: TEXT
  - variables: JSONB

-- Notifications
notifications:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - user_id: UUID (FK)
  - notification_type: VARCHAR(100)
  - title: VARCHAR(255)
  - message: TEXT
  - priority: ENUM('low', 'normal', 'high', 'urgent')
  - channels: VARCHAR(50)[]
  - status: ENUM('pending', 'sent', 'delivered', 'failed', 'read')
  - sent_at: TIMESTAMP
  - read_at: TIMESTAMP

-- Messages
messages:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - sender_id: UUID (FK)
  - recipient_id: UUID (FK)
  - subject: VARCHAR(255)
  - body: TEXT
  - message_type: ENUM('direct', 'broadcast', 'group')
  - is_confidential: BOOLEAN
  - sent_at: TIMESTAMP

-- Communication Preferences
communication_preferences:
  - id: UUID (PK)
  - user_id: UUID (FK)
  - notification_type: VARCHAR(100)
  - email_enabled: BOOLEAN
  - sms_enabled: BOOLEAN
  - push_enabled: BOOLEAN
  - in_app_enabled: BOOLEAN
  - quiet_hours_start: TIME
  - quiet_hours_end: TIME
```

## API Endpoints
- `POST /api/v1/notifications/send` - Send notification
- `GET /api/v1/notifications` - List user notifications
- `PUT /api/v1/notifications/{id}/read` - Mark as read
- `GET /api/v1/messages` - List messages
- `POST /api/v1/messages` - Send message
- `PUT /api/v1/communication/preferences` - Update preferences

## Key Features  
- Multi-channel delivery (Email, SMS, Push, In-app)
- Smart routing based on urgency and preferences
- Message templates with variable substitution
- Delivery tracking and read receipts
- Escalation workflows for critical alerts
- Quiet hours and Do Not Disturb modes
- Group messaging and broadcasts
- Integration with Resend for email delivery