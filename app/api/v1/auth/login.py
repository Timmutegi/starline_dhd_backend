from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, timezone
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token, generate_otp, hash_otp
from app.models.user import User, UserSession, AuthAuditLog, UserStatus, Role, Permission
from app.schemas.auth import LoginRequest, LoginResponse, OTPVerification, PermissionInfo, RoleInfo
from app.schemas.user import UserResponse
from app.core.config import settings
from app.services.email_service import EmailService
import json

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).options(
        joinedload(User.role).joinedload(Role.permissions)
    ).filter(
        (User.email == login_data.email) | (User.username == login_data.email)
    ).first()

    if not user:
        db.add(AuthAuditLog(
            action="login_failed",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            success=False,
            error_message="User not found",
            metadata=json.dumps({"email": login_data.email})
        ))
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if user.lockout_until and user.lockout_until > datetime.now(timezone.utc):
        remaining_time = (user.lockout_until - datetime.now(timezone.utc)).total_seconds() / 60
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is locked. Try again in {int(remaining_time)} minutes"
        )

    if not verify_password(login_data.password, user.password_hash):
        user.failed_login_attempts += 1

        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.lockout_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
            await EmailService.send_account_locked_email(
                user.email,
                user.full_name,
                user.lockout_until.strftime("%Y-%m-%d %H:%M:%S UTC")
            )

        db.add(AuthAuditLog(
            user_id=user.id,
            action="login_failed",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            success=False,
            error_message="Incorrect password",
            metadata=json.dumps({"attempts": user.failed_login_attempts})
        ))
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status.value}"
        )

    if not user.email_verified:
        otp = generate_otp()
        user.email_verification_otp = hash_otp(otp)
        user.email_verification_otp_expires = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        db.commit()

        verification_link = f"{settings.FRONTEND_URL}/verify-email?email={user.email}"
        await EmailService.send_verification_email(user.email, otp, verification_link)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Verification code sent to your email."
        )

    user.failed_login_attempts = 0
    user.lockout_until = None
    user.last_login = datetime.now(timezone.utc)

    if login_data.remember_me:
        access_token_expires = timedelta(days=settings.REMEMBER_ME_DAYS)
    else:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(user.id, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(user.id)

    session_expires = datetime.now(timezone.utc) + (
        timedelta(days=settings.REMEMBER_ME_DAYS) if login_data.remember_me
        else timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    )

    session = UserSession(
        user_id=user.id,
        token=access_token,
        refresh_token=refresh_token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        is_remember_me=login_data.remember_me,
        expires_at=session_expires
    )
    db.add(session)

    db.add(AuthAuditLog(
        user_id=user.id,
        action="login_success",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        success=True
    ))
    db.commit()

    user_response = UserResponse.model_validate(user)

    # Extract role and permissions information
    role_info = None
    permissions_list = []

    if user.role:
        # Build permissions list for the role
        role_permissions = []
        for permission in user.role.permissions:
            role_permissions.append(PermissionInfo(
                resource=permission.resource,
                action=permission.action,
                description=permission.description
            ))
            permissions_list.append(f"{permission.resource}:{permission.action}")

        role_info = RoleInfo(
            id=user.role.id,
            name=user.role.name,
            description=user.role.description,
            is_system_role=user.role.is_system_role,
            permissions=role_permissions
        )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        user=user_response.model_dump(),
        role=role_info,
        permissions=permissions_list,
        must_change_password=user.must_change_password
    )

@router.post("/verify-email-otp")
async def verify_email_otp(
    request: Request,
    verification_data: OTPVerification,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == verification_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )

    if not user.email_verification_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification code found. Please request a new one."
        )

    if user.email_verification_otp_expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one."
        )

    from app.core.security import verify_otp
    if not verify_otp(verification_data.otp, user.email_verification_otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )

    user.email_verified = True
    user.email_verification_otp = None
    user.email_verification_otp_expires = None

    if user.status == UserStatus.PENDING:
        user.status = UserStatus.ACTIVE

    db.add(AuthAuditLog(
        user_id=user.id,
        action="email_verified",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        success=True
    ))
    db.commit()

    await EmailService.send_welcome_email(
        user.email,
        user.full_name,
        user.organization.name if user.organization else "Starline"
    )

    return {"message": "Email verified successfully", "success": True}