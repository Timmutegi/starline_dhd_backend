from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import secrets
import string

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.security import get_password_hash
from app.models.user import User, UserStatus, Organization, Role, Permission
from app.models.client import (
    Client, ClientContact, ClientLocation, ClientAssignment,
    CarePlan, ClientNote, ClientMedication, ClientInsurance
)
from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientResponse, ClientListResponse,
    ClientContactCreate, ClientContactUpdate, ClientContactResponse,
    ClientLocationCreate, ClientLocationUpdate, ClientLocationResponse,
    ClientAssignmentCreate, ClientAssignmentUpdate, ClientAssignmentResponse,
    CarePlanCreate, CarePlanUpdate, CarePlanResponse,
    ClientNoteCreate, ClientNoteUpdate, ClientNoteResponse,
    ClientMedicationCreate, ClientMedicationUpdate, ClientMedicationResponse,
    ClientInsuranceCreate, ClientInsuranceUpdate, ClientInsuranceResponse,
    ClientSearchParams, ClientPermissionUpdate, ClientPermissionResponse
)
from app.services.email_service import EmailService

router = APIRouter()

def generate_client_id(db: Session, organization_id: UUID) -> str:
    """Generate unique client ID"""
    import random
    while True:
        client_id = f"CL{random.randint(10000, 99999)}"
        existing = db.query(Client).filter(
            Client.client_id == client_id,
            Client.organization_id == organization_id
        ).first()
        if not existing:
            return client_id

def generate_secure_password(length: int = 12) -> str:
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

# Client CRUD Operations
@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin", "Organization Admin"]))
):
    """Create a new client and their user account"""

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == client_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate role if provided
    role = None
    if client_data.role_id:
        role = db.query(Role).filter(Role.id == client_data.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

    # Validate custom permissions if provided
    custom_permissions = []
    if client_data.use_custom_permissions and client_data.custom_permission_ids:
        custom_permissions = db.query(Permission).filter(
            Permission.id.in_(client_data.custom_permission_ids)
        ).all()
        if len(custom_permissions) != len(client_data.custom_permission_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more permissions not found"
            )

    # Generate secure password
    temp_password = generate_secure_password()

    # Create user account for client
    user = User(
        organization_id=current_user.organization_id,
        email=client_data.email,
        username=client_data.email.split('@')[0],
        password_hash=get_password_hash(temp_password),
        first_name=client_data.first_name,
        last_name=client_data.last_name,
        role_id=client_data.role_id,
        status=UserStatus.ACTIVE,
        email_verified=False,
        must_change_password=True,
        password_changed_at=datetime.utcnow(),
        use_custom_permissions=client_data.use_custom_permissions
    )
    db.add(user)
    db.flush()  # Get user ID without committing

    # Create client profile
    client_id = generate_client_id(db, current_user.organization_id)

    client = Client(
        organization_id=current_user.organization_id,
        client_id=client_id,
        user_id=user.id,
        first_name=client_data.first_name,
        last_name=client_data.last_name,
        middle_name=client_data.middle_name,
        preferred_name=client_data.preferred_name,
        date_of_birth=client_data.date_of_birth,
        gender=client_data.gender,
        ssn_encrypted=client_data.ssn_encrypted,
        admission_date=client_data.admission_date,
        primary_diagnosis=client_data.primary_diagnosis,
        secondary_diagnoses=client_data.secondary_diagnoses,
        allergies=client_data.allergies,
        dietary_restrictions=client_data.dietary_restrictions,
        status="active",
        created_by=current_user.id
    )
    db.add(client)
    db.flush()  # Get the client ID

    # Assign custom permissions if provided
    if client_data.use_custom_permissions and custom_permissions:
        user.custom_permissions = custom_permissions

    try:
        db.commit()
        db.refresh(client)

        # Send email with credentials if requested
        if client_data.send_credentials:
            email_service = EmailService()
            await email_service.send_client_credentials(
                email=client_data.email,
                full_name=f"{client_data.first_name} {client_data.last_name}",
                username=user.username,
                password=temp_password,
                organization_name=current_user.organization.name if current_user.organization else "Starline"
            )

        # Add email to response
        response = ClientResponse.model_validate(client)
        response.email = user.email
        response.full_name = client.full_name

        return response

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create client: {str(e)}"
        )

@router.get("/", response_model=ClientListResponse)
async def list_clients(
    search: Optional[str] = Query(None, description="Search by name or client ID"),
    status: Optional[str] = Query(None, description="Filter by client status"),
    location_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all clients with filtering and pagination"""

    query = db.query(Client).filter(Client.organization_id == current_user.organization_id)

    # Apply filters
    if search:
        query = query.filter(
            or_(
                Client.first_name.ilike(f"%{search}%"),
                Client.last_name.ilike(f"%{search}%"),
                Client.client_id.ilike(f"%{search}%")
            )
        )

    if status:
        query = query.filter(Client.status == status)

    if location_id:
        query = query.join(ClientAssignment).filter(
            ClientAssignment.location_id == location_id,
            ClientAssignment.is_current == True
        )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    clients = query.offset(offset).limit(page_size).all()

    # Add user emails to response
    client_responses = []
    for client in clients:
        response = ClientResponse.model_validate(client)
        if client.user:
            response.email = client.user.email
        response.full_name = client.full_name
        client_responses.append(response)

    return ClientListResponse(
        items=client_responses,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get client details by ID"""

    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).options(
        joinedload(Client.user),
        joinedload(Client.contacts),
        joinedload(Client.assignments).joinedload(ClientAssignment.location),
        joinedload(Client.care_plans),
        joinedload(Client.medications),
        joinedload(Client.insurance_policies)
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    response = ClientResponse.model_validate(client)
    if client.user:
        response.email = client.user.email
    response.full_name = client.full_name

    return response

@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    client_update: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin", "Organization Admin", "Support Staff"]))
):
    """Update client information"""

    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Update fields
    update_data = client_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    client.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(client)

        response = ClientResponse.model_validate(client)
        if client.user:
            response.email = client.user.email
        response.full_name = client.full_name

        return response

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update client: {str(e)}"
        )

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin"]))
):
    """Soft delete a client"""

    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Soft delete by changing status
    client.status = "inactive"
    client.updated_at = datetime.utcnow()

    # Also deactivate user account if exists
    if client.user:
        client.user.status = UserStatus.INACTIVE

    db.commit()
    return None

@router.post("/{client_id}/discharge", response_model=ClientResponse)
async def discharge_client(
    client_id: UUID,
    discharge_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin", "Organization Admin", "Support Staff"]))
):
    """Discharge a client"""

    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    client.status = "discharged"
    client.discharge_date = discharge_date or datetime.utcnow().date()
    client.updated_at = datetime.utcnow()

    # End current assignments
    current_assignments = db.query(ClientAssignment).filter(
        ClientAssignment.client_id == client_id,
        ClientAssignment.is_current == True
    ).all()

    for assignment in current_assignments:
        assignment.is_current = False
        assignment.end_date = discharge_date or datetime.utcnow().date()

    db.commit()
    db.refresh(client)

    response = ClientResponse.model_validate(client)
    if client.user:
        response.email = client.user.email
    response.full_name = client.full_name

    return response

@router.post("/{client_id}/readmit", response_model=ClientResponse)
async def readmit_client(
    client_id: UUID,
    admission_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin", "Organization Admin", "Support Staff"]))
):
    """Readmit a discharged client"""

    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    if client.status != "discharged":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client is not discharged"
        )

    client.status = "active"
    client.admission_date = admission_date or datetime.utcnow().date()
    client.discharge_date = None
    client.updated_at = datetime.utcnow()

    # Reactivate user account if exists
    if client.user:
        client.user.status = UserStatus.ACTIVE

    db.commit()
    db.refresh(client)

    response = ClientResponse.model_validate(client)
    if client.user:
        response.email = client.user.email
    response.full_name = client.full_name

    return response

# Client Contacts
@router.get("/{client_id}/contacts", response_model=List[ClientContactResponse])
async def list_client_contacts(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all contacts for a client"""

    # Verify client exists and belongs to organization
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    contacts = db.query(ClientContact).filter(
        ClientContact.client_id == client_id
    ).all()

    return contacts

@router.post("/{client_id}/contacts", response_model=ClientContactResponse, status_code=status.HTTP_201_CREATED)
async def add_client_contact(
    client_id: UUID,
    contact_data: ClientContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin", "Organization Admin", "Support Staff"]))
):
    """Add a contact to a client"""

    # Verify client exists and belongs to organization
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    contact = ClientContact(
        client_id=client_id,
        **contact_data.model_dump()
    )

    db.add(contact)
    db.commit()
    db.refresh(contact)

    return contact

@router.put("/{client_id}/contacts/{contact_id}", response_model=ClientContactResponse)
async def update_client_contact(
    client_id: UUID,
    contact_id: UUID,
    contact_update: ClientContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin", "Organization Admin", "Support Staff"]))
):
    """Update a client contact"""

    contact = db.query(ClientContact).join(Client).filter(
        ClientContact.id == contact_id,
        ClientContact.client_id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    update_data = contact_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    contact.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(contact)

    return contact

@router.delete("/{client_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_contact(
    client_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin", "Organization Admin", "Support Staff"]))
):
    """Delete a client contact"""

    contact = db.query(ClientContact).join(Client).filter(
        ClientContact.id == contact_id,
        ClientContact.client_id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    db.delete(contact)
    db.commit()

    return None

@router.put("/{client_id}/permissions", response_model=ClientPermissionResponse)
async def update_client_permissions(
    client_id: UUID,
    permission_update: ClientPermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Super Admin", "Organization Admin"]))
):
    """Update client's role and/or custom permissions."""

    client = db.query(Client).options(
        joinedload(Client.user)
    ).filter(
        Client.id == client_id,
        Client.organization_id == current_user.organization_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    if not client.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client does not have a user account"
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
            client.user.role_id = permission_update.role_id

        # Update custom permissions settings
        client.user.use_custom_permissions = permission_update.use_custom_permissions

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
                client.user.custom_permissions = custom_permissions
            else:
                # Clear custom permissions if none provided
                client.user.custom_permissions = []
        else:
            # Clear custom permissions when not using custom permissions
            client.user.custom_permissions = []

        client.user.updated_at = datetime.utcnow()
        client.updated_at = datetime.utcnow()
        db.commit()

        return ClientPermissionResponse(
            message=f"Permissions updated successfully for {client.full_name}",
            success=True
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update permissions: {str(e)}"
        )