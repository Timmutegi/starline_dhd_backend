from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date
from uuid import UUID

# Type aliases using Literal for better validation
ClientStatusType = Literal["active", "inactive", "discharged", "deceased", "on_hold"]
GenderType = Literal["male", "female", "other", "prefer_not_to_say"]
ContactTypeType = Literal["emergency", "primary", "guardian", "power_of_attorney", "physician", "case_manager"]
LocationTypeType = Literal["residential", "day_program", "workshop", "community"]
PlanTypeType = Literal["ISP", "behavior", "medical", "dietary", "therapy"]
PlanStatusType = Literal["draft", "active", "under_review", "expired", "archived"]
NoteTypeType = Literal["general", "medical", "behavioral", "incident", "progress"]
InsuranceTypeType = Literal["primary", "secondary", "tertiary"]

# Client schemas
class ClientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    preferred_name: Optional[str] = Field(None, max_length=100)
    date_of_birth: date
    gender: GenderType
    ssn_encrypted: Optional[str] = None
    primary_diagnosis: Optional[str] = None
    secondary_diagnoses: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None

class ClientCreate(ClientBase):
    email: EmailStr
    send_credentials: bool = True
    admission_date: Optional[date] = None
    # Role and permission assignment for client user account
    role_id: Optional[UUID] = None
    custom_permission_ids: Optional[List[UUID]] = None
    use_custom_permissions: bool = False

    @validator('admission_date', pre=True, always=True)
    def set_admission_date(cls, v):
        return v or date.today()

class ClientUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    preferred_name: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[GenderType] = None
    status: Optional[ClientStatusType] = None
    primary_diagnosis: Optional[str] = None
    secondary_diagnoses: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None
    discharge_date: Optional[date] = None

class ClientResponse(ClientBase):
    id: UUID
    organization_id: UUID
    client_id: str
    user_id: Optional[UUID] = None
    photo_url: Optional[str] = None
    status: ClientStatusType
    admission_date: date
    discharge_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None
    reporting_days: Optional[List[str]] = None
    last_interaction: Optional[datetime] = None

    class Config:
        from_attributes = True

class ClientCreateResponse(BaseModel):
    client: ClientResponse
    temporary_password: str
    username: str
    message: str
    success: bool = True

class ClientListResponse(BaseModel):
    items: List[ClientResponse]
    total: int
    page: int
    page_size: int
    pages: int

# Contact schemas
class ClientContactBase(BaseModel):
    contact_type: ContactTypeType
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    relationship_type: Optional[str] = Field(None, max_length=100)
    phone_primary: str = Field(..., min_length=1, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_primary: bool = False
    can_make_decisions: bool = False
    notes: Optional[str] = None

class ClientContactCreate(ClientContactBase):
    pass

class ClientContactUpdate(BaseModel):
    contact_type: Optional[ContactTypeType] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    relationship_type: Optional[str] = Field(None, max_length=100)
    phone_primary: Optional[str] = Field(None, min_length=1, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_primary: Optional[bool] = None
    can_make_decisions: Optional[bool] = None
    notes: Optional[str] = None

class ClientContactResponse(ClientContactBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Location schemas
class ClientLocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=50)
    zip_code: str = Field(..., min_length=1, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)
    type: LocationTypeType
    capacity: Optional[int] = None
    manager_id: Optional[UUID] = None

class ClientLocationCreate(ClientLocationBase):
    pass

class ClientLocationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=50)
    zip_code: Optional[str] = Field(None, min_length=1, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)
    type: Optional[LocationTypeType] = None
    capacity: Optional[int] = None
    manager_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class ClientLocationResponse(ClientLocationBase):
    id: UUID
    organization_id: UUID
    current_occupancy: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Assignment schemas
class ClientAssignmentBase(BaseModel):
    location_id: UUID
    room_number: Optional[str] = Field(None, max_length=50)
    bed_number: Optional[str] = Field(None, max_length=50)
    start_date: date

class ClientAssignmentCreate(ClientAssignmentBase):
    pass

class ClientAssignmentUpdate(BaseModel):
    location_id: Optional[UUID] = None
    room_number: Optional[str] = Field(None, max_length=50)
    bed_number: Optional[str] = Field(None, max_length=50)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None

class ClientAssignmentResponse(ClientAssignmentBase):
    id: UUID
    client_id: UUID
    end_date: Optional[date] = None
    is_current: bool
    created_at: datetime
    updated_at: datetime
    location: Optional[ClientLocationResponse] = None

    class Config:
        from_attributes = True

# Care Plan schemas
class CarePlanBase(BaseModel):
    plan_type: PlanTypeType
    title: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: Optional[date] = None
    review_date: Optional[date] = None
    goals: Optional[Dict[str, Any]] = None
    interventions: Optional[Dict[str, Any]] = None
    responsible_staff: Optional[List[UUID]] = None
    document_url: Optional[str] = None

class CarePlanCreate(CarePlanBase):
    pass

class CarePlanUpdate(BaseModel):
    plan_type: Optional[PlanTypeType] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    review_date: Optional[date] = None
    status: Optional[PlanStatusType] = None
    goals: Optional[Dict[str, Any]] = None
    interventions: Optional[Dict[str, Any]] = None
    responsible_staff: Optional[List[UUID]] = None
    document_url: Optional[str] = None

class CarePlanResponse(CarePlanBase):
    id: UUID
    client_id: UUID
    status: PlanStatusType
    created_by: Optional[UUID] = None
    approved_by: Optional[UUID] = None
    approved_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Note schemas
class ClientNoteBase(BaseModel):
    note_type: NoteTypeType
    subject: str = Field(..., min_length=1, max_length=255)
    content: str
    is_confidential: bool = False

class ClientNoteCreate(ClientNoteBase):
    pass

class ClientNoteUpdate(BaseModel):
    note_type: Optional[NoteTypeType] = None
    subject: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    is_confidential: Optional[bool] = None

class ClientNoteResponse(ClientNoteBase):
    id: UUID
    client_id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Medication schemas
class ClientMedicationBase(BaseModel):
    medication_name: str = Field(..., min_length=1, max_length=255)
    generic_name: Optional[str] = Field(None, max_length=255)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    route: str = Field(..., min_length=1, max_length=50)
    prescriber_name: Optional[str] = Field(None, max_length=255)
    prescriber_phone: Optional[str] = Field(None, max_length=20)
    pharmacy_name: Optional[str] = Field(None, max_length=255)
    pharmacy_phone: Optional[str] = Field(None, max_length=20)
    start_date: date
    is_prn: bool = False
    prn_instructions: Optional[str] = None
    side_effects: Optional[str] = None
    notes: Optional[str] = None

class ClientMedicationCreate(ClientMedicationBase):
    pass

class ClientMedicationUpdate(BaseModel):
    medication_name: Optional[str] = Field(None, min_length=1, max_length=255)
    generic_name: Optional[str] = Field(None, max_length=255)
    dosage: Optional[str] = Field(None, min_length=1, max_length=100)
    frequency: Optional[str] = Field(None, min_length=1, max_length=100)
    route: Optional[str] = Field(None, min_length=1, max_length=50)
    prescriber_name: Optional[str] = Field(None, max_length=255)
    prescriber_phone: Optional[str] = Field(None, max_length=20)
    pharmacy_name: Optional[str] = Field(None, max_length=255)
    pharmacy_phone: Optional[str] = Field(None, max_length=20)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    is_prn: Optional[bool] = None
    prn_instructions: Optional[str] = None
    side_effects: Optional[str] = None
    notes: Optional[str] = None

class ClientMedicationResponse(ClientMedicationBase):
    id: UUID
    client_id: UUID
    end_date: Optional[date] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Insurance schemas
class ClientInsuranceBase(BaseModel):
    insurance_type: InsuranceTypeType
    company_name: str = Field(..., min_length=1, max_length=255)
    policy_number: str = Field(..., min_length=1, max_length=100)
    group_number: Optional[str] = Field(None, max_length=100)
    subscriber_name: str = Field(..., min_length=1, max_length=255)
    subscriber_dob: Optional[date] = None
    subscriber_relationship: Optional[str] = Field(None, max_length=50)
    effective_date: date
    expiration_date: Optional[date] = None
    copay_amount: Optional[float] = None
    deductible: Optional[float] = None
    out_of_pocket_max: Optional[float] = None

class ClientInsuranceCreate(ClientInsuranceBase):
    pass

class ClientInsuranceUpdate(BaseModel):
    insurance_type: Optional[InsuranceTypeType] = None
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    policy_number: Optional[str] = Field(None, min_length=1, max_length=100)
    group_number: Optional[str] = Field(None, max_length=100)
    subscriber_name: Optional[str] = Field(None, min_length=1, max_length=255)
    subscriber_dob: Optional[date] = None
    subscriber_relationship: Optional[str] = Field(None, max_length=50)
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    copay_amount: Optional[float] = None
    deductible: Optional[float] = None
    out_of_pocket_max: Optional[float] = None
    is_active: Optional[bool] = None

class ClientInsuranceResponse(ClientInsuranceBase):
    id: UUID
    client_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Search and filter schemas
class ClientSearchParams(BaseModel):
    name: Optional[str] = None
    client_id: Optional[str] = None
    date_of_birth: Optional[date] = None
    status: Optional[ClientStatusType] = None
    location_id: Optional[UUID] = None
    program_id: Optional[UUID] = None
    assigned_staff: Optional[UUID] = None
    diagnosis: Optional[str] = None
    insurance_provider: Optional[str] = None
    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"

# Permission assignment schemas for clients
class ClientPermissionUpdate(BaseModel):
    role_id: Optional[UUID] = None
    custom_permission_ids: Optional[List[UUID]] = None
    use_custom_permissions: bool = False

class ClientPermissionResponse(BaseModel):
    message: str
    success: bool