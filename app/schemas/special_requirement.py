from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from typing import Optional, List
from enum import Enum
import uuid


class PriorityLevel(str, Enum):
    """Priority level for special requirements"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequirementStatus(str, Enum):
    """Status of special requirement"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    DRAFT = "draft"


class ActionPlanItem(BaseModel):
    """Single action plan item that DSP must acknowledge"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique item ID")
    text: str = Field(..., min_length=1, max_length=500, description="Action item text")
    order: int = Field(..., ge=0, description="Display order")


# ==================== MANAGER SCHEMAS ====================

class SpecialRequirementCreate(BaseModel):
    """Schema for manager creating a new special requirement"""
    client_id: str = Field(..., description="Client ID")
    title: str = Field(..., min_length=3, max_length=255, description="Requirement title")
    instructions: str = Field(..., min_length=10, max_length=5000, description="Detailed instructions for DSP")
    action_plan_items: List[ActionPlanItem] = Field(..., min_items=1, description="Action plan checkbox items")
    start_date: date = Field(..., description="Start date of requirement")
    end_date: date = Field(..., description="End date of requirement")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="Priority level")

    @validator('end_date')
    def end_date_after_start(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after or equal to start date')
        return v

    @validator('action_plan_items')
    def validate_action_items(cls, v):
        if len(v) == 0:
            raise ValueError('At least one action plan item is required')
        if len(v) > 20:
            raise ValueError('Maximum 20 action plan items allowed')
        return v


class SpecialRequirementUpdate(BaseModel):
    """Schema for manager updating a special requirement"""
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    instructions: Optional[str] = Field(None, min_length=10, max_length=5000)
    action_plan_items: Optional[List[ActionPlanItem]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    priority: Optional[PriorityLevel] = None
    status: Optional[RequirementStatus] = None

    @validator('action_plan_items')
    def validate_action_items(cls, v):
        if v is not None:
            if len(v) == 0:
                raise ValueError('At least one action plan item is required')
            if len(v) > 20:
                raise ValueError('Maximum 20 action plan items allowed')
        return v


class SpecialRequirementSchema(BaseModel):
    """Response schema for special requirement"""
    id: str
    organization_id: str
    client_id: str
    client_name: str
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    title: str
    instructions: str
    action_plan_items: List[ActionPlanItem]
    start_date: date
    end_date: date
    priority: str
    status: str
    is_active: bool  # Computed: status == active AND current date within range
    response_count: int = 0  # Count of DSP responses
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== DSP RESPONSE SCHEMAS ====================

class SpecialRequirementResponseCreate(BaseModel):
    """Schema for DSP submitting response to a special requirement"""
    special_requirement_id: str = Field(..., description="Special requirement ID")
    client_id: str = Field(..., description="Client ID")
    instructions_acknowledged: bool = Field(..., description="DSP acknowledged instructions")
    acknowledged_items: List[str] = Field(..., description="List of acknowledged action item IDs")
    intervention_notes: str = Field(..., min_length=10, max_length=2000, description="What DSP actually did")
    is_certified: bool = Field(..., description="DSP certifies completion")

    @validator('instructions_acknowledged')
    def must_acknowledge_instructions(cls, v):
        if not v:
            raise ValueError('You must acknowledge that you have read the instructions')
        return v

    @validator('acknowledged_items')
    def validate_acknowledged_items(cls, v):
        if len(v) == 0:
            raise ValueError('At least one action item must be acknowledged')
        return v

    @validator('is_certified')
    def must_certify(cls, v):
        if not v:
            raise ValueError('You must certify your response for legal compliance')
        return v


class SpecialRequirementResponseSchema(BaseModel):
    """Response schema for DSP's special requirement response"""
    id: str
    special_requirement_id: str
    requirement_title: str
    client_id: str
    client_name: str
    staff_id: str
    staff_name: str
    shift_id: Optional[str] = None
    instructions_acknowledged: bool
    acknowledged_items: List[str]
    intervention_notes: Optional[str] = None
    is_certified: bool
    certification_statement: Optional[str] = None
    certified_at: Optional[datetime] = None
    shift_date: date
    shift_start_time: Optional[str] = None
    shift_end_time: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== DSP VIEW SCHEMAS ====================

class ActiveSpecialRequirementForDSP(BaseModel):
    """Schema for DSP viewing active requirements"""
    id: str
    title: str
    instructions: str
    action_plan_items: List[ActionPlanItem]
    priority: str
    client_id: str
    client_name: str
    start_date: date
    end_date: date
    has_response_this_shift: bool = False  # Whether DSP already responded this shift
    existing_response_id: Optional[str] = None  # ID of existing response if any

    class Config:
        from_attributes = True


class PendingSpecialRequirement(BaseModel):
    """Schema for pending requirements in DSP dashboard alert"""
    id: str
    title: str
    priority: str
    client_id: str
    client_name: str

    class Config:
        from_attributes = True


class PendingRequirementsAlert(BaseModel):
    """Schema for DSP dashboard alert showing pending requirements"""
    total_pending: int
    highest_priority: str
    requirements: List[PendingSpecialRequirement]

    class Config:
        from_attributes = True


# ==================== LIST/FILTER SCHEMAS ====================

class SpecialRequirementListResponse(BaseModel):
    """Paginated list of special requirements"""
    data: List[SpecialRequirementSchema]
    pagination: dict

    class Config:
        from_attributes = True


class SpecialRequirementResponseListResponse(BaseModel):
    """Paginated list of DSP responses"""
    data: List[SpecialRequirementResponseSchema]
    pagination: dict

    class Config:
        from_attributes = True
