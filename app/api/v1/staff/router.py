from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from typing import List, Optional
from uuid import UUID
from app.core.database import get_db
from app.core.security import get_password_hash, generate_random_password
from app.models.user import User, Organization, Role, UserStatus, Permission
from app.models.staff import Staff, EmploymentStatus, StaffAssignment, AssignmentType
from app.models.client import Client
from app.schemas.client import ClientResponse
from app.middleware.auth import get_current_user, require_permission
from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    StaffResponse,
    StaffCreateResponse,
    StaffSummary,
    StaffListResponse,
    StaffPermissionUpdate,
    PermissionAssignmentResponse,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentResponse,
    TimeOffRequestCreate,
    TimeOffRequestResponse
)
from app.models.staff import TimeOffRequest, TimeOffStatus, TimeOffType
from app.models.scheduling import Shift, ShiftExchangeRequest, ShiftExchangeStatus, ShiftStatus
from app.schemas.scheduling import (
    ShiftExchangeRequestCreate,
    ShiftExchangeRequestPeerResponse,
    ShiftExchangeRequestResponse,
    StaffShiftInfo,
    ColleagueShiftResponse
)
from app.models.location import Location
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.auth import MessageResponse
from app.services.email_service import EmailService
from app.core.config import settings
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def generate_username(first_name: str, last_name: str, db: Session) -> str:
    """Generate a unique username based on first and last name."""
    base_username = f"{first_name.lower()}.{last_name.lower()}"
    username = base_username
    counter = 1

    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1

    return username

def generate_employee_id(organization_id: UUID, db: Session) -> str:
    """Generate a unique employee ID for the organization."""
    # Get organization to potentially use prefix
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    org_prefix = org.name[:3].upper() if org else "EMP"

    # Find the highest existing employee ID for this organization
    existing_staff = db.query(Staff).filter(
        Staff.organization_id == organization_id
    ).order_by(Staff.employee_id.desc()).first()

    if existing_staff and existing_staff.employee_id:
        try:
            # Extract number from existing ID (assuming format like "ABC001")
            existing_num = int(existing_staff.employee_id[-3:])
            new_num = existing_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1

    return f"{org_prefix}{new_num:03d}"


@router.get("/roles/assignable")
async def get_assignable_staff_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get roles that can be assigned to staff members.
    Available to managers and admins for populating role dropdowns when creating staff.
    Returns only staff-appropriate roles (Support Staff for now).
    """
    # Define staff-assignable role names
    # For now, only Support Staff as requested
    assignable_role_names = ["Support Staff"]

    # Query roles that match these names and are either system roles or belong to the organization
    roles = db.query(Role).filter(
        Role.name.in_(assignable_role_names),
        (
            (Role.organization_id == current_user.organization_id) |
            (Role.is_system_role == True)
        )
    ).all()

    # Return simple role objects with id and name
    return [{"id": str(role.id), "name": role.name} for role in roles]


@router.post("/", response_model=StaffCreateResponse)
async def create_staff(
    staff_data: StaffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "create"))
):
    """Create a new staff member with auto-generated password and send credentials via email."""

    try:
        # Check if user with email already exists
        existing_user = db.query(User).filter(User.email == staff_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )

        # Auto-generate employee ID if not provided
        employee_id = staff_data.employee_id
        if not employee_id:
            employee_id = generate_employee_id(current_user.organization_id, db)
        else:
            # Check if employee ID already exists only if one was provided
            existing_staff = db.query(Staff).filter(
                Staff.employee_id == employee_id,
                Staff.organization_id == current_user.organization_id
            ).first()
            if existing_staff:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An employee with this ID already exists"
                )

        # Validate role
        role = db.query(Role).filter(Role.id == staff_data.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        # Validate custom permissions if provided
        custom_permissions = []
        if staff_data.use_custom_permissions and staff_data.custom_permission_ids:
            custom_permissions = db.query(Permission).filter(
                Permission.id.in_(staff_data.custom_permission_ids)
            ).all()
            if len(custom_permissions) != len(staff_data.custom_permission_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more permissions not found"
                )

        # Validate supervisor if provided
        supervisor = None
        if staff_data.supervisor_id:
            supervisor = db.query(Staff).filter(
                Staff.id == staff_data.supervisor_id,
                Staff.organization_id == current_user.organization_id
            ).first()
            if not supervisor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supervisor not found"
                )

        # Generate username and password
        username = generate_username(staff_data.first_name, staff_data.last_name, db)
        temporary_password = generate_random_password(12)
        password_hash = get_password_hash(temporary_password)

        # Create User account
        new_user = User(
            email=staff_data.email,
            username=username,
            password_hash=password_hash,
            first_name=staff_data.first_name,
            last_name=staff_data.last_name,
            phone=staff_data.phone,
            organization_id=current_user.organization_id,
            role_id=staff_data.role_id,
            status=UserStatus.ACTIVE,  # Staff are active immediately
            email_verified=True,  # Skip email verification for staff
            must_change_password=True,  # Force password change on first login
            use_custom_permissions=staff_data.use_custom_permissions
        )

        db.add(new_user)
        db.flush()  # Get the user ID

        # Create Staff record
        new_staff = Staff(
            user_id=new_user.id,
            organization_id=current_user.organization_id,
            employee_id=employee_id,  # Use the generated or provided employee_id
            middle_name=staff_data.middle_name,
            preferred_name=staff_data.preferred_name,
            mobile_phone=staff_data.mobile_phone,
            date_of_birth=staff_data.date_of_birth,
            address=staff_data.address,
            city=staff_data.city,
            state=staff_data.state,
            zip_code=staff_data.zip_code,
            hire_date=staff_data.hire_date,
            employment_status=staff_data.employment_status,
            department=staff_data.department,
            job_title=staff_data.job_title,
            supervisor_id=staff_data.supervisor_id,
            hourly_rate=staff_data.hourly_rate,
            salary=staff_data.salary,
            pay_type=staff_data.pay_type,
            fte_percentage=staff_data.fte_percentage,
            notes=staff_data.notes,
            created_by=current_user.id
        )

        db.add(new_staff)
        db.flush()  # Get the staff ID

        # Assign custom permissions if provided
        if staff_data.use_custom_permissions and custom_permissions:
            new_user.custom_permissions = custom_permissions

        db.commit()
        db.refresh(new_staff)

        # Load relationships for response
        staff_with_relations = db.query(Staff).options(
            joinedload(Staff.user),
            joinedload(Staff.supervisor)
        ).filter(Staff.id == new_staff.id).first()

        # Get organization info for email
        organization = db.query(Organization).filter(
            Organization.id == current_user.organization_id
        ).first()

        # Send credentials email
        try:
            await EmailService.send_staff_credentials(
                email=staff_data.email,
                full_name=f"{staff_data.first_name} {staff_data.last_name}",
                username=username,
                password=temporary_password,
                employee_id=staff_data.employee_id,
                organization_name=organization.name if organization else "Starline",
                role_name=role.name,
                department=staff_data.department,
                hire_date=staff_data.hire_date.strftime("%B %d, %Y") if staff_data.hire_date else None,
                supervisor_name=supervisor.full_name if supervisor else None,
                supervisor_email=supervisor.user.email if supervisor and supervisor.user else None,
                support_email=organization.contact_email if organization else settings.DEFAULT_ADMIN_EMAIL,
                support_phone=organization.contact_phone if organization else None
            )

            logger.info(f"Staff credentials email sent successfully to {staff_data.email}")

        except Exception as email_error:
            logger.error(f"Failed to send staff credentials email: {str(email_error)}")
            # Don't fail the staff creation if email fails

        return StaffCreateResponse(
            staff=StaffResponse.model_validate(staff_with_relations),
            temporary_password=temporary_password,
            message="Staff member created successfully and credentials sent via email",
            success=True
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating staff: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create staff member"
        )

@router.get("/", response_model=PaginatedResponse[StaffSummary])
async def get_staff_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    employment_status: Optional[EmploymentStatus] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "read"))
):
    """Get list of staff members with pagination and filtering."""

    query = db.query(Staff).options(
        joinedload(Staff.user).joinedload(User.role)
    ).filter(Staff.organization_id == current_user.organization_id)

    # Apply filters
    if search:
        search_pattern = f"%{search}%"
        query = query.join(User).filter(
            (User.first_name.ilike(search_pattern)) |
            (User.last_name.ilike(search_pattern)) |
            (User.email.ilike(search_pattern)) |
            (Staff.employee_id.ilike(search_pattern))
        )

    if employment_status:
        query = query.filter(Staff.employment_status == employment_status)

    if department:
        query = query.filter(Staff.department.ilike(f"%{department}%"))

    # Get total count for pagination
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    staff_list = query.offset(offset).limit(page_size).all()

    # Convert to summary format
    staff_summaries = []
    for staff in staff_list:
        # Get role name from user's role
        role_name = None
        if staff.user and staff.user.role:
            role_name = staff.user.role.name

        staff_summaries.append(StaffSummary(
            id=staff.id,
            employee_id=staff.employee_id,
            full_name=staff.full_name,
            display_name=staff.display_name,
            email=staff.user.email,
            job_title=staff.job_title,
            position=staff.job_title,  # Add position field (alias for job_title)
            department=staff.department,
            employment_status=staff.employment_status.value if hasattr(staff.employment_status, 'value') else str(staff.employment_status),
            hire_date=staff.hire_date,
            last_login=staff.user.last_login,
            role_name=role_name
        ))

    # Calculate total pages
    pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        data=staff_summaries,
        pagination=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            pages=pages
        )
    )

@router.get("/{staff_id}", response_model=StaffResponse)
async def get_staff(
    staff_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "read"))
):
    """Get detailed staff information."""

    staff = db.query(Staff).options(
        joinedload(Staff.user),
        joinedload(Staff.supervisor)
    ).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    return StaffResponse.model_validate(staff)

@router.put("/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: UUID,
    staff_update: StaffUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "update"))
):
    """Update staff information."""

    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Validate supervisor if provided
    if staff_update.supervisor_id:
        supervisor = db.query(Staff).filter(
            Staff.id == staff_update.supervisor_id,
            Staff.organization_id == current_user.organization_id
        ).first()
        if not supervisor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supervisor not found"
            )

    # Update staff fields
    update_data = staff_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(staff, field, value)

    staff.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(staff)

    # Load relationships for response
    staff_with_relations = db.query(Staff).options(
        joinedload(Staff.user),
        joinedload(Staff.supervisor)
    ).filter(Staff.id == staff.id).first()

    return StaffResponse.model_validate(staff_with_relations)

@router.post("/{staff_id}/terminate", response_model=MessageResponse)
async def terminate_staff(
    staff_id: UUID,
    termination_date: Optional[str] = Query(None, description="Termination date (YYYY-MM-DD)"),
    reason: Optional[str] = Query(None, description="Termination reason"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "update"))
):
    """Terminate a staff member's employment."""

    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    if staff.employment_status == EmploymentStatus.TERMINATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff member is already terminated"
        )

    # Parse termination date
    from datetime import datetime, date
    if termination_date:
        try:
            term_date = datetime.strptime(termination_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    else:
        term_date = date.today()

    # Update staff status
    staff.employment_status = EmploymentStatus.TERMINATED
    staff.termination_date = term_date
    if reason:
        staff.notes = f"{staff.notes or ''}\n\nTermination Reason: {reason}".strip()

    # Deactivate user account
    staff.user.status = UserStatus.INACTIVE
    staff.user.updated_at = datetime.now(timezone.utc)

    staff.updated_at = datetime.now(timezone.utc)
    db.commit()

    return MessageResponse(
        message=f"Staff member {staff.full_name} has been terminated",
        success=True
    )

@router.post("/{staff_id}/reactivate", response_model=MessageResponse)
async def reactivate_staff(
    staff_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "update"))
):
    """Reactivate a terminated staff member."""

    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    if staff.employment_status != EmploymentStatus.TERMINATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff member is not terminated"
        )

    # Reactivate staff
    staff.employment_status = EmploymentStatus.ACTIVE
    staff.termination_date = None

    # Reactivate user account
    staff.user.status = UserStatus.ACTIVE
    staff.user.updated_at = datetime.now(timezone.utc)

    staff.updated_at = datetime.now(timezone.utc)
    db.commit()

    return MessageResponse(
        message=f"Staff member {staff.full_name} has been reactivated",
        success=True
    )

@router.post("/{staff_id}/reset-password", response_model=MessageResponse)
async def reset_staff_password(
    staff_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "update"))
):
    """Reset a staff member's password and send new credentials."""

    staff = db.query(Staff).options(
        joinedload(Staff.user)
    ).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    # Generate new password
    new_password = generate_random_password(12)
    staff.user.password_hash = get_password_hash(new_password)
    staff.user.must_change_password = True
    staff.user.password_changed_at = datetime.now(timezone.utc)
    staff.user.updated_at = datetime.now(timezone.utc)

    db.commit()

    # Get additional info for email
    organization = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()

    role = db.query(Role).filter(Role.id == staff.user.role_id).first()

    # Send new credentials email
    try:
        await EmailService.send_staff_credentials(
            email=staff.user.email,
            full_name=staff.full_name,
            username=staff.user.username,
            password=new_password,
            employee_id=staff.employee_id,
            organization_name=organization.name if organization else "Starline",
            role_name=role.name if role else "Staff",
            department=staff.department,
            hire_date=staff.hire_date.strftime("%B %d, %Y") if staff.hire_date else None,
            supervisor_name=staff.supervisor.full_name if staff.supervisor else None,
            supervisor_email=staff.supervisor.user.email if staff.supervisor and staff.supervisor.user else None,
            support_email=organization.contact_email if organization else settings.DEFAULT_ADMIN_EMAIL,
            support_phone=organization.contact_phone if organization else None
        )

        logger.info(f"Password reset email sent successfully to {staff.user.email}")

    except Exception as email_error:
        logger.error(f"Failed to send password reset email: {str(email_error)}")

    return MessageResponse(
        message=f"Password reset successfully for {staff.full_name}. New credentials sent via email.",
        success=True
    )

@router.put("/{staff_id}/permissions", response_model=PermissionAssignmentResponse)
async def update_staff_permissions(
    staff_id: UUID,
    permission_update: StaffPermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "update"))
):
    """Update staff member's role and/or custom permissions."""

    staff = db.query(Staff).options(
        joinedload(Staff.user)
    ).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    try:
        # Update role if provided
        if permission_update.role_id:
            role = db.query(Role).filter(Role.id == permission_update.role_id).first()
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
            staff.user.role_id = permission_update.role_id

        # Update custom permissions settings
        staff.user.use_custom_permissions = permission_update.use_custom_permissions

        # Update custom permissions if provided
        if permission_update.use_custom_permissions:
            if permission_update.custom_permission_ids:
                # Validate permissions exist
                custom_permissions = db.query(Permission).filter(
                    Permission.id.in_(permission_update.custom_permission_ids)
                ).all()
                if len(custom_permissions) != len(permission_update.custom_permission_ids):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="One or more permissions not found"
                    )
                # Assign custom permissions
                staff.user.custom_permissions = custom_permissions
            else:
                # Clear custom permissions if none provided
                staff.user.custom_permissions = []
        else:
            # Clear custom permissions when not using custom permissions
            staff.user.custom_permissions = []

        staff.user.updated_at = datetime.now(timezone.utc)
        staff.updated_at = datetime.now(timezone.utc)
        db.commit()

        return PermissionAssignmentResponse(
            message=f"Permissions updated successfully for {staff.full_name}",
            success=True
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating staff permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update permissions"
        )

# Staff-to-Client Assignment Endpoints

@router.get("/me/clients", response_model=List[ClientResponse])
async def get_my_assigned_clients(
    active_only: bool = Query(True, description="Return only active assignments"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all clients assigned to the currently logged-in staff member"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Query assignments - get client IDs first to avoid DISTINCT on JSON columns
    assignment_query = db.query(StaffAssignment.client_id).filter(
        StaffAssignment.staff_id == staff.id
    )

    if active_only:
        assignment_query = assignment_query.filter(
            StaffAssignment.is_active == True
        )

    client_ids = [row[0] for row in assignment_query.distinct().all()]

    # Now query clients by IDs
    if not client_ids:
        return []

    query = db.query(Client).filter(
        Client.id.in_(client_ids),
        Client.organization_id == current_user.organization_id
    )

    if active_only:
        query = query.filter(Client.status == "active")

    clients = query.all()

    # Add user emails, location, and schedule to response
    client_responses = []
    for client in clients:
        response = ClientResponse.model_validate(client)
        if client.user:
            response.email = client.user.email
        response.full_name = client.full_name

        # Get assignment details
        assignment = db.query(StaffAssignment).filter(
            StaffAssignment.staff_id == staff.id,
            StaffAssignment.client_id == client.id,
            StaffAssignment.is_active == True
        ).first()

        # Add location information - Priority order:
        # 1. Client's direct location_id field
        # 2. Client assignment (legacy)
        from app.models.client import ClientAssignment, ClientLocation
        from app.models.location import Location

        location_found = False

        # First priority: Check client's direct location_id
        if client.location_id:
            location = db.query(Location).filter(
                Location.id == client.location_id
            ).first()
            if location:
                response.location_name = location.name
                response.location_address = location.address or ""
                location_found = True

        # Second priority: Check client assignment (legacy)
        if not location_found:
            current_assignment = db.query(ClientAssignment).filter(
                ClientAssignment.client_id == client.id,
                ClientAssignment.is_current == True
            ).first()

            if current_assignment and current_assignment.location_id:
                location = db.query(ClientLocation).filter(
                    ClientLocation.id == current_assignment.location_id
                ).first()
                if location:
                    response.location_name = location.name
                    response.location_address = location.address
                    location_found = True

        # Set to None if no location found
        if not location_found:
            response.location_name = None
            response.location_address = None

        # Add reporting schedule (days of week) based on actual shifts
        from app.models.scheduling import Shift, ShiftStatus, ShiftAssignment
        from datetime import datetime, timedelta

        # Get recent/upcoming shifts to determine reporting days for this specific client
        start_date = datetime.now().date() - timedelta(days=7)
        end_date = datetime.now().date() + timedelta(days=7)

        # Query shifts that are either directly assigned to this client or have shift assignments for this client
        shifts = db.query(Shift).outerjoin(
            ShiftAssignment, Shift.id == ShiftAssignment.shift_id
        ).filter(
            Shift.staff_id == staff.id,
            Shift.shift_date >= start_date,
            Shift.shift_date <= end_date,
            Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.IN_PROGRESS, ShiftStatus.COMPLETED]),
            or_(
                Shift.client_id == client.id,  # Primary client assignment
                ShiftAssignment.client_id == client.id  # Additional client assignment
            )
        ).distinct().all()

        # Extract unique days of week from shifts
        reporting_days = set()
        for shift in shifts:
            day_of_week = shift.shift_date.weekday()  # 0=Monday, 6=Sunday
            day_names = ['M', 'T', 'W', 'Th', 'F', 'Sa', 'Su']
            reporting_days.add(day_names[day_of_week])

        response.reporting_days = list(reporting_days) if reporting_days else []

        # Get last interaction timestamp from most recent documentation
        from app.models.vitals_log import VitalsLog
        from app.models.meal_log import MealLog
        from app.models.activity_log import ActivityLog
        from app.models.shift_note import ShiftNote
        from app.models.incident_report import IncidentReport
        from sqlalchemy import func

        # Query most recent timestamp from each documentation type
        latest_timestamps = []

        # Vitals
        latest_vital = db.query(func.max(VitalsLog.recorded_at)).filter(
            VitalsLog.client_id == client.id
        ).scalar()
        if latest_vital:
            latest_timestamps.append(latest_vital)

        # Meals
        latest_meal = db.query(func.max(MealLog.meal_date)).filter(
            MealLog.client_id == client.id
        ).scalar()
        if latest_meal:
            # Convert date to datetime for comparison
            from datetime import datetime, time
            if isinstance(latest_meal, datetime):
                latest_timestamps.append(latest_meal)
            else:
                latest_timestamps.append(datetime.combine(latest_meal, time.min))

        # Activities
        latest_activity = db.query(func.max(ActivityLog.activity_date)).filter(
            ActivityLog.client_id == client.id
        ).scalar()
        if latest_activity:
            from datetime import datetime, time
            if isinstance(latest_activity, datetime):
                latest_timestamps.append(latest_activity)
            else:
                latest_timestamps.append(datetime.combine(latest_activity, time.min))

        # Shift Notes
        latest_shift_note = db.query(func.max(ShiftNote.created_at)).filter(
            ShiftNote.client_id == client.id
        ).scalar()
        if latest_shift_note:
            latest_timestamps.append(latest_shift_note)

        # Incidents
        latest_incident = db.query(func.max(IncidentReport.created_at)).filter(
            IncidentReport.client_id == client.id
        ).scalar()
        if latest_incident:
            latest_timestamps.append(latest_incident)

        # Get the most recent timestamp
        response.last_interaction = max(latest_timestamps) if latest_timestamps else None

        client_responses.append(response)

    return client_responses


@router.get("/me/clients/{client_id}", response_model=ClientResponse)
async def get_assigned_client_by_id(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get details of a specific client assigned to the currently logged-in staff member"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Check if client is assigned to this staff member
    assignment = db.query(StaffAssignment).filter(
        StaffAssignment.staff_id == staff.id,
        StaffAssignment.client_id == client_id,
        StaffAssignment.is_active == True
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or not assigned to you"
        )

    # Get client details with relationships
    from sqlalchemy.orm import joinedload
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).options(
        joinedload(Client.user),
        joinedload(Client.contacts),
        joinedload(Client.assignments),
        joinedload(Client.care_plans),
        joinedload(Client.medications),
        joinedload(Client.insurance_policies)
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Build response
    response = ClientResponse.model_validate(client)
    if client.user:
        response.email = client.user.email
    response.full_name = client.full_name

    # Add location information - Priority order:
    # 1. Client's direct location_id field
    # 2. Client assignment (legacy)
    from app.models.client import ClientAssignment as ClientAssignmentModel, ClientLocation
    from app.models.location import Location

    location_found = False

    # First priority: Check client's direct location_id
    if client.location_id:
        location = db.query(Location).filter(
            Location.id == client.location_id
        ).first()
        if location:
            response.location_name = location.name
            response.location_address = location.address or ""
            location_found = True

    # Second priority: Check client assignment (legacy)
    if not location_found:
        current_assignment = db.query(ClientAssignmentModel).filter(
            ClientAssignmentModel.client_id == client.id,
            ClientAssignmentModel.is_current == True
        ).first()

        if current_assignment and current_assignment.location_id:
            location = db.query(ClientLocation).filter(
                ClientLocation.id == current_assignment.location_id
            ).first()
            if location:
                response.location_name = location.name
                response.location_address = location.address
                location_found = True

    # Set to None if no location found
    if not location_found:
        response.location_name = None
        response.location_address = None

    # Add reporting schedule from shifts
    from app.models.scheduling import Shift, ShiftStatus
    from datetime import datetime, timedelta

    start_date = datetime.now().date() - timedelta(days=7)
    end_date = datetime.now().date() + timedelta(days=7)

    shifts = db.query(Shift).filter(
        Shift.staff_id == staff.id,
        Shift.client_id == client_id,  # Filter by specific client
        Shift.shift_date >= start_date,
        Shift.shift_date <= end_date,
        Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.IN_PROGRESS, ShiftStatus.COMPLETED])
    ).all()

    # Extract unique days of week from shifts
    reporting_days = set()
    for shift in shifts:
        day_of_week = shift.shift_date.weekday()  # 0=Monday, 6=Sunday
        day_names = ['M', 'T', 'W', 'Th', 'F', 'Sa', 'Su']
        reporting_days.add(day_names[day_of_week])

    response.reporting_days = list(reporting_days) if reporting_days else []
    response.last_interaction = None

    return response


@router.post("/{staff_id}/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_staff_to_client(
    staff_id: UUID,
    assignment_data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "manage_assignments"))
):
    """Assign a staff member to a client"""

    try:
        # Verify staff exists and belongs to organization
        staff = db.query(Staff).filter(
            Staff.id == staff_id,
            Staff.organization_id == current_user.organization_id
        ).first()

        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found"
            )

        # Verify staff is active
        if staff.employment_status != EmploymentStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign {staff.employment_status.value} staff member"
            )

        # Verify client exists and belongs to organization if client_id provided
        if assignment_data.client_id:
            client = db.query(Client).filter(
                Client.id == assignment_data.client_id,
                Client.organization_id == current_user.organization_id
            ).first()

            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Client not found"
                )

            # Verify client is active
            if client.status not in ["active", "on_hold"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot assign staff to {client.status} client"
                )

        # Check if this staff is already assigned to this client (any assignment type)
        if assignment_data.client_id:
            existing_assignment = db.query(StaffAssignment).filter(
                StaffAssignment.staff_id == staff_id,
                StaffAssignment.client_id == assignment_data.client_id,
                StaffAssignment.is_active == True
            ).first()

            if existing_assignment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This staff member is already assigned to this client as {existing_assignment.assignment_type.value}. Please end the existing assignment first or modify it."
                )

            # Check for existing active PRIMARY assignment (different staff)
            if assignment_data.assignment_type == AssignmentType.PRIMARY:
                existing_primary = db.query(StaffAssignment).filter(
                    StaffAssignment.client_id == assignment_data.client_id,
                    StaffAssignment.assignment_type == AssignmentType.PRIMARY,
                    StaffAssignment.is_active == True
                ).first()

                if existing_primary:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Client already has a primary staff assignment. Please end that assignment first or use a different assignment type."
                    )

        # Create assignment
        assignment = StaffAssignment(
            staff_id=staff_id,
            client_id=assignment_data.client_id,
            location_id=assignment_data.location_id,
            assignment_type=assignment_data.assignment_type,
            start_date=assignment_data.start_date,
            end_date=assignment_data.end_date,
            is_active=assignment_data.is_active,
            notes=assignment_data.notes
        )

        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        # Reload with client data
        assignment = db.query(StaffAssignment).options(
            joinedload(StaffAssignment.client).joinedload(Client.user)
        ).filter(StaffAssignment.id == assignment.id).first()

        # Enrich assignment with client email
        if assignment.client and assignment.client.user:
            assignment.client.email = assignment.client.user.email

        logger.info(f"Staff {staff.full_name} assigned to client {assignment_data.client_id} by {current_user.email}")

        return assignment

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating staff assignment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create assignment"
        )

@router.get("/{staff_id}/assignments", response_model=List[AssignmentResponse])
async def list_staff_assignments(
    staff_id: UUID,
    active_only: bool = Query(False, description="Return only active assignments"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all assignments for a staff member"""

    # Verify staff exists and belongs to organization
    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    query = db.query(StaffAssignment).options(
        joinedload(StaffAssignment.client).joinedload(Client.user)
    ).filter(StaffAssignment.staff_id == staff_id)

    if active_only:
        query = query.filter(StaffAssignment.is_active == True)

    assignments = query.order_by(StaffAssignment.start_date.desc()).all()

    # Enrich assignments with client email
    for assignment in assignments:
        if assignment.client and assignment.client.user:
            assignment.client.email = assignment.client.user.email

    return assignments

@router.get("/{staff_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_staff_assignment(
    staff_id: UUID,
    assignment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific assignment for a staff member"""

    # Verify staff exists and belongs to organization
    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found"
        )

    assignment = db.query(StaffAssignment).options(
        joinedload(StaffAssignment.client).joinedload(Client.user)
    ).filter(
        StaffAssignment.id == assignment_id,
        StaffAssignment.staff_id == staff_id
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    # Enrich assignment with client email
    if assignment.client and assignment.client.user:
        assignment.client.email = assignment.client.user.email

    return assignment

@router.put("/{staff_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_staff_assignment(
    staff_id: UUID,
    assignment_id: UUID,
    assignment_update: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "manage_assignments"))
):
    """Update a staff assignment"""

    try:
        # Verify staff exists and belongs to organization
        staff = db.query(Staff).filter(
            Staff.id == staff_id,
            Staff.organization_id == current_user.organization_id
        ).first()

        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found"
            )

        assignment = db.query(StaffAssignment).filter(
            StaffAssignment.id == assignment_id,
            StaffAssignment.staff_id == staff_id
        ).first()

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )

        # Update fields
        update_data = assignment_update.model_dump(exclude_unset=True)

        # Validate client if being updated
        if 'client_id' in update_data and update_data['client_id']:
            client = db.query(Client).filter(
                Client.id == update_data['client_id'],
                Client.organization_id == current_user.organization_id
            ).first()

            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Client not found"
                )

        for field, value in update_data.items():
            setattr(assignment, field, value)

        assignment.updated_at = datetime.now(timezone.utc)

        db.commit()

        # Reload with client data
        assignment = db.query(StaffAssignment).options(
            joinedload(StaffAssignment.client).joinedload(Client.user)
        ).filter(StaffAssignment.id == assignment_id).first()

        # Enrich assignment with client email
        if assignment.client and assignment.client.user:
            assignment.client.email = assignment.client.user.email

        logger.info(f"Assignment {assignment_id} updated by {current_user.email}")

        return assignment

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating assignment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update assignment"
        )

@router.delete("/{staff_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_staff_assignment(
    staff_id: UUID,
    assignment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "manage_assignments"))
):
    """End a staff assignment (soft delete by setting end_date and is_active=False)"""

    try:
        # Verify staff exists and belongs to organization
        staff = db.query(Staff).filter(
            Staff.id == staff_id,
            Staff.organization_id == current_user.organization_id
        ).first()

        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found"
            )

        assignment = db.query(StaffAssignment).filter(
            StaffAssignment.id == assignment_id,
            StaffAssignment.staff_id == staff_id
        ).first()

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )

        # Soft delete
        assignment.is_active = False
        assignment.end_date = datetime.now(timezone.utc).date()
        assignment.updated_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(f"Assignment {assignment_id} ended by {current_user.email}")

        return None

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error ending assignment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end assignment"
        )


# ==================== DSP Time-Off Request Endpoints ====================

@router.get("/me/time-off-requests", response_model=List[TimeOffRequestResponse])
async def get_my_time_off_requests(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, approved, denied, cancelled"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all time-off requests for the currently logged-in staff member"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Query time-off requests
    query = db.query(TimeOffRequest).filter(
        TimeOffRequest.staff_id == staff.id
    )

    # Apply status filter if provided
    if status_filter:
        try:
            status_enum = TimeOffStatus(status_filter.lower())
            query = query.filter(TimeOffRequest.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter: {status_filter}. Valid values: pending, approved, denied, cancelled"
            )

    # Order by requested date descending (newest first)
    requests = query.order_by(TimeOffRequest.requested_date.desc()).all()

    return requests


@router.get("/me/time-off-requests/{request_id}", response_model=TimeOffRequestResponse)
async def get_my_time_off_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific time-off request for the currently logged-in staff member"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Get the request
    time_off_request = db.query(TimeOffRequest).filter(
        TimeOffRequest.id == request_id,
        TimeOffRequest.staff_id == staff.id
    ).first()

    if not time_off_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time-off request not found"
        )

    return time_off_request


@router.post("/me/time-off-requests", response_model=TimeOffRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_my_time_off_request(
    request_data: TimeOffRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new time-off request for the currently logged-in staff member"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Validation: End date must be >= start date
    if request_data.end_date < request_data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date"
        )

    # Validation: Total hours must be positive
    if request_data.total_hours <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total hours must be a positive number"
        )

    # Validation: Minimum 24 hours notice (start date must be at least tomorrow)
    from datetime import date, timedelta
    min_start_date = date.today() + timedelta(days=1)
    if request_data.start_date < min_start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time-off requests require at least 24 hours advance notice"
        )

    # Create the time-off request
    try:
        new_request = TimeOffRequest(
            staff_id=staff.id,
            request_type=request_data.request_type,
            start_date=request_data.start_date,
            end_date=request_data.end_date,
            total_hours=request_data.total_hours,
            reason=request_data.reason,
            status=TimeOffStatus.PENDING
        )

        db.add(new_request)
        db.commit()
        db.refresh(new_request)

        logger.info(f"Time-off request created by {current_user.email}: {new_request.id}")

        # Send email notification to manager(s)
        try:
            staff_name = staff.full_name
            staff_role = staff.job_title

            # Format dates
            start_date_str = request_data.start_date.strftime("%a, %b %d, %Y")
            end_date_str = request_data.end_date.strftime("%a, %b %d, %Y")
            total_hours_str = str(request_data.total_hours)
            request_type_str = request_data.request_type.value.replace("_", " ").title()

            # Find managers in the organization
            managers = db.query(User).join(Role).filter(
                User.organization_id == current_user.organization_id,
                User.status == UserStatus.ACTIVE,
                or_(
                    Role.name.ilike("%manager%"),
                    Role.name.ilike("%admin%"),
                    Role.name.ilike("%supervisor%")
                )
            ).all()

            for manager in managers:
                await EmailService.send_time_off_request_email(
                    to_email=manager.email,
                    manager_name=f"{manager.first_name} {manager.last_name}",
                    staff_name=staff_name,
                    request_type=request_type_str,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    total_hours=total_hours_str,
                    staff_role=staff_role,
                    reason=request_data.reason
                )
                logger.info(f"Time-off request email sent to manager {manager.email}")

        except Exception as email_error:
            logger.error(f"Failed to send time-off request email: {str(email_error)}")
            # Don't fail the request if email fails

        return new_request

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating time-off request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create time-off request"
        )


@router.delete("/me/time-off-requests/{request_id}", response_model=MessageResponse)
async def cancel_my_time_off_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel a pending time-off request for the currently logged-in staff member"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Get the request
    time_off_request = db.query(TimeOffRequest).filter(
        TimeOffRequest.id == request_id,
        TimeOffRequest.staff_id == staff.id
    ).first()

    if not time_off_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time-off request not found"
        )

    # Only allow cancellation of pending requests
    if time_off_request.status != TimeOffStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a request with status '{time_off_request.status.value}'. Only pending requests can be cancelled."
        )

    try:
        time_off_request.status = TimeOffStatus.CANCELLED
        time_off_request.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Time-off request {request_id} cancelled by {current_user.email}")

        return MessageResponse(
            message="Time-off request cancelled successfully",
            success=True
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling time-off request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel time-off request"
        )


# ==================== DSP Shift Exchange Request Endpoints ====================

def _build_staff_shift_info(shift: Shift, staff: Staff, db: Session) -> StaffShiftInfo:
    """Helper function to build StaffShiftInfo from shift and staff"""
    client_name = None
    if shift.client:
        client_name = f"{shift.client.first_name} {shift.client.last_name}"

    location_name = None
    if shift.location_id:
        location = db.query(Location).filter(Location.id == shift.location_id).first()
        if location:
            location_name = location.name

    return StaffShiftInfo(
        staff_id=staff.id,
        staff_name=staff.full_name,
        staff_email=staff.user.email if staff.user else None,
        shift_id=shift.id,
        shift_date=shift.shift_date,
        start_time=shift.start_time,
        end_time=shift.end_time,
        shift_type=shift.shift_type.value if hasattr(shift.shift_type, 'value') else str(shift.shift_type),
        client_name=client_name,
        location_name=location_name
    )


def _build_exchange_response(exchange: ShiftExchangeRequest, db: Session) -> ShiftExchangeRequestResponse:
    """Helper function to build ShiftExchangeRequestResponse"""
    requester_info = _build_staff_shift_info(exchange.requester_shift, exchange.requester_staff, db)
    target_info = _build_staff_shift_info(exchange.target_shift, exchange.target_staff, db)

    return ShiftExchangeRequestResponse(
        id=exchange.id,
        organization_id=exchange.organization_id,
        status=exchange.status,
        reason=exchange.reason,
        requester=requester_info,
        target=target_info,
        requested_at=exchange.requested_at,
        peer_responded_at=exchange.peer_responded_at,
        peer_response_notes=exchange.peer_response_notes,
        manager_responded_by=exchange.manager_responded_by,
        manager_responded_at=exchange.manager_responded_at,
        manager_response_notes=exchange.manager_response_notes,
        created_at=exchange.created_at,
        updated_at=exchange.updated_at
    )


@router.get("/me/colleagues-shifts", response_model=List[ColleagueShiftResponse])
async def get_colleagues_shifts(
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all colleagues' shifts for exchange (full visibility)"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Import Schedule model
    from app.models.scheduling import Schedule

    # Query all shifts from the same organization, excluding own shifts
    query = db.query(Shift).join(
        Schedule, Shift.schedule_id == Schedule.id
    ).join(
        Staff, Shift.staff_id == Staff.id
    ).filter(
        Schedule.organization_id == current_user.organization_id,
        Shift.staff_id != staff.id,  # Exclude own shifts
        Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.CONFIRMED])  # Only available shifts
    )

    # Filter by date range (default to future shifts)
    from datetime import date as date_type, timedelta
    today = date_type.today()

    if start_date:
        try:
            filter_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
    else:
        # Default to today + 1 day (24 hour notice)
        filter_start = today + timedelta(days=1)

    if end_date:
        try:
            filter_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD"
            )
    else:
        # Default to 30 days from now
        filter_end = today + timedelta(days=30)

    query = query.filter(
        Shift.shift_date >= filter_start,
        Shift.shift_date <= filter_end
    )

    # Order by date
    shifts = query.order_by(Shift.shift_date, Shift.start_time).all()

    # Build response
    result = []
    for shift in shifts:
        staff_member = db.query(Staff).options(
            joinedload(Staff.user)
        ).filter(Staff.id == shift.staff_id).first()

        if staff_member:
            client_name = None
            if shift.client:
                client_name = f"{shift.client.first_name} {shift.client.last_name}"

            location_name = None
            if shift.location_id:
                location = db.query(Location).filter(Location.id == shift.location_id).first()
                if location:
                    location_name = location.name

            result.append(ColleagueShiftResponse(
                shift_id=shift.id,
                staff_id=staff_member.id,
                staff_name=staff_member.full_name,
                shift_date=shift.shift_date,
                start_time=shift.start_time,
                end_time=shift.end_time,
                shift_type=shift.shift_type.value if hasattr(shift.shift_type, 'value') else str(shift.shift_type),
                client_name=client_name,
                location_name=location_name
            ))

    return result


@router.get("/me/my-shifts", response_model=List[ColleagueShiftResponse])
async def get_my_shifts_for_exchange(
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get own shifts available for exchange"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Query own shifts
    query = db.query(Shift).filter(
        Shift.staff_id == staff.id,
        Shift.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.CONFIRMED])
    )

    # Filter by date range
    from datetime import date as date_type, timedelta
    today = date_type.today()

    if start_date:
        try:
            filter_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
    else:
        # Default to today + 1 day (24 hour notice)
        filter_start = today + timedelta(days=1)

    if end_date:
        try:
            filter_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD"
            )
    else:
        # Default to 30 days from now
        filter_end = today + timedelta(days=30)

    query = query.filter(
        Shift.shift_date >= filter_start,
        Shift.shift_date <= filter_end
    )

    shifts = query.order_by(Shift.shift_date, Shift.start_time).all()

    # Build response
    result = []
    for shift in shifts:
        client_name = None
        if shift.client:
            client_name = f"{shift.client.first_name} {shift.client.last_name}"

        location_name = None
        if shift.location_id:
            location = db.query(Location).filter(Location.id == shift.location_id).first()
            if location:
                location_name = location.name

        result.append(ColleagueShiftResponse(
            shift_id=shift.id,
            staff_id=staff.id,
            staff_name=staff.full_name,
            shift_date=shift.shift_date,
            start_time=shift.start_time,
            end_time=shift.end_time,
            shift_type=shift.shift_type.value if hasattr(shift.shift_type, 'value') else str(shift.shift_type),
            client_name=client_name,
            location_name=location_name
        ))

    return result


@router.get("/me/shift-exchange-requests", response_model=List[ShiftExchangeRequestResponse])
async def get_my_shift_exchange_requests(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get shift exchange requests I've sent"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Query exchange requests sent by me
    query = db.query(ShiftExchangeRequest).options(
        joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
        joinedload(ShiftExchangeRequest.requester_shift),
        joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
        joinedload(ShiftExchangeRequest.target_shift)
    ).filter(
        ShiftExchangeRequest.requester_staff_id == staff.id
    )

    # Apply status filter
    if status_filter:
        try:
            status_enum = ShiftExchangeStatus(status_filter.lower())
            query = query.filter(ShiftExchangeRequest.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Valid values: pending_peer, pending_manager, approved, denied, cancelled"
            )

    exchanges = query.order_by(ShiftExchangeRequest.requested_at.desc()).all()

    return [_build_exchange_response(ex, db) for ex in exchanges]


@router.get("/me/shift-exchange-requests/incoming", response_model=List[ShiftExchangeRequestResponse])
async def get_incoming_shift_exchange_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get shift exchange requests from colleagues needing my acceptance"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Query exchange requests where I'm the target (waiting for my response)
    exchanges = db.query(ShiftExchangeRequest).options(
        joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
        joinedload(ShiftExchangeRequest.requester_shift),
        joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
        joinedload(ShiftExchangeRequest.target_shift)
    ).filter(
        ShiftExchangeRequest.target_staff_id == staff.id,
        ShiftExchangeRequest.status == ShiftExchangeStatus.PENDING_PEER
    ).order_by(ShiftExchangeRequest.requested_at.desc()).all()

    return [_build_exchange_response(ex, db) for ex in exchanges]


@router.post("/me/shift-exchange-requests", response_model=ShiftExchangeRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_shift_exchange_request(
    request_data: ShiftExchangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new shift exchange request (Step 1: DSP A requests)"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Validate requester's shift exists and belongs to them
    requester_shift = db.query(Shift).filter(
        Shift.id == request_data.requester_shift_id,
        Shift.staff_id == staff.id
    ).first()

    if not requester_shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requester shift not found or doesn't belong to you"
        )

    # Validate target shift exists
    target_shift = db.query(Shift).filter(
        Shift.id == request_data.target_shift_id
    ).first()

    if not target_shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target shift not found"
        )

    # Cannot exchange with own shift
    if target_shift.staff_id == staff.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot exchange with your own shift"
        )

    # Get target staff
    target_staff = db.query(Staff).filter(
        Staff.id == target_shift.staff_id
    ).first()

    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target staff not found"
        )

    # Validate minimum 24-hour notice
    from datetime import date as date_type, timedelta
    min_date = date_type.today() + timedelta(days=1)

    if requester_shift.shift_date < min_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shift exchange requests require at least 24 hours advance notice"
        )

    if target_shift.shift_date < min_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target shift must be at least 24 hours in the future"
        )

    # Check for existing pending exchange request for these shifts
    existing = db.query(ShiftExchangeRequest).filter(
        ShiftExchangeRequest.requester_shift_id == request_data.requester_shift_id,
        ShiftExchangeRequest.target_shift_id == request_data.target_shift_id,
        ShiftExchangeRequest.status.in_([ShiftExchangeStatus.PENDING_PEER, ShiftExchangeStatus.PENDING_MANAGER])
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An exchange request for these shifts is already pending"
        )

    try:
        # Create the exchange request
        new_request = ShiftExchangeRequest(
            organization_id=current_user.organization_id,
            requester_staff_id=staff.id,
            requester_shift_id=request_data.requester_shift_id,
            target_staff_id=target_staff.id,
            target_shift_id=request_data.target_shift_id,
            reason=request_data.reason,
            status=ShiftExchangeStatus.PENDING_PEER
        )

        db.add(new_request)
        db.commit()
        db.refresh(new_request)

        # Reload with relationships
        new_request = db.query(ShiftExchangeRequest).options(
            joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
            joinedload(ShiftExchangeRequest.requester_shift),
            joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
            joinedload(ShiftExchangeRequest.target_shift)
        ).filter(ShiftExchangeRequest.id == new_request.id).first()

        logger.info(f"Shift exchange request created by {current_user.email}: {new_request.id}")

        # Send email notification to target staff
        try:
            target_user = target_staff.user
            requester_name = staff.full_name
            target_name = target_staff.full_name

            # Format shift dates and times
            requester_shift_date = requester_shift.shift_date.strftime("%a, %b %d, %Y")
            requester_shift_time = f"{requester_shift.start_time.strftime('%I:%M %p')} - {requester_shift.end_time.strftime('%I:%M %p')}"
            target_shift_date = target_shift.shift_date.strftime("%a, %b %d, %Y")
            target_shift_time = f"{target_shift.start_time.strftime('%I:%M %p')} - {target_shift.end_time.strftime('%I:%M %p')}"

            # Get client names if applicable
            requester_client = None
            target_client = None
            if requester_shift.client_id:
                client = db.query(Client).filter(Client.id == requester_shift.client_id).first()
                if client:
                    requester_client = f"{client.first_name} {client.last_name}"
            if target_shift.client_id:
                client = db.query(Client).filter(Client.id == target_shift.client_id).first()
                if client:
                    target_client = f"{client.first_name} {client.last_name}"

            await EmailService.send_shift_exchange_request_email(
                to_email=target_user.email,
                recipient_name=target_name,
                requester_name=requester_name,
                requester_shift_date=requester_shift_date,
                requester_shift_time=requester_shift_time,
                target_shift_date=target_shift_date,
                target_shift_time=target_shift_time,
                requester_client=requester_client,
                target_client=target_client,
                reason=request_data.reason
            )
            logger.info(f"Shift exchange request email sent to {target_user.email}")
        except Exception as email_error:
            logger.error(f"Failed to send shift exchange request email: {str(email_error)}")
            # Don't fail the request if email fails

        return _build_exchange_response(new_request, db)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating shift exchange request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create shift exchange request"
        )


@router.post("/me/shift-exchange-requests/{request_id}/accept", response_model=ShiftExchangeRequestResponse)
async def accept_shift_exchange_request(
    request_id: UUID,
    response_data: ShiftExchangeRequestPeerResponse,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Accept a shift exchange request (Step 2: DSP B accepts)"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Get the exchange request
    exchange = db.query(ShiftExchangeRequest).options(
        joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
        joinedload(ShiftExchangeRequest.requester_shift),
        joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
        joinedload(ShiftExchangeRequest.target_shift)
    ).filter(
        ShiftExchangeRequest.id == request_id,
        ShiftExchangeRequest.target_staff_id == staff.id
    ).first()

    if not exchange:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange request not found or you're not the target"
        )

    if exchange.status != ShiftExchangeStatus.PENDING_PEER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot accept a request with status '{exchange.status.value}'"
        )

    try:
        # Update status to pending manager approval
        exchange.status = ShiftExchangeStatus.PENDING_MANAGER
        exchange.peer_responded_at = datetime.now(timezone.utc)
        exchange.peer_response_notes = response_data.notes
        exchange.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(exchange)

        logger.info(f"Shift exchange request {request_id} accepted by {current_user.email}")

        # Send email notifications
        try:
            requester_staff = exchange.requester_staff
            target_staff = exchange.target_staff
            requester_shift = exchange.requester_shift
            target_shift = exchange.target_shift

            # Format shift dates and times
            requester_shift_date = requester_shift.shift_date.strftime("%a, %b %d, %Y")
            requester_shift_time = f"{requester_shift.start_time.strftime('%I:%M %p')} - {requester_shift.end_time.strftime('%I:%M %p')}"
            target_shift_date = target_shift.shift_date.strftime("%a, %b %d, %Y")
            target_shift_time = f"{target_shift.start_time.strftime('%I:%M %p')} - {target_shift.end_time.strftime('%I:%M %p')}"

            # Get client names if applicable
            requester_client = None
            target_client = None
            if requester_shift.client_id:
                client = db.query(Client).filter(Client.id == requester_shift.client_id).first()
                if client:
                    requester_client = f"{client.first_name} {client.last_name}"
            if target_shift.client_id:
                client = db.query(Client).filter(Client.id == target_shift.client_id).first()
                if client:
                    target_client = f"{client.first_name} {client.last_name}"

            # 1. Notify the requester that their request was accepted
            await EmailService.send_shift_exchange_accepted_email(
                to_email=requester_staff.user.email,
                recipient_name=requester_staff.full_name,
                accepter_name=target_staff.full_name,
                requester_shift_date=requester_shift_date,
                requester_shift_time=requester_shift_time,
                target_shift_date=target_shift_date,
                target_shift_time=target_shift_time,
                requester_client=requester_client,
                target_client=target_client
            )
            logger.info(f"Shift exchange acceptance email sent to requester {requester_staff.user.email}")

            # 2. Notify manager(s) that a shift exchange needs approval
            # Find managers in the organization
            managers = db.query(User).join(Role).filter(
                User.organization_id == current_user.organization_id,
                User.status == UserStatus.ACTIVE,
                or_(
                    Role.name.ilike("%manager%"),
                    Role.name.ilike("%admin%"),
                    Role.name.ilike("%supervisor%")
                )
            ).all()

            for manager in managers:
                await EmailService.send_shift_exchange_pending_manager_email(
                    to_email=manager.email,
                    manager_name=f"{manager.first_name} {manager.last_name}",
                    requester_name=requester_staff.full_name,
                    target_name=target_staff.full_name,
                    requester_shift_date=requester_shift_date,
                    requester_shift_time=requester_shift_time,
                    target_shift_date=target_shift_date,
                    target_shift_time=target_shift_time,
                    requester_client=requester_client,
                    target_client=target_client,
                    reason=exchange.reason
                )
                logger.info(f"Shift exchange pending approval email sent to manager {manager.email}")

        except Exception as email_error:
            logger.error(f"Failed to send shift exchange acceptance emails: {str(email_error)}")
            # Don't fail the request if email fails

        return _build_exchange_response(exchange, db)

    except Exception as e:
        db.rollback()
        logger.error(f"Error accepting shift exchange request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept shift exchange request"
        )


@router.post("/me/shift-exchange-requests/{request_id}/decline", response_model=ShiftExchangeRequestResponse)
async def decline_shift_exchange_request(
    request_id: UUID,
    response_data: ShiftExchangeRequestPeerResponse,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Decline a shift exchange request (Step 2: DSP B declines)"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Get the exchange request
    exchange = db.query(ShiftExchangeRequest).options(
        joinedload(ShiftExchangeRequest.requester_staff).joinedload(Staff.user),
        joinedload(ShiftExchangeRequest.requester_shift),
        joinedload(ShiftExchangeRequest.target_staff).joinedload(Staff.user),
        joinedload(ShiftExchangeRequest.target_shift)
    ).filter(
        ShiftExchangeRequest.id == request_id,
        ShiftExchangeRequest.target_staff_id == staff.id
    ).first()

    if not exchange:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange request not found or you're not the target"
        )

    if exchange.status != ShiftExchangeStatus.PENDING_PEER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot decline a request with status '{exchange.status.value}'"
        )

    try:
        # Update status to denied
        exchange.status = ShiftExchangeStatus.DENIED
        exchange.peer_responded_at = datetime.now(timezone.utc)
        exchange.peer_response_notes = response_data.notes
        exchange.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(exchange)

        logger.info(f"Shift exchange request {request_id} declined by {current_user.email}")

        # Send email notification to the requester
        try:
            requester_staff = exchange.requester_staff
            target_staff = exchange.target_staff
            requester_shift = exchange.requester_shift
            target_shift = exchange.target_shift

            # Format shift dates and times
            requester_shift_date = requester_shift.shift_date.strftime("%a, %b %d, %Y")
            requester_shift_time = f"{requester_shift.start_time.strftime('%I:%M %p')} - {requester_shift.end_time.strftime('%I:%M %p')}"
            target_shift_date = target_shift.shift_date.strftime("%a, %b %d, %Y")
            target_shift_time = f"{target_shift.start_time.strftime('%I:%M %p')} - {target_shift.end_time.strftime('%I:%M %p')}"

            # Get client names if applicable
            requester_client = None
            target_client = None
            if requester_shift.client_id:
                client = db.query(Client).filter(Client.id == requester_shift.client_id).first()
                if client:
                    requester_client = f"{client.first_name} {client.last_name}"
            if target_shift.client_id:
                client = db.query(Client).filter(Client.id == target_shift.client_id).first()
                if client:
                    target_client = f"{client.first_name} {client.last_name}"

            await EmailService.send_shift_exchange_declined_email(
                to_email=requester_staff.user.email,
                recipient_name=requester_staff.full_name,
                decliner_name=target_staff.full_name,
                requester_shift_date=requester_shift_date,
                requester_shift_time=requester_shift_time,
                target_shift_date=target_shift_date,
                target_shift_time=target_shift_time,
                requester_client=requester_client,
                target_client=target_client,
                notes=response_data.notes
            )
            logger.info(f"Shift exchange declined email sent to requester {requester_staff.user.email}")

        except Exception as email_error:
            logger.error(f"Failed to send shift exchange declined email: {str(email_error)}")
            # Don't fail the request if email fails

        return _build_exchange_response(exchange, db)

    except Exception as e:
        db.rollback()
        logger.error(f"Error declining shift exchange request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decline shift exchange request"
        )


@router.delete("/me/shift-exchange-requests/{request_id}", response_model=MessageResponse)
async def cancel_shift_exchange_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel a pending shift exchange request (requester only)"""

    # Get staff record for current user
    staff = db.query(Staff).filter(
        Staff.user_id == current_user.id,
        Staff.organization_id == current_user.organization_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff record not found for current user"
        )

    # Get the exchange request (only requester can cancel)
    exchange = db.query(ShiftExchangeRequest).filter(
        ShiftExchangeRequest.id == request_id,
        ShiftExchangeRequest.requester_staff_id == staff.id
    ).first()

    if not exchange:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange request not found or you're not the requester"
        )

    if exchange.status not in [ShiftExchangeStatus.PENDING_PEER, ShiftExchangeStatus.PENDING_MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a request with status '{exchange.status.value}'"
        )

    try:
        exchange.status = ShiftExchangeStatus.CANCELLED
        exchange.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Shift exchange request {request_id} cancelled by {current_user.email}")

        return MessageResponse(
            message="Shift exchange request cancelled successfully",
            success=True
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling shift exchange request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel shift exchange request"
        )