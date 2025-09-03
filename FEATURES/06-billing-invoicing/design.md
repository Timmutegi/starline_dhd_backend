# Billing & Invoicing - Design Document

## Overview
Comprehensive billing system supporting multiple payers, service tracking, automated claim generation, and revenue management for domestic service providers.

## Database Schema

```sql
-- Service Catalog
services:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - service_code: VARCHAR(50)
  - service_name: VARCHAR(255)
  - description: TEXT
  - unit_type: ENUM('hour', 'day', 'visit', 'unit')
  - base_rate: DECIMAL(10,2)
  - is_active: BOOLEAN

-- Rate Tables
rate_tables:
  - id: UUID (PK)
  - payer_id: UUID (FK)
  - service_id: UUID (FK)
  - rate: DECIMAL(10,2)
  - effective_date: DATE
  - expiry_date: DATE

-- Service Authorizations
service_authorizations:
  - id: UUID (PK)
  - client_id: UUID (FK)
  - payer_id: UUID (FK)
  - service_id: UUID (FK)
  - authorization_number: VARCHAR(100)
  - authorized_units: INTEGER
  - used_units: INTEGER
  - start_date: DATE
  - end_date: DATE
  - status: ENUM('active', 'expired', 'suspended')

-- Billable Services (actual service delivery)
billable_services:
  - id: UUID (PK)
  - client_id: UUID (FK)
  - staff_id: UUID (FK)
  - service_id: UUID (FK)
  - authorization_id: UUID (FK)
  - service_date: DATE
  - start_time: TIME
  - end_time: TIME
  - units: DECIMAL(8,2)
  - rate: DECIMAL(10,2)
  - total_amount: DECIMAL(12,2)
  - notes: TEXT
  - created_at: TIMESTAMP

-- Claims
claims:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - payer_id: UUID (FK)
  - claim_number: VARCHAR(100)
  - claim_type: ENUM('initial', 'replacement', 'void')
  - total_amount: DECIMAL(12,2)
  - status: ENUM('draft', 'submitted', 'processed', 'paid', 'denied', 'rejected')
  - submitted_date: DATE
  - processed_date: DATE
  - payment_date: DATE
  - created_at: TIMESTAMP

-- Invoices
invoices:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - client_id: UUID (FK)
  - invoice_number: VARCHAR(100)
  - invoice_date: DATE
  - due_date: DATE
  - subtotal: DECIMAL(12,2)
  - tax_amount: DECIMAL(10,2)
  - total_amount: DECIMAL(12,2)
  - paid_amount: DECIMAL(12,2)
  - status: ENUM('draft', 'sent', 'overdue', 'paid', 'cancelled')

-- Payments
payments:
  - id: UUID (PK)
  - invoice_id: UUID (FK)
  - payment_method: VARCHAR(50)
  - amount: DECIMAL(12,2)
  - payment_date: DATE
  - reference_number: VARCHAR(100)
  - notes: TEXT
```

## API Endpoints
- `GET /api/v1/billing/services` - List billable services
- `POST /api/v1/billing/services` - Create service entry
- `GET /api/v1/billing/claims` - List claims
- `POST /api/v1/billing/claims/generate` - Generate claim
- `GET /api/v1/billing/invoices` - List invoices
- `POST /api/v1/billing/payments` - Record payment

## Key Features
- Service authorization tracking
- Automated claim generation
- Electronic claim submission (837 EDI)
- Payment reconciliation
- Revenue reporting and analytics
- Aging reports and collections
- Integration with accounting systems