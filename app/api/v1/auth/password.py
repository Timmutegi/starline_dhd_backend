from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    generate_password_reset_token,
    verify_password_reset_token,
    generate_otp,
    hash_otp,
    verify_otp,
    validate_password
)
from app.models.user import User, AuthAuditLog, PasswordHistory
from app.middleware.auth import get_current_user
from app.schemas.auth import (
    PasswordResetRequest,
    PasswordResetConfirm,
    MessageResponse,
    OTPVerification
)
from app.schemas.user import ChangePassword
from app.services.email_service import EmailService
from app.core.config import settings

router = APIRouter()

@router.post("/password/reset-request", response_model=MessageResponse)
async def request_password_reset(
    request: Request,
    reset_data: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == reset_data.email).first()

    if not user:
        return MessageResponse(
            message="If an account exists with this email, a password reset link has been sent.",
            success=True
        )

    otp = generate_otp()
    reset_token = generate_password_reset_token(user.email)

    user.password_reset_token = reset_token
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    user.email_verification_otp = hash_otp(otp)
    user.email_verification_otp_expires = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    db.add(AuthAuditLog(
        user_id=user.id,
        action="password_reset_requested",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        success=True
    ))
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    await EmailService.send_password_reset_email(
        user.email,
        otp,
        reset_link,
        user.full_name
    )

    return MessageResponse(
        message="If an account exists with this email, a password reset link has been sent.",
        success=True
    )

@router.post("/password/verify-otp", response_model=MessageResponse)
async def verify_reset_otp(
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

    if not user.email_verification_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP found. Please request a password reset first."
        )

    if user.email_verification_otp_expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new password reset."
        )

    if not verify_otp(verification_data.otp, user.email_verification_otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )

    return MessageResponse(
        message="OTP verified successfully. You can now reset your password.",
        success=True
    )

@router.post("/password/reset-confirm", response_model=MessageResponse)
async def reset_password(
    request: Request,
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    email = verify_password_reset_token(reset_data.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.password_reset_token != reset_data.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )

    if user.password_reset_expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )

    is_valid, message = validate_password(reset_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    recent_passwords = db.query(PasswordHistory).filter(
        PasswordHistory.user_id == user.id
    ).order_by(PasswordHistory.created_at.desc()).limit(5).all()

    for old_password in recent_passwords:
        if verify_password(reset_data.new_password, old_password.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot use any of your last 5 passwords"
            )

    new_password_hash = get_password_hash(reset_data.new_password)

    db.add(PasswordHistory(
        user_id=user.id,
        password_hash=user.password_hash
    ))

    user.password_hash = new_password_hash
    user.password_reset_token = None
    user.password_reset_expires = None
    user.email_verification_otp = None
    user.email_verification_otp_expires = None
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False  # Clear mandatory password change flag

    db.add(AuthAuditLog(
        user_id=user.id,
        action="password_reset_completed",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        success=True
    ))
    db.commit()

    await EmailService.send_password_changed_email(user.email, user.full_name)

    return MessageResponse(
        message="Password reset successfully",
        success=True
    )

@router.post("/password/change", response_model=MessageResponse)
async def change_password(
    request: Request,
    password_data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    is_valid, message = validate_password(password_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    recent_passwords = db.query(PasswordHistory).filter(
        PasswordHistory.user_id == current_user.id
    ).order_by(PasswordHistory.created_at.desc()).limit(5).all()

    for old_password in recent_passwords:
        if verify_password(password_data.new_password, old_password.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot use any of your last 5 passwords"
            )

    new_password_hash = get_password_hash(password_data.new_password)

    db.add(PasswordHistory(
        user_id=current_user.id,
        password_hash=current_user.password_hash
    ))

    current_user.password_hash = new_password_hash
    current_user.password_changed_at = datetime.now(timezone.utc)
    current_user.must_change_password = False  # Clear mandatory password change flag

    db.add(AuthAuditLog(
        user_id=current_user.id,
        action="password_changed",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        success=True
    ))
    db.commit()

    await EmailService.send_password_changed_email(current_user.email, current_user.full_name)

    return MessageResponse(
        message="Password changed successfully",
        success=True
    )