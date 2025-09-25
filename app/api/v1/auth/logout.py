from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.core.database import get_db
from app.models.user import User, UserSession, AuthAuditLog
from app.middleware.auth import get_current_user
from app.schemas.auth import MessageResponse

router = APIRouter()

@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )

    token = auth_header.split(" ")[1] if " " in auth_header else auth_header

    session = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.token == token,
        UserSession.revoked_at.is_(None)
    ).first()

    if session:
        session.revoked_at = datetime.now(timezone.utc)
        db.add(AuthAuditLog(
            user_id=current_user.id,
            action="logout",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            success=True
        ))
        db.commit()

    return MessageResponse(message="Logged out successfully", success=True)

@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.revoked_at.is_(None)
    ).all()

    for session in sessions:
        session.revoked_at = datetime.now(timezone.utc)

    db.add(AuthAuditLog(
        user_id=current_user.id,
        action="logout_all",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        success=True,
        metadata=f"Revoked {len(sessions)} sessions"
    ))
    db.commit()

    return MessageResponse(
        message=f"Logged out from {len(sessions)} devices successfully",
        success=True
    )