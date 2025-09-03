# White Labeling - Design Document

## Overview
Multi-tenant architecture enabling complete white-label customization for different organizations with isolated data and branding.

## Database Schema
```sql
-- Organizations (Enhanced)
organizations:
  - id: UUID (PK)
  - name: VARCHAR(255)
  - subdomain: VARCHAR(100) UNIQUE
  - custom_domain: VARCHAR(255)
  - logo_url: TEXT
  - favicon_url: TEXT
  - primary_color: VARCHAR(7)
  - secondary_color: VARCHAR(7)
  - font_family: VARCHAR(100)
  - white_label_config: JSONB
  - feature_flags: JSONB
  - billing_settings: JSONB

-- Custom Themes
custom_themes:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - theme_name: VARCHAR(255)
  - css_variables: JSONB
  - custom_css: TEXT
  - is_active: BOOLEAN

-- Email Templates (Organization-specific)
org_email_templates:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - template_type: VARCHAR(100)
  - subject: VARCHAR(255)
  - html_content: TEXT
  - text_content: TEXT
  - variables: JSONB

-- Feature Configurations
feature_configurations:
  - id: UUID (PK)
  - organization_id: UUID (FK)
  - feature_name: VARCHAR(255)
  - is_enabled: BOOLEAN
  - configuration: JSONB
```

## API Endpoints
- `GET /api/v1/organizations/{id}/branding` - Get branding config
- `PUT /api/v1/organizations/{id}/branding` - Update branding
- `GET /api/v1/organizations/{id}/themes` - List themes
- `POST /api/v1/organizations/{id}/themes` - Create theme
- `GET /api/v1/organizations/{id}/features` - Feature configuration

## Key Features
- Complete data isolation between organizations
- Custom branding (logos, colors, fonts, CSS)
- Subdomain and custom domain support
- Organization-specific email templates
- Feature toggles per organization
- Custom workflows and forms
- White-label mobile apps
- Billing isolation and configuration