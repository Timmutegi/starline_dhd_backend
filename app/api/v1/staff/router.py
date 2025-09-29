from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from app.core.database import get_db
from app.core.security import get_password_hash, generate_random_password
from app.models.user import User, Organization, Role, UserStatus
from app.models.staff import Staff, EmploymentStatus
from app.middleware.auth import get_current_user, require_permission
from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    StaffResponse,
    StaffCreateResponse,
    StaffSummary,
    StaffListResponse
)
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

        # Check if employee ID already exists
        existing_staff = db.query(Staff).filter(
            Staff.employee_id == staff_data.employee_id,
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
            must_change_password=True  # Force password change on first login
        )

        db.add(new_user)
        db.flush()  # Get the user ID

        # Create Staff record
        new_staff = Staff(
            user_id=new_user.id,
            organization_id=current_user.organization_id,
            employee_id=staff_data.employee_id,
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

@router.get("/", response_model=StaffListResponse)
async def get_staff_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: Optional[str] = None,
    employment_status: Optional[EmploymentStatus] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff", "read"))
):
    """Get list of staff members with pagination and filtering."""

    query = db.query(Staff).options(
        joinedload(Staff.user)
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
    staff_list = query.offset(skip).limit(limit).all()

    # Convert to summary format
    staff_summaries = []
    for staff in staff_list:
        staff_summaries.append(StaffSummary(
            id=staff.id,
            employee_id=staff.employee_id,
            full_name=staff.full_name,
            display_name=staff.display_name,
            email=staff.user.email,
            job_title=staff.job_title,
            department=staff.department,
            employment_status=staff.employment_status,
            hire_date=staff.hire_date,
            last_login=staff.user.last_login
        ))

    pages = (total + limit - 1) // limit

    return StaffListResponse(
        staff=staff_summaries,
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=pages
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