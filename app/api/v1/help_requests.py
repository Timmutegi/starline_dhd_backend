"""
Help Requests API endpoints for Staff
Allows staff to view and respond to client help requests
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, func
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.client import Client
from app.models.task import Task, TaskStatusEnum, TaskPriorityEnum
from app.models.staff import Staff, StaffAssignment

router = APIRouter()


# Pydantic schemas
class HelpRequestResponse(BaseModel):
    id: UUID
    client_id: UUID
    client_name: str
    request_type: str
    title: str
    description: str
    priority: str
    status: str
    preferred_time: Optional[datetime]
    assigned_to: Optional[UUID]
    assigned_to_name: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    resolved_at: Optional[datetime]
    response: Optional[str]

    class Config:
        from_attributes = True


class HelpRequestUpdate(BaseModel):
    status: Optional[str] = Field(None, description="New status for the request")
    response: Optional[str] = Field(None, description="Staff response to the request")
    assigned_to: Optional[UUID] = Field(None, description="Staff member to assign the request to")


class HelpRequestCountResponse(BaseModel):
    pending_count: int = Field(..., description="Number of pending help requests")
    in_progress_count: int = Field(..., description="Number of in-progress help requests")
    urgent_count: int = Field(..., description="Number of urgent help requests")
    total_active: int = Field(..., description="Total active help requests")


def get_staff_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Verify user is a staff member (not a client) and ensure role is loaded"""
    # Reload user with role if not loaded
    if current_user.role is None:
        user_with_role = db.query(User).options(joinedload(User.role)).filter(User.id == current_user.id).first()
        if user_with_role:
            current_user = user_with_role

    if current_user.role and current_user.role.name.lower() == "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is not accessible to clients"
        )
    return current_user


def _get_help_request_base_query(current_user: User, db: Session):
    """
    Build base query for help requests based on user role.
    Returns (query, is_manager_or_admin) tuple.
    """
    # Base query for help requests
    query = db.query(Task).filter(
        Task.organization_id == current_user.organization_id,
        Task.task_type == "help_request"
    )

    # Check if user is a manager/admin or regular staff
    # Normalize role name: lowercase and replace spaces with underscores
    normalized_role = current_user.role.name.lower().replace(" ", "_") if current_user.role else ""
    manager_roles = ["super_admin", "organization_admin", "admin", "manager", "hr_manager", "supervisor", "billing_admin"]
    is_manager_or_admin = normalized_role in manager_roles

    if not is_manager_or_admin:
        # For regular staff, get their assigned clients
        staff_record = db.query(Staff).filter(Staff.user_id == current_user.id).first()

        if staff_record:
            # Get client IDs from active assignments
            assigned_client_ids = db.query(StaffAssignment.client_id).filter(
                StaffAssignment.staff_id == staff_record.id,
                StaffAssignment.is_active == True
            ).all()
            assigned_client_ids = [c[0] for c in assigned_client_ids]

            if assigned_client_ids:
                query = query.filter(Task.client_id.in_(assigned_client_ids))
            else:
                # No assigned clients, filter to requests assigned to them
                query = query.filter(Task.assigned_to == current_user.id)
        else:
            # User is not a staff member with assignments, show requests assigned to them
            query = query.filter(Task.assigned_to == current_user.id)

    return query, is_manager_or_admin


@router.get("/count", response_model=HelpRequestCountResponse)
async def get_help_request_counts(
    current_user: User = Depends(get_staff_user),
    db: Session = Depends(get_db)
):
    """
    Get counts of help requests for sidebar badge indicator.

    - For managers/admins: Returns counts for all help requests in the organization
    - For staff: Returns counts for help requests from their assigned clients
    """
    query, _ = _get_help_request_base_query(current_user, db)

    # Count pending requests
    pending_count = query.filter(Task.status == TaskStatusEnum.PENDING).count()

    # Count in-progress requests
    in_progress_count = query.filter(Task.status == TaskStatusEnum.IN_PROGRESS).count()

    # Count urgent requests (pending or in_progress with urgent priority)
    urgent_count = query.filter(
        Task.priority == TaskPriorityEnum.URGENT,
        Task.status.in_([TaskStatusEnum.PENDING, TaskStatusEnum.IN_PROGRESS])
    ).count()

    # Total active (pending + in_progress)
    total_active = pending_count + in_progress_count

    return HelpRequestCountResponse(
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        urgent_count=urgent_count,
        total_active=total_active
    )


@router.get("", response_model=List[HelpRequestResponse])
async def get_help_requests(
    status_filter: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_staff_user),
    db: Session = Depends(get_db)
):
    """
    Get help requests from clients.

    - For managers/admins: Returns all help requests in the organization
    - For staff: Returns help requests from clients assigned to them
    """
    # Debug logging
    role_name = current_user.role.name if current_user.role else "No Role"
    print(f"[HelpRequests] User: {current_user.email}, Role: {role_name}, Org: {current_user.organization_id}")

    # Base query for help requests
    query = db.query(Task).options(
        joinedload(Task.client),
        joinedload(Task.assigned_to_user),
        joinedload(Task.created_by_user)
    ).filter(
        Task.organization_id == current_user.organization_id,
        Task.task_type == "help_request"
    )

    # Check if user is a manager/admin or regular staff
    # Normalize role name: lowercase and replace spaces with underscores
    normalized_role = current_user.role.name.lower().replace(" ", "_") if current_user.role else ""
    manager_roles = ["super_admin", "organization_admin", "admin", "manager", "hr_manager", "supervisor", "billing_admin"]
    is_manager_or_admin = normalized_role in manager_roles
    print(f"[HelpRequests] Is manager/admin: {is_manager_or_admin} (normalized role: {normalized_role})")

    if not is_manager_or_admin:
        # For regular staff, get their assigned clients
        staff_record = db.query(Staff).filter(Staff.user_id == current_user.id).first()

        if staff_record:
            # Get client IDs from active assignments
            assigned_client_ids = db.query(StaffAssignment.client_id).filter(
                StaffAssignment.staff_id == staff_record.id,
                StaffAssignment.is_active == True
            ).all()
            assigned_client_ids = [c[0] for c in assigned_client_ids]

            if assigned_client_ids:
                query = query.filter(Task.client_id.in_(assigned_client_ids))
            else:
                # No assigned clients, return empty list
                print(f"[HelpRequests] Staff has no assigned clients, returning empty")
                return []
        else:
            # User is not a staff member with assignments, show requests assigned to them
            query = query.filter(Task.assigned_to == current_user.id)

    # Apply status filter
    if status_filter and status_filter != "all":
        try:
            status_enum = TaskStatusEnum(status_filter)
            query = query.filter(Task.status == status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter

    # Order by priority (urgent first) and creation date
    tasks = query.order_by(
        Task.priority.desc(),
        desc(Task.created_at)
    ).limit(limit).all()

    print(f"[HelpRequests] Found {len(tasks)} help requests")

    # Build response
    result = []
    for task in tasks:
        client_name = "Unknown Client"
        if task.client:
            client_name = task.client.full_name or f"{task.client.first_name} {task.client.last_name}"

        assigned_to_name = None
        if task.assigned_to_user:
            assigned_to_name = f"{task.assigned_to_user.first_name} {task.assigned_to_user.last_name}"

        # Extract request_type from additional_data if available
        request_type = "other"
        if task.additional_data and isinstance(task.additional_data, dict):
            request_type = task.additional_data.get("request_type", "other")

        result.append(HelpRequestResponse(
            id=task.id,
            client_id=task.client_id,
            client_name=client_name,
            request_type=request_type,
            title=task.title,
            description=task.description or "",
            priority=task.priority.value if task.priority else "medium",
            status=task.status.value if task.status else "pending",
            preferred_time=task.due_date,
            assigned_to=task.assigned_to,
            assigned_to_name=assigned_to_name,
            created_at=task.created_at,
            updated_at=task.updated_at,
            resolved_at=task.completed_at,
            response=task.notes,
        ))

    return result


@router.get("/{request_id}", response_model=HelpRequestResponse)
async def get_help_request(
    request_id: UUID,
    current_user: User = Depends(get_staff_user),
    db: Session = Depends(get_db)
):
    """Get a specific help request by ID"""
    task = db.query(Task).options(
        joinedload(Task.client),
        joinedload(Task.assigned_to_user)
    ).filter(
        Task.id == request_id,
        Task.organization_id == current_user.organization_id,
        Task.task_type == "help_request"
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Help request not found"
        )

    client_name = "Unknown Client"
    if task.client:
        client_name = task.client.full_name or f"{task.client.first_name} {task.client.last_name}"

    assigned_to_name = None
    if task.assigned_to_user:
        assigned_to_name = f"{task.assigned_to_user.first_name} {task.assigned_to_user.last_name}"

    request_type = "other"
    if task.additional_data and isinstance(task.additional_data, dict):
        request_type = task.additional_data.get("request_type", "other")

    return HelpRequestResponse(
        id=task.id,
        client_id=task.client_id,
        client_name=client_name,
        request_type=request_type,
        title=task.title,
        description=task.description or "",
        priority=task.priority.value if task.priority else "medium",
        status=task.status.value if task.status else "pending",
        preferred_time=task.due_date,
        assigned_to=task.assigned_to,
        assigned_to_name=assigned_to_name,
        created_at=task.created_at,
        updated_at=task.updated_at,
        resolved_at=task.completed_at,
        response=task.notes,
    )


@router.put("/{request_id}", response_model=HelpRequestResponse)
async def update_help_request(
    request_id: UUID,
    update_data: HelpRequestUpdate,
    current_user: User = Depends(get_staff_user),
    db: Session = Depends(get_db)
):
    """
    Update a help request (status, response, assignment).
    Staff can update requests assigned to them or from their assigned clients.
    Managers/admins can update any request in their organization.
    """
    task = db.query(Task).options(
        joinedload(Task.client),
        joinedload(Task.assigned_to_user)
    ).filter(
        Task.id == request_id,
        Task.organization_id == current_user.organization_id,
        Task.task_type == "help_request"
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Help request not found"
        )

    # Update status if provided
    if update_data.status:
        try:
            task.status = TaskStatusEnum(update_data.status)
            if update_data.status == "completed":
                task.completed_at = datetime.now(timezone.utc)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {update_data.status}"
            )

    # Update response/notes if provided
    if update_data.response is not None:
        task.notes = update_data.response

    # Update assignment if provided
    if update_data.assigned_to:
        # Verify the user exists and is in the same organization
        assigned_user = db.query(User).filter(
            User.id == update_data.assigned_to,
            User.organization_id == current_user.organization_id
        ).first()

        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned user not found in organization"
            )

        task.assigned_to = update_data.assigned_to

    task.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(task)

    # Reload relationships
    task = db.query(Task).options(
        joinedload(Task.client),
        joinedload(Task.assigned_to_user)
    ).filter(Task.id == request_id).first()

    client_name = "Unknown Client"
    if task.client:
        client_name = task.client.full_name or f"{task.client.first_name} {task.client.last_name}"

    assigned_to_name = None
    if task.assigned_to_user:
        assigned_to_name = f"{task.assigned_to_user.first_name} {task.assigned_to_user.last_name}"

    request_type = "other"
    if task.additional_data and isinstance(task.additional_data, dict):
        request_type = task.additional_data.get("request_type", "other")

    return HelpRequestResponse(
        id=task.id,
        client_id=task.client_id,
        client_name=client_name,
        request_type=request_type,
        title=task.title,
        description=task.description or "",
        priority=task.priority.value if task.priority else "medium",
        status=task.status.value if task.status else "pending",
        preferred_time=task.due_date,
        assigned_to=task.assigned_to,
        assigned_to_name=assigned_to_name,
        created_at=task.created_at,
        updated_at=task.updated_at,
        resolved_at=task.completed_at,
        response=task.notes,
    )
