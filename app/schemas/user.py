from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum
import re

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"

class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    subdomain: str = Field(..., min_length=3, max_length=100, pattern="^[a-z0-9-]+$")
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    timezone: str = Field(default="UTC", max_length=50)
    primary_color: str = Field(default="#4F46E5", pattern="^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(default="#FFFFFF", pattern="^#[0-9A-Fa-f]{6}$")

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    timezone: Optional[str] = Field(None, max_length=50)
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")

class OrganizationInDB(OrganizationBase):
    id: UUID
    logo_url: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    employee_id: Optional[str] = Field(None, max_length=50)
    hire_date: Optional[datetime] = None
    timezone: Optional[str] = Field(None, max_length=50)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)
    organization_id: Optional[UUID] = None
    role_id: Optional[UUID] = None

    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"[a-z]", v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};:,.<>?]", v):
            raise ValueError('Password must contain at least one special character')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    employee_id: Optional[str] = Field(None, max_length=50)
    hire_date: Optional[datetime] = None
    status: Optional[UserStatus] = None
    role_id: Optional[UUID] = None

class UserInDB(UserBase):
    id: UUID
    organization_id: Optional[UUID]
    status: UserStatus
    email_verified: bool
    two_factor_enabled: bool
    profile_picture_url: Optional[str]
    role_id: Optional[UUID]
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserResponse(UserInDB):
    organization: Optional[OrganizationInDB] = None
    role_name: Optional[str] = None
    user_type: Optional[str] = None  # 'staff', 'client', or 'admin'

    class Config:
        from_attributes = True

class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"[a-z]", v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};:,.<>?]", v):
            raise ValueError('Password must contain at least one special character')
        return v

class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

class RoleCreate(RoleBase):
    organization_id: Optional[UUID] = None
    permission_ids: List[UUID] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    permission_ids: Optional[List[UUID]] = None

class RoleInDB(RoleBase):
    id: UUID
    organization_id: Optional[UUID]
    is_system_role: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PermissionBase(BaseModel):
    resource: str = Field(..., min_length=1, max_length=100)
    action: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class PermissionInDB(PermissionBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class RoleWithPermissions(RoleInDB):
    permissions: List[PermissionInDB] = []