from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

# Import the models
VitalsLog = None
ShiftNote = None
IncidentReport = None

# Vitals Schemas
class VitalsLogCreate(BaseModel):
    client_id: str = Field(..., description="Client ID")
    temperature: Optional[float] = Field(None, ge=90.0, le=110.0, description="Temperature in Fahrenheit")
    blood_pressure_systolic: Optional[int] = Field(None, ge=60, le=300, description="Systolic blood pressure")
    blood_pressure_diastolic: Optional[int] = Field(None, ge=40, le=200, description="Diastolic blood pressure")
    blood_sugar: Optional[float] = Field(None, ge=0.0, le=1000.0, description="Blood sugar level")
    weight: Optional[float] = Field(None, ge=0.0, le=1000.0, description="Weight in pounds")
    heart_rate: Optional[int] = Field(None, ge=30, le=300, description="Heart rate in BPM")
    oxygen_saturation: Optional[float] = Field(None, ge=0.0, le=100.0, description="Oxygen saturation percentage")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    recorded_at: Optional[datetime] = Field(None, description="Time when vitals were recorded")

    @validator('blood_pressure_diastolic')
    def validate_blood_pressure(cls, v, values):
        if 'blood_pressure_systolic' in values:
            systolic = values.get('blood_pressure_systolic')
            if systolic and v and v >= systolic:
                raise ValueError('Diastolic pressure must be less than systolic pressure')
        return v

class VitalsLogResponse(BaseModel):
    id: str
    client_id: str
    client_name: str
    staff_id: str
    staff_name: str
    temperature: Optional[float]
    blood_pressure_systolic: Optional[int]
    blood_pressure_diastolic: Optional[int]
    blood_sugar: Optional[float]
    weight: Optional[float]
    heart_rate: Optional[int]
    oxygen_saturation: Optional[float]
    notes: Optional[str]
    recorded_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

# Shift Notes Schemas
class ShiftNoteCreate(BaseModel):
    client_id: str = Field(..., description="Client ID")
    shift_date: date = Field(..., description="Date of the shift")
    shift_time: str = Field(..., description="Shift time (e.g., '8:00 AM - 4:00 PM')")
    narrative: str = Field(..., min_length=10, max_length=2000, description="Narrative/observations section")
    challenges_faced: Optional[str] = Field(None, max_length=1000, description="Challenges faced during shift")
    support_required: Optional[str] = Field(None, max_length=1000, description="Support required section")
    observations: Optional[str] = Field(None, max_length=1000, description="Additional observations")

class ShiftNoteResponse(BaseModel):
    id: str
    client_id: str
    client_name: str
    staff_id: str
    staff_name: str
    shift_date: date
    shift_time: str
    narrative: str
    challenges_faced: Optional[str]
    support_required: Optional[str]
    observations: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Incident Report Schemas
class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentType(str, Enum):
    FALL = "fall"
    MEDICATION_ERROR = "medication_error"
    INJURY = "injury"
    BEHAVIORAL = "behavioral"
    EMERGENCY = "emergency"
    PROPERTY_DAMAGE = "property_damage"
    OTHER = "other"

class IncidentStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REQUIRES_FOLLOW_UP = "requires_follow_up"

class IncidentReportCreate(BaseModel):
    client_id: str = Field(..., description="Client ID")
    incident_type: IncidentType = Field(..., description="Type of incident")
    description: str = Field(..., min_length=10, max_length=2000, description="Incident description")
    action_taken: str = Field(..., min_length=5, max_length=1000, description="Action taken")
    severity: IncidentSeverity = Field(..., description="Incident severity")
    incident_date: date = Field(..., description="Date when incident occurred")
    incident_time: str = Field(..., description="Time when incident occurred")
    location: Optional[str] = Field(None, max_length=200, description="Location where incident occurred")
    witnesses: Optional[str] = Field(None, max_length=500, description="Witnesses present")
    follow_up_required: bool = Field(default=False, description="Whether follow-up is required")

class IncidentFileInfo(BaseModel):
    id: str = Field(..., description="File ID")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")

class IncidentReportResponse(BaseModel):
    id: str
    client_id: str
    client_name: str
    staff_id: str
    staff_name: str
    incident_type: str
    description: str
    action_taken: str
    severity: str
    incident_date: date
    incident_time: str
    location: Optional[str]
    witnesses: Optional[str]
    follow_up_required: bool
    attached_files: Optional[List[Dict[str, Any]]]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Documentation Entry (Generic)
class DocumentationType(str, Enum):
    VITALS = "vitals"
    SHIFT_NOTE = "shift_note"
    INCIDENT = "incident"
    MEDICATION = "medication"
    ASSESSMENT = "assessment"
    CARE_PLAN = "care_plan"

class DocumentationEntry(BaseModel):
    id: str
    client_id: str
    client_name: str
    staff_id: str
    staff_name: str
    type: DocumentationType
    title: str
    content: str
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Task Management Schemas
class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskCreate(BaseModel):
    client_id: str = Field(..., description="Client ID")
    title: str = Field(..., min_length=5, max_length=200, description="Task title")
    description: Optional[str] = Field(None, max_length=1000, description="Task description")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    assigned_to: Optional[str] = Field(None, description="Staff ID task is assigned to")

class TaskResponse(BaseModel):
    id: str
    client_id: str
    client_name: str
    title: str
    description: Optional[str]
    priority: str
    status: str
    due_date: Optional[datetime]
    assigned_to: Optional[str]
    assigned_to_name: Optional[str]
    created_by: str
    created_by_name: str
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500, description="Update notes")