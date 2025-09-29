from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from app.core.database import get_db
from app.models.user import User, Role, Permission
from app.middleware.auth import get_current_user, require_permission
from app.schemas.user import (
    RoleCreate,
    RoleUpdate,
    RoleWithPermissions,
    PermissionInDB
)
from app.schemas.auth import MessageResponse
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[RoleWithPermissions])
async def list_roles(
    include_system: bool = Query(False, description="Include system roles"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "read"))
):
    """List all roles available to the organization."""

    query = db.query(Role).options(joinedload(Role.permissions))

    if include_system:
        # Include both organization-specific and system roles
        query = query.filter(
            (Role.organization_id == current_user.organization_id) |
            (Role.is_system_role == True)
        )
    else:
        # Only organization-specific roles
        query = query.filter(Role.organization_id == current_user.organization_id)

    roles = query.all()
    return [RoleWithPermissions.model_validate(role) for role in roles]

@router.get("/{role_id}", response_model=RoleWithPermissions)
async def get_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "read"))
):
    """Get role details by ID."""

    role = db.query(Role).options(joinedload(Role.permissions)).filter(
        Role.id == role_id,
        ((Role.organization_id == current_user.organization_id) | (Role.is_system_role == True))
    ).first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return RoleWithPermissions.model_validate(role)

@router.post("/", response_model=RoleWithPermissions)
async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "create"))
):
    """Create a new custom role for the organization."""

    # Check if role name already exists in the organization
    existing_role = db.query(Role).filter(
        Role.name == role_data.name,
        Role.organization_id == current_user.organization_id
    ).first()

    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A role with this name already exists"
        )

    # Validate permissions if provided
    permissions = []
    if role_data.permission_ids:
        permissions = db.query(Permission).filter(
            Permission.id.in_(role_data.permission_ids)
        ).all()
        if len(permissions) != len(role_data.permission_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more permissions not found"
            )

    try:
        # Create the role
        new_role = Role(
            name=role_data.name,
            description=role_data.description,
            organization_id=current_user.organization_id,
            is_system_role=False
        )

        db.add(new_role)
        db.flush()  # Get the role ID

        # Assign permissions
        if permissions:
            new_role.permissions = permissions

        db.commit()
        db.refresh(new_role)

        # Load with permissions for response
        role_with_perms = db.query(Role).options(
            joinedload(Role.permissions)
        ).filter(Role.id == new_role.id).first()

        return RoleWithPermissions.model_validate(role_with_perms)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create role"
        )

@router.put("/{role_id}", response_model=RoleWithPermissions)
async def update_role(
    role_id: UUID,
    role_update: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "update"))
):
    """Update a custom role."""

    role = db.query(Role).filter(
        Role.id == role_id,
        Role.organization_id == current_user.organization_id,
        Role.is_system_role == False  # Only allow updating custom roles
    ).first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found or is a system role"
        )

    try:
        # Update role fields
        if role_update.name is not None:
            # Check for name conflicts
            existing_role = db.query(Role).filter(
                Role.name == role_update.name,
                Role.organization_id == current_user.organization_id,
                Role.id != role_id
            ).first()

            if existing_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A role with this name already exists"
                )

            role.name = role_update.name

        if role_update.description is not None:
            role.description = role_update.description

        # Update permissions if provided
        if role_update.permission_ids is not None:
            if role_update.permission_ids:
                permissions = db.query(Permission).filter(
                    Permission.id.in_(role_update.permission_ids)
                ).all()
                if len(permissions) != len(role_update.permission_ids):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="One or more permissions not found"
                    )
                role.permissions = permissions
            else:
                # Clear all permissions
                role.permissions = []

        role.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(role)

        # Load with permissions for response
        role_with_perms = db.query(Role).options(
            joinedload(Role.permissions)
        ).filter(Role.id == role.id).first()

        return RoleWithPermissions.model_validate(role_with_perms)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update role"
        )

@router.delete("/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "delete"))
):
    """Delete a custom role."""

    role = db.query(Role).filter(
        Role.id == role_id,
        Role.organization_id == current_user.organization_id,
        Role.is_system_role == False  # Only allow deleting custom roles
    ).first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found or is a system role"
        )

    # Check if role is still assigned to users
    users_with_role = db.query(User).filter(User.role_id == role_id).first()
    if users_with_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete role that is still assigned to users"
        )

    try:
        db.delete(role)
        db.commit()

        return MessageResponse(
            message=f"Role '{role.name}' deleted successfully",
            success=True
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete role"
        )

@router.get("/permissions/all", response_model=List[PermissionInDB])
async def list_all_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles", "read"))
):
    """List all available permissions."""

    permissions = db.query(Permission).order_by(Permission.resource, Permission.action).all()
    return [PermissionInDB.model_validate(perm) for perm in permissions]