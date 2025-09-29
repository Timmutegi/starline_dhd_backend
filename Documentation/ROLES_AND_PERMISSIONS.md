# Roles and Permissions System

This document describes the comprehensive roles and permissions system implemented in the Starline backend, which allows administrators to control access and assign specific capabilities to staff and clients.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Role Types](#role-types)
- [Permission Structure](#permission-structure)
- [User Assignment Options](#user-assignment-options)
- [API Endpoints](#api-endpoints)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)

## Overview

The Starline permission system provides granular access control through:

- **Role-Based Access Control (RBAC)**: Predefined roles with specific permission sets
- **Custom Permissions**: Individual permission assignment for specific users
- **Hybrid Approach**: Ability to use custom permissions that override role permissions
- **Organization Scoping**: Custom roles are organization-specific while system roles are global

## System Architecture

### Database Structure

```
users
├── role_id (FK to roles.id)
├── use_custom_permissions (boolean)
└── custom_permissions (many-to-many via user_permissions table)

roles
├── organization_id (FK to organizations.id, nullable for system roles)
├── is_system_role (boolean)
└── permissions (many-to-many via role_permissions table)

permissions
├── resource (string) - e.g., "staff", "clients", "scheduling"
├── action (string) - e.g., "create", "read", "update", "delete"
└── description (string)
```

### Permission Resolution Logic

When determining a user's permissions:

1. **If `use_custom_permissions = false`**: Use permissions from the assigned role
2. **If `use_custom_permissions = true`**: Use custom permissions (ignores role permissions)
3. **If no role assigned and no custom permissions**: User has no permissions

## Role Types

### System Roles (Global)

Predefined roles available to all organizations:

- **Super Admin**: Complete system access across all organizations
- **Organization Admin**: Full access within their organization
- **HR Manager**: Comprehensive staff management capabilities
- **Supervisor**: Staff oversight and performance management
- **Support Staff**: Client care and documentation access
- **Billing Admin**: Financial and billing system access

### Custom Roles (Organization-Specific)

Organizations can create custom roles with tailored permission sets:

- Scoped to the specific organization
- Can combine any available permissions
- Managed through the roles API endpoints
- Cannot be system roles (`is_system_role = false`)

## Permission Structure

Permissions follow a `resource:action` pattern:

### Available Resources

| Resource | Description |
|----------|-------------|
| `users` | User account management |
| `roles` | Role and permission management |
| `organizations` | Organization settings |
| `staff` | Staff member management |
| `clients` | Client management |
| `scheduling` | Schedule and shift management |
| `appointments` | Appointment scheduling |
| `time_clock` | Time tracking and clock in/out |
| `calendar` | Calendar events and management |
| `documentation` | Documentation access |
| `reports` | Report generation and viewing |
| `billing` | Financial and billing operations |

### Available Actions

| Action | Description |
|--------|-------------|
| `create` | Create new records |
| `read` | View/access records |
| `update` | Modify existing records |
| `delete` | Remove records |
| `manage_*` | Specialized management actions |
| `export` | Export data |
| `process` | Process transactions |

### Permission Examples

```
staff:create - Create new staff members
clients:read - View client information
scheduling:update - Modify schedules and shifts
reports:export - Export reports to files
billing:process - Process payments
```

## User Assignment Options

### Option 1: Role-Based Assignment

Assign a user to a predefined role:

```json
{
  "role_id": "uuid-of-role",
  "use_custom_permissions": false
}
```

The user inherits all permissions from the assigned role.

### Option 2: Custom Permissions

Assign specific permissions directly to a user:

```json
{
  "role_id": "uuid-of-role", // Optional, for organizational purposes
  "use_custom_permissions": true,
  "custom_permission_ids": [
    "permission-uuid-1",
    "permission-uuid-2",
    "permission-uuid-3"
  ]
}
```

The user gets exactly the specified permissions, ignoring role permissions.

### Option 3: Hybrid Approach

Assign a role for organizational context but override with custom permissions:

```json
{
  "role_id": "uuid-of-support-staff-role",
  "use_custom_permissions": true,
  "custom_permission_ids": [
    "clients:read",
    "clients:update",
    "scheduling:read"
  ]
}
```

## API Endpoints

### Role Management

#### List Roles
```http
GET /api/v1/roles/
Authorization: Bearer {token}

Query Parameters:
- include_system: boolean (include system roles)
```

#### Get Role Details
```http
GET /api/v1/roles/{role_id}
Authorization: Bearer {token}
```

#### Create Custom Role
```http
POST /api/v1/roles/
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Custom Role Name",
  "description": "Role description",
  "permission_ids": ["uuid1", "uuid2", "uuid3"]
}
```

#### Update Role
```http
PUT /api/v1/roles/{role_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Updated Role Name",
  "description": "Updated description",
  "permission_ids": ["uuid1", "uuid2"]
}
```

#### Delete Role
```http
DELETE /api/v1/roles/{role_id}
Authorization: Bearer {token}
```

#### List All Permissions
```http
GET /api/v1/roles/permissions/all
Authorization: Bearer {token}
```

### Staff Permission Management

#### Create Staff with Permissions
```http
POST /api/v1/staff/
Authorization: Bearer {token}
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "employee_id": "EMP001",
  "role_id": "role-uuid",
  "use_custom_permissions": true,
  "custom_permission_ids": ["perm-uuid-1", "perm-uuid-2"]
}
```

#### Update Staff Permissions
```http
PUT /api/v1/staff/{staff_id}/permissions
Authorization: Bearer {token}
Content-Type: application/json

{
  "role_id": "new-role-uuid",
  "use_custom_permissions": false,
  "custom_permission_ids": []
}
```

### Client Permission Management

#### Create Client with Permissions
```http
POST /api/v1/clients/
Authorization: Bearer {token}
Content-Type: application/json

{
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane.smith@example.com",
  "date_of_birth": "1990-01-01",
  "gender": "female",
  "role_id": "role-uuid",
  "use_custom_permissions": true,
  "custom_permission_ids": ["perm-uuid-1", "perm-uuid-2"]
}
```

#### Update Client Permissions
```http
PUT /api/v1/clients/{client_id}/permissions
Authorization: Bearer {token}
Content-Type: application/json

{
  "role_id": "new-role-uuid",
  "use_custom_permissions": false,
  "custom_permission_ids": []
}
```

## Usage Examples

### Example 1: Creating a Custom Role

```bash
# 1. Get all available permissions
curl -X GET "http://localhost:8000/api/v1/roles/permissions/all" \
  -H "Authorization: Bearer {token}"

# 2. Create custom role with selected permissions
curl -X POST "http://localhost:8000/api/v1/roles/" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Scheduling Coordinator",
    "description": "Manages schedules and appointments",
    "permission_ids": [
      "scheduling:create",
      "scheduling:read",
      "scheduling:update",
      "appointments:create",
      "appointments:read",
      "appointments:update",
      "staff:read"
    ]
  }'
```

### Example 2: Staff Member with Custom Permissions

```bash
# Create staff member with specific permissions (not role-based)
curl -X POST "http://localhost:8000/api/v1/staff/" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Alice",
    "last_name": "Johnson",
    "email": "alice.johnson@starline.com",
    "employee_id": "EMP002",
    "role_id": "support-staff-role-uuid",
    "use_custom_permissions": true,
    "custom_permission_ids": [
      "clients:read",
      "clients:update",
      "documentation:read",
      "scheduling:read"
    ]
  }'
```

### Example 3: Updating Permissions

```bash
# Change staff member from custom permissions to role-based
curl -X PUT "http://localhost:8000/api/v1/staff/{staff_id}/permissions" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "hr-manager-role-uuid",
    "use_custom_permissions": false,
    "custom_permission_ids": []
  }'
```

## Best Practices

### Role Design

1. **Start with System Roles**: Use predefined system roles when they match requirements
2. **Create Minimal Custom Roles**: Only create custom roles when system roles don't fit
3. **Principle of Least Privilege**: Grant only necessary permissions
4. **Clear Naming**: Use descriptive names for custom roles

### Permission Assignment

1. **Prefer Role-Based**: Use roles for common permission patterns
2. **Custom for Exceptions**: Use custom permissions for unique requirements
3. **Regular Review**: Periodically audit user permissions
4. **Document Changes**: Keep track of permission modifications

### Security Considerations

1. **Validation**: Always validate permission IDs before assignment
2. **Organization Scoping**: Ensure users can only access their organization's data
3. **Audit Logging**: Track permission changes for compliance
4. **Regular Cleanup**: Remove unused custom roles and revoke unnecessary permissions

### Performance Tips

1. **Cache Permissions**: Cache user permissions to avoid repeated database queries
2. **Batch Operations**: Update multiple permissions in single requests when possible
3. **Index Optimization**: Ensure proper database indexes on permission lookup fields

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**
   - Verify user has required permissions
   - Check if `use_custom_permissions` is set correctly
   - Ensure role is assigned and active

2. **Invalid Permission IDs**
   - Validate permission IDs exist in database
   - Check for typos in permission resource:action format

3. **Role Assignment Issues**
   - Verify role exists and belongs to correct organization
   - Check if role is marked as active/not deleted

### Debugging Steps

1. Check user's current permissions:
   ```sql
   SELECT u.use_custom_permissions, r.name as role_name, p.resource, p.action
   FROM users u
   LEFT JOIN roles r ON u.role_id = r.id
   LEFT JOIN user_permissions up ON u.id = up.user_id
   LEFT JOIN permissions p ON up.permission_id = p.id
   WHERE u.id = 'user-uuid';
   ```

2. Verify permission exists:
   ```sql
   SELECT * FROM permissions WHERE resource = 'staff' AND action = 'create';
   ```

3. Check role permissions:
   ```sql
   SELECT r.name, p.resource, p.action
   FROM roles r
   JOIN role_permissions rp ON r.id = rp.role_id
   JOIN permissions p ON rp.permission_id = p.id
   WHERE r.id = 'role-uuid';
   ```

## Migration Guide

When upgrading existing systems:

1. **Backup Database**: Always backup before making permission changes
2. **Audit Current Access**: Document existing user access patterns
3. **Gradual Migration**: Migrate users in batches, not all at once
4. **Test Thoroughly**: Verify permissions work correctly after migration
5. **Rollback Plan**: Prepare rollback procedures if issues arise

For questions or support with the roles and permissions system, contact the development team or refer to the API documentation.