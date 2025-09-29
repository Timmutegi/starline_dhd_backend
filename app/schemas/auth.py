from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False

class PermissionInfo(BaseModel):
    resource: str
    action: str
    description: Optional[str] = None

class RoleInfo(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_system_role: bool
    permissions: List[PermissionInfo]

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict
    role: Optional[RoleInfo] = None
    permissions: List[str] = []  # List of "resource:action" strings for easy checking
    must_change_password: bool = False

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)

class EmailVerificationRequest(BaseModel):
    token: Optional[str] = None
    otp: Optional[str] = None

class TwoFactorSetup(BaseModel):
    enabled: bool

class TwoFactorVerify(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)

class SessionInfo(BaseModel):
    id: UUID
    user_id: UUID
    ip_address: Optional[str]
    user_agent: Optional[str]
    device_name: Optional[str]
    created_at: datetime
    expires_at: datetime
    is_current: bool = False

class TokenPayload(BaseModel):
    sub: str
    exp: int
    type: str

class MessageResponse(BaseModel):
    message: str
    success: bool = True

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int

class OTPRequest(BaseModel):
    email: EmailStr

class OTPVerification(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)