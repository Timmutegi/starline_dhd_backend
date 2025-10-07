# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Starline is a comprehensive white-label backend system for domestic service providers (DSPs), similar to Therap Services. It manages client care, staff operations, documentation, billing, compliance, and more. Built with FastAPI, PostgreSQL, and AWS infrastructure, it provides multi-tenant support with complete data isolation.

## Commands

### Development

```bash
# Start development environment (includes PostgreSQL, Redis, pgAdmin, Redis Commander)
./deploy.sh dev

# Start with rebuild
./deploy.sh dev --build

# Check service status
./deploy.sh dev --status

# View logs
./deploy.sh dev --logs

# Stop services
./deploy.sh dev --stop

# Direct Docker Compose commands
docker compose -f docker-compose-dev.yml up -d
docker compose -f docker-compose-dev.yml logs -f backend
docker compose -f docker-compose-dev.yml down
```

### Production

```bash
# Deploy to production
./deploy.sh production

# Deploy with database backup
./deploy.sh prod --backup

# Deploy with monitoring stack (Prometheus, Grafana)
./deploy.sh prod --monitoring
```

### Database

```bash
# Initialize database (creates tables and default admin user)
python -m app.init_db

# Seed sample data (clients, staff, assignments)
python seed_database.py

# Database migrations (if Alembic is configured)
alembic upgrade head
alembic downgrade -1
alembic revision --autogenerate -m "description"
```

### Running the API

```bash
# Development mode (with hot reload)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode (multi-worker)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Testing

```bash
# Run tests (pytest configured in requirements.txt)
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_auth.py
```

## Architecture

### Application Structure

```
app/
├── main.py                 # FastAPI application entry point, router registration
├── core/
│   ├── config.py          # Settings loaded from environment variables
│   ├── database.py        # SQLAlchemy engine and session management
│   ├── dependencies.py    # Dependency injection (auth, role checks)
│   ├── security.py        # JWT, password hashing, token generation
│   └── audit_mixins.py    # Audit trail mixins for models
├── models/                # SQLAlchemy models (User, Client, Staff, etc.)
├── schemas/               # Pydantic schemas for request/response validation
├── api/v1/               # API route handlers organized by resource
│   ├── auth/             # Login, logout, password reset
│   ├── users/            # User CRUD operations
│   ├── clients/          # Client management
│   ├── staff/            # Staff management
│   ├── scheduling/       # Shifts, appointments, time clock, availability
│   ├── roles/            # Role and permission management
│   ├── dashboard.py      # Dashboard metrics and stats
│   ├── documentation.py  # Dynamic forms and documentation
│   ├── notifications.py  # Notification management
│   ├── tasks.py          # Task assignment and tracking
│   ├── admin.py          # Admin operations
│   └── audit.py          # Audit log access
├── middleware/
│   ├── auth.py           # Authentication middleware
│   └── audit_middleware.py  # HIPAA-compliant audit logging middleware
├── services/
│   ├── email_service.py  # Resend email integration
│   ├── audit_service.py  # Audit log creation and management
│   └── compliance_email_service.py  # Compliance notifications
└── emails/               # Email templates (Jinja2)
```

### Multi-Tenant Architecture

The system uses **organization-based multi-tenancy** with data isolation at the database level:

- **Organization model**: Central tenant identifier (`organizations` table)
- **User model**: Each user belongs to one organization (`organization_id` foreign key)
- **Data isolation**: All resources (clients, staff, schedules) are scoped to organization
- **White-label support**: Organizations have custom branding (logo, colors, subdomain)
- **Role-based access**: Permissions are scoped within organizations

**Key principle**: When creating or querying any resource, always filter/associate by the authenticated user's `organization_id` to ensure tenant isolation.

### Authentication & Authorization

**JWT-based authentication**:
- Access tokens (30 min expiry) and refresh tokens (7 days)
- Tokens stored in `user_sessions` table with device info
- Bearer token required in `Authorization` header

**Role hierarchy** (from highest to lowest privilege):
1. `super_admin` - Cross-organization access (system management)
2. `admin` - Organization-wide access
3. `manager` - Program/team management
4. `staff` - Client care and documentation
5. (Additional custom roles supported)

**Permission checking**:
- Use `get_current_user` dependency for authenticated endpoints
- Use `require_role(['admin', 'manager'])` for role-specific access
- Helper dependencies: `get_super_admin`, `get_admin_or_above`, `get_manager_or_above`, `get_staff_or_above`

**Security features**:
- Bcrypt password hashing (12 rounds)
- Account lockout after 5 failed login attempts (30 min lockout)
- Password history tracking (prevent reuse)
- Email verification with OTP
- Optional 2FA support (TOTP)

### Database Models

**Core models**:
- `User` - Authentication, profiles, role assignment
- `Organization` - Multi-tenant container with branding
- `Role` - Role definitions with permission associations
- `Permission` - Granular resource-action permissions
- `UserSession` - Active sessions with refresh tokens
- `Client` - Client demographics, care plans, health records
- `Staff` - Employee profiles, certifications, assignments
- `Shift`, `Appointment`, `Availability` - Scheduling components
- `Task`, `Notification` - Workflow management
- `AuditLog` - HIPAA-compliant activity tracking

**Important patterns**:
- All models inherit from `Base` (SQLAlchemy declarative base)
- Models with PHI inherit from `AuditMixin` for automatic audit logging
- UUID primary keys for all tables
- Timestamps: `created_at`, `updated_at` (auto-managed)
- Soft deletes available on some models

### Audit & Compliance

**HIPAA compliance features**:
- `AuditMiddleware` automatically logs all API requests/responses
- Sensitive fields (PHI) are masked in logs
- All data access tracked with user, timestamp, IP, action
- Audit logs stored in `audit_logs` table (never deleted)
- Excluded paths: `/docs`, `/health`, `/openapi.json` (non-PHI endpoints)

**Audit log fields**:
- `resource_type` - Model being accessed (e.g., "client", "user")
- `action` - Operation (CREATE, READ, UPDATE, DELETE, LOGIN, etc.)
- `user_id` - Actor performing the action
- `organization_id` - Tenant context
- `ip_address`, `user_agent` - Request metadata
- `changes_made` - JSON diff of before/after state
- `data_classification` - PHI, PII, INTERNAL, PUBLIC

**Compliance alerts**:
- Security events trigger email alerts to configured recipients
- Failed login attempts, unauthorized access logged
- Configuration: `AUDIT_ALERT_EMAIL`, `SECURITY_ALERT_EMAILS` in `.env`

### Email Service

Starline uses **Resend** for transactional emails:
- Configuration: `RESEND_API_KEY` and `FROM_EMAIL` in `.env`
- Email templates in `app/emails/` (Jinja2)
- Service: `app/services/email_service.py`
- Common emails: password reset, email verification, notifications

### File Storage

**AWS S3 integration**:
- Bucket configured via `AWS_S3_BUCKET` environment variable
- Files organized by organization and resource type
- CloudFront CDN for serving files: `CLOUDFRONT_URL`
- Credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

### API Conventions

**Response format**:
```json
{
  "id": "uuid",
  "field": "value",
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T00:00:00"
}
```

**Error format**:
```json
{
  "error": "Error message",
  "status_code": 400
}
```

**Pagination** (query parameters):
- `page` - Page number (default: 1)
- `limit` - Items per page (default: 20, max: 100)
- `search` - Search term (filters across relevant fields)
- `sort_by` - Field to sort by
- `sort_order` - "asc" or "desc"

**Common headers**:
- `Authorization: Bearer <token>` - Required for authenticated endpoints
- `Content-Type: application/json` - For POST/PUT requests

### Rate Limiting

**SlowAPI integration**:
- Rate limiting middleware configured at app level
- Default: 60 requests per minute per IP
- Configuration: `RATE_LIMIT_PER_MINUTE` in settings
- Excluded endpoints: `/health`, `/docs`

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Expected response
{"status": "healthy", "database": "connected", "version": "1.0.0"}
```

## Environment Configuration

Critical environment variables (`.env` file):

```bash
# Database
POSTGRES_USER=starline
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=starline_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Application
SECRET_KEY=<jwt-secret-key>
API_HOST=0.0.0.0
API_PORT=8000

# AWS
AWS_ACCESS_KEY=<aws-access-key>
AWS_SECRET_KEY=<aws-secret-key>
AWS_S3_BUCKET=<bucket-name>
AWS_REGION=eu-west-2
CLOUDFRONT_URL=<cloudfront-distribution-url>

# Email
RESEND_API_KEY=<resend-api-key>
FROM_EMAIL=noreply@domain.com
FRONTEND_URL=http://localhost:4200

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Default Admin (created on first run)
DEFAULT_ADMIN_EMAIL=support@starline.com
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=Admin123!!
DEFAULT_ADMIN_FULL_NAME=Administrator
```

## Development Guidelines

### Adding a New Model

1. Create model in `app/models/<resource>.py` (inherit from `Base`, optionally `AuditMixin`)
2. Import model in `app/main.py` to register with SQLAlchemy
3. Create Pydantic schemas in `app/schemas/<resource>.py`
4. Create router in `app/api/v1/<resource>/router.py`
5. Register router in `app/main.py`
6. If sensitive data (PHI), set `__audit_resource_type__` and `__audit_phi_fields__` on model

### Adding a New API Endpoint

1. Define route in appropriate router file under `app/api/v1/`
2. Use dependency injection for authentication: `current_user: User = Depends(get_current_user)`
3. Use role dependencies for authorization: `current_user: User = Depends(require_role(['admin']))`
4. Return Pydantic schemas for type safety
5. Handle exceptions with HTTPException
6. Filter queries by `current_user.organization_id` for multi-tenant isolation

### Database Sessions

Always use dependency injection for database sessions:

```python
from app.core.database import get_db
from sqlalchemy.orm import Session

@router.get("/resource")
def get_resource(db: Session = Depends(get_db)):
    # Use db session
    resource = db.query(Model).filter(...).first()
    return resource
```

Sessions are automatically closed after request completion.

### Audit Logging

Models with PHI automatically log changes when using `AuditMixin`:

```python
from app.core.audit_mixins import AuditMixin

class Client(AuditMixin, Base):
    __tablename__ = "clients"
    __audit_resource_type__ = "client"
    __audit_phi_fields__ = ["first_name", "last_name", "ssn", "medical_info"]
    # ... fields
```

For manual audit logging, use `AuditService`:

```python
from app.services.audit_service import AuditService

await AuditService.log_action(
    db=db,
    action=AuditAction.READ,
    resource_type="client",
    resource_id=client_id,
    user_id=current_user.id,
    ip_address=request.client.host
)
```

## Common Issues

### Database connection errors
- Ensure PostgreSQL is running: `docker compose -f docker-compose-dev.yml ps`
- Check credentials in `.env` match database configuration
- Verify `POSTGRES_HOST` is correct (`localhost` for local, `postgres` in Docker)

### Missing tables
- Run database initialization: `python -m app.init_db`
- This creates all tables and default admin user

### Authentication failures
- Check JWT secret is configured: `SECRET_KEY` in `.env`
- Verify token hasn't expired (30 min for access tokens)
- Use refresh token endpoint to get new access token

### CORS issues
- CORS is configured to allow all origins in development (`BACKEND_CORS_ORIGINS: ["*"]`)
- For production, update `settings.BACKEND_CORS_ORIGINS` with specific domains

### AWS/S3 errors
- Ensure AWS credentials are configured in `.env`
- Verify S3 bucket exists and has correct permissions
- CloudFront URL should end with `/`

## API Documentation

When the application is running, interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`

## Documentation

Comprehensive documentation is available in the repository:
- `README.md` - System overview, setup, and deployment
- `DEPLOYMENT.md` - Deployment guide for dev and production
- `Documentation/STARLINE_BACKEND_FEATURES.md` - Complete feature specifications
- `Documentation/STARLINE_DATABASE_SCHEMA.md` - Database schema details
- `Documentation/STARLINE_API_DOCUMENTATION.md` - API endpoint documentation
- `Documentation/STARLINE_SYSTEM_ARCHITECTURE.md` - Architecture overview
- `FEATURES/` - Individual feature design documents
