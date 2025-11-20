from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Union, List
from app.core.database import get_db
from app.models.user import User, UserStatus
from app.core.config import settings
from jose import JWTError, jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is {user.status.value}"
        )

    return user

def require_role(allowed_roles: List[str]):
    """Dependency factory for role-based access control"""
    async def role_checker(current_user: User = Depends(get_current_user)):
        if not current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No role assigned to user"
            )

        # Normalize role names for comparison (handle spaces vs underscores)
        user_role_normalized = current_user.role.name.lower().replace(" ", "_")
        normalized_allowed_roles = [role.lower().replace(" ", "_") for role in allowed_roles]

        if user_role_normalized not in normalized_allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}"
            )

        return current_user

    return role_checker

async def get_super_admin(current_user: User = Depends(require_role(["super_admin"]))):
    """Dependency for super admin only access"""
    return current_user

async def get_admin_or_above(current_user: User = Depends(require_role(["super_admin", "organization_admin", "billing_admin"]))):
    """Dependency for admin level access and above"""
    return current_user

async def get_manager_or_above(current_user: User = Depends(require_role(["super_admin", "organization_admin", "billing_admin", "hr_manager", "manager", "supervisor"]))):
    """Dependency for manager level access and above"""
    return current_user

async def get_staff_or_above(current_user: User = Depends(require_role(["super_admin", "organization_admin", "billing_admin", "hr_manager", "manager", "supervisor", "support_staff", "staff"]))):
    """Dependency for staff level access and above"""
    return current_user