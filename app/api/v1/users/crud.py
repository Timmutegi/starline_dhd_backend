from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from app.core.database import get_db
from app.core.security import get_password_hash, generate_otp, hash_otp, generate_random_password
from app.models.user import User, Organization, Role, UserStatus
from app.middleware.auth import get_current_user, require_permission
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserInDB
)
from app.schemas.auth import MessageResponse
from app.services.email_service import EmailService
from app.core.config import settings
from datetime import datetime, timedelta, timezone

router = APIRouter()

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "create"))
):
    existing_user = db.query(User).filter(
        (User.email == user_data.email) |
        (User.username == user_data.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )

    if user_data.organization_id:
        organization = db.query(Organization).filter(
            Organization.id == user_data.organization_id
        ).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
    else:
        organization_id = current_user.organization_id

    if user_data.role_id:
        role = db.query(Role).filter(Role.id == user_data.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

    password_hash = get_password_hash(user_data.password)

    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=password_hash,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        employee_id=user_data.employee_id,
        hire_date=user_data.hire_date,
        organization_id=user_data.organization_id or current_user.organization_id,
        role_id=user_data.role_id,
        status=UserStatus.PENDING
    )

    otp = generate_otp()
    new_user.email_verification_otp = hash_otp(otp)
    new_user.email_verification_otp_expires = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    verification_link = f"{settings.FRONTEND_URL}/verify-email?email={new_user.email}"
    await EmailService.send_verification_email(new_user.email, otp, verification_link)

    return UserResponse.model_validate(new_user)

@router.get("/", response_model=List[UserResponse])
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[UserStatus] = None,
    organization_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read"))
):
    query = db.query(User)

    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    elif not current_user.role or not current_user.role.is_system_role:
        query = query.filter(User.organization_id == current_user.organization_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.email.ilike(search_pattern)) |
            (User.first_name.ilike(search_pattern)) |
            (User.last_name.ilike(search_pattern)) |
            (User.username.ilike(search_pattern))
        )

    if status:
        query = query.filter(User.status == status)

    users = query.offset(skip).limit(limit).all()
    return [UserResponse.model_validate(user) for user in users]

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read"))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if (not current_user.role or not current_user.role.is_system_role) and \
       user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access users from other organizations"
        )

    return UserResponse.model_validate(user)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "update"))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if (not current_user.role or not current_user.role.is_system_role) and \
       user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update users from other organizations"
        )

    if user_update.email and user_update.email != user.email:
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )

    if user_update.username and user_update.username != user.username:
        existing_user = db.query(User).filter(User.username == user_update.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already in use"
            )

    if user_update.role_id:
        role = db.query(Role).filter(Role.id == user_update.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)

@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "delete"))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if (not current_user.role or not current_user.role.is_system_role) and \
       user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete users from other organizations"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    db.delete(user)
    db.commit()

    return MessageResponse(
        message="User deleted successfully",
        success=True
    )

@router.post("/{user_id}/activate", response_model=MessageResponse)
async def activate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "update"))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if (not current_user.role or not current_user.role.is_system_role) and \
       user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot activate users from other organizations"
        )

    user.status = UserStatus.ACTIVE
    user.updated_at = datetime.now(timezone.utc)
    db.commit()

    return MessageResponse(
        message="User activated successfully",
        success=True
    )

@router.post("/{user_id}/deactivate", response_model=MessageResponse)
async def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "update"))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if (not current_user.role or not current_user.role.is_system_role) and \
       user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate users from other organizations"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    user.status = UserStatus.INACTIVE
    user.updated_at = datetime.now(timezone.utc)
    db.commit()

    return MessageResponse(
        message="User deactivated successfully",
        success=True
    )

@router.post("/{user_id}/reset-password", response_model=MessageResponse)
async def admin_reset_password(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "update"))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if (not current_user.role or not current_user.role.is_system_role) and \
       user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot reset password for users from other organizations"
        )

    new_password = generate_random_password()
    user.password_hash = get_password_hash(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()

    await EmailService.send_password_changed_email(user.email, user.full_name)

    return MessageResponse(
        message=f"Password reset successfully. New password: {new_password}",
        success=True
    )