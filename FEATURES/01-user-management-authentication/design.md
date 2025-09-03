# User Management & Authentication - Design Document

## Overview
The User Management & Authentication system provides secure access control, user administration, and role-based permissions for the Starline platform. This feature supports multi-tenant architecture for white-labeling.

## Architecture

### Database Schema

```sql
-- Organizations (for white-labeling)
organizations:
  - id: UUID (PK)
  - name: VARCHAR(255)
  - subdomain: VARCHAR(100) UNIQUE
  - logo_url: TEXT
  - primary_color: VARCHAR(7)
  - secondary_color: VARCHAR(7)
  - contact_email: VARCHAR(255)
  - contact_phone: VARCHAR(20)
  - address: TEXT
  - timezone: VARCHAR(50)
  - settings: JSONB
  - is_active: BOOLEAN
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Users
users:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - email: VARCHAR(255) UNIQUE
  - username: VARCHAR(100)
  - password_hash: VARCHAR(255)
  - first_name: VARCHAR(100)
  - last_name: VARCHAR(100)
  - phone: VARCHAR(20)
  - profile_picture_url: TEXT
  - role_id: UUID (FK)
  - employee_id: VARCHAR(50)
  - hire_date: DATE
  - status: ENUM('active', 'inactive', 'suspended', 'pending')
  - last_login: TIMESTAMP
  - password_reset_token: VARCHAR(255)
  - password_reset_expires: TIMESTAMP
  - email_verified: BOOLEAN
  - email_verification_token: VARCHAR(255)
  - two_factor_enabled: BOOLEAN
  - two_factor_secret: VARCHAR(255)
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Roles
roles:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - name: VARCHAR(100)
  - description: TEXT
  - is_system_role: BOOLEAN
  - created_at: TIMESTAMP
  - updated_at: TIMESTAMP

-- Permissions
permissions:
  - id: UUID (PK)
  - resource: VARCHAR(100)
  - action: VARCHAR(50)
  - description: TEXT
  - created_at: TIMESTAMP

-- Role Permissions
role_permissions:
  - role_id: UUID (FK)
  - permission_id: UUID (FK)
  - created_at: TIMESTAMP
  PRIMARY KEY (role_id, permission_id)

-- User Sessions
user_sessions:
  - id: UUID (PK)
  - user_id: UUID (FK)
  - token: VARCHAR(500) UNIQUE
  - refresh_token: VARCHAR(500) UNIQUE
  - ip_address: VARCHAR(45)
  - user_agent: TEXT
  - expires_at: TIMESTAMP
  - created_at: TIMESTAMP
  - revoked_at: TIMESTAMP

-- Audit Logs
auth_audit_logs:
  - id: UUID (PK)
  - user_id: UUID (FK)
  - action: VARCHAR(100)
  - ip_address: VARCHAR(45)
  - user_agent: TEXT
  - metadata: JSONB
  - created_at: TIMESTAMP
```

### API Endpoints

#### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/logout` - User logout
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/forgot-password` - Request password reset
- `POST /api/v1/auth/reset-password` - Reset password
- `POST /api/v1/auth/verify-email` - Verify email address
- `POST /api/v1/auth/2fa/enable` - Enable 2FA
- `POST /api/v1/auth/2fa/disable` - Disable 2FA
- `POST /api/v1/auth/2fa/verify` - Verify 2FA code

#### User Management
- `GET /api/v1/users` - List all users (paginated)
- `GET /api/v1/users/{id}` - Get user details
- `POST /api/v1/users` - Create new user
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Deactivate user
- `POST /api/v1/users/{id}/suspend` - Suspend user
- `POST /api/v1/users/{id}/activate` - Activate user
- `POST /api/v1/users/{id}/reset-password` - Admin password reset
- `GET /api/v1/users/{id}/sessions` - Get user sessions
- `POST /api/v1/users/{id}/revoke-sessions` - Revoke all sessions

#### Role & Permission Management
- `GET /api/v1/roles` - List all roles
- `GET /api/v1/roles/{id}` - Get role details
- `POST /api/v1/roles` - Create new role
- `PUT /api/v1/roles/{id}` - Update role
- `DELETE /api/v1/roles/{id}` - Delete role
- `GET /api/v1/permissions` - List all permissions
- `POST /api/v1/roles/{id}/permissions` - Assign permissions

#### Organization Management
- `GET /api/v1/organizations/current` - Get current organization
- `PUT /api/v1/organizations/current` - Update organization settings

### Security Features

#### Authentication Flow
1. **Login Process**:
   - Validate credentials
   - Check user status (active/suspended)
   - Generate JWT tokens (access + refresh)
   - Log authentication event
   - Return tokens and user profile

2. **Token Management**:
   - Access token: 15 minutes expiry
   - Refresh token: 7 days expiry
   - Secure token storage in HTTP-only cookies
   - Token rotation on refresh

3. **Password Security**:
   - Bcrypt hashing with salt rounds = 12
   - Password complexity requirements
   - Password history (prevent reuse)
   - Account lockout after failed attempts

4. **Two-Factor Authentication**:
   - TOTP-based 2FA
   - Backup codes generation
   - QR code for authenticator apps

### Middleware & Guards

```python
# Authentication middleware
class AuthenticationMiddleware:
    - Validate JWT token
    - Check token expiry
    - Verify user status
    - Load user context

# Permission guard
class PermissionGuard:
    - Check user permissions
    - Validate resource access
    - Log access attempts

# Rate limiting
class RateLimiter:
    - Login attempts: 5 per 15 minutes
    - API calls: 100 per minute per user
    - Password reset: 3 per hour
```

### Integration Points

1. **Email Service (Resend)**:
   - Welcome emails
   - Password reset emails
   - Email verification
   - Security alerts

2. **AWS S3**:
   - Profile picture storage
   - Organization logo storage

3. **Redis Cache**:
   - Session management
   - Rate limiting counters
   - Permission cache

### White-Labeling Support

1. **Multi-tenant Isolation**:
   - Organization-based data segregation
   - Subdomain routing
   - Custom branding per organization

2. **Customizable Elements**:
   - Logo and branding
   - Color schemes
   - Email templates
   - Custom domains (future)

### Error Handling

```python
# Standard error responses
- 401: Unauthorized
- 403: Forbidden
- 404: User not found
- 409: Email already exists
- 422: Validation errors
- 429: Too many requests
```

### Performance Optimizations

1. **Caching Strategy**:
   - User permissions cached for 5 minutes
   - Organization settings cached for 1 hour
   - Session data cached in Redis

2. **Database Indexing**:
   - Index on email, username
   - Composite index on organization_id + status
   - Index on session tokens

3. **Query Optimization**:
   - Eager loading for user roles
   - Pagination for user lists
   - Selective field queries

### Monitoring & Logging

1. **Audit Trail**:
   - All authentication events
   - Permission changes
   - User modifications
   - Failed login attempts

2. **Metrics**:
   - Login success/failure rates
   - Token refresh frequency
   - API endpoint response times
   - Active user sessions

### Compliance & Security

1. **HIPAA Compliance**:
   - Encrypted passwords
   - Session timeout after inactivity
   - Audit logging
   - Access controls

2. **Data Protection**:
   - PII encryption at rest
   - TLS for data in transit
   - Regular security audits
   - Penetration testing