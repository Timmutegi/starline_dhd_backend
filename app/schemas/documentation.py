from pydantic import BaseModel, Field, validator
from datetime import datetime, timezone, date
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
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None), description="Upload timestamp")

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

# Meal Logging Schemas
class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

class IntakeAmount(str, Enum):
    NONE = "none"
    MINIMAL = "minimal"
    PARTIAL = "partial"
    MOST = "most"
    ALL = "all"

class MealLogCreate(BaseModel):
    client_id: str = Field(..., description="Client ID")
    meal_type: MealType = Field(..., description="Type of meal")
    meal_date: Optional[datetime] = Field(None, description="Date and time of meal")
    meal_time: Optional[str] = Field(None, max_length=10, description="Meal time (e.g., '08:30 AM')")
    food_items: Optional[List[str]] = Field(None, description="List of food items served")
    intake_amount: Optional[IntakeAmount] = Field(None, description="Overall intake amount")
    percentage_consumed: Optional[int] = Field(None, ge=0, le=100, description="Percentage consumed (0-100)")
    calories: Optional[float] = Field(None, ge=0, description="Calories consumed")
    protein_grams: Optional[float] = Field(None, ge=0, description="Protein in grams")
    carbs_grams: Optional[float] = Field(None, ge=0, description="Carbohydrates in grams")
    fat_grams: Optional[float] = Field(None, ge=0, description="Fat in grams")
    water_intake_ml: Optional[int] = Field(None, ge=0, description="Water intake in milliliters")
    other_fluids: Optional[str] = Field(None, max_length=500, description="Other fluids consumed")
    appetite_level: Optional[str] = Field(None, max_length=50, description="Appetite level (good/fair/poor)")
    dietary_preferences_followed: Optional[bool] = Field(True, description="Dietary preferences followed")
    dietary_restrictions_followed: Optional[bool] = Field(True, description="Dietary restrictions followed")
    assistance_required: Optional[bool] = Field(False, description="Assistance required")
    assistance_type: Optional[str] = Field(None, max_length=500, description="Type of assistance")
    refusals: Optional[str] = Field(None, max_length=500, description="Food refusals")
    allergic_reactions: Optional[str] = Field(None, max_length=500, description="Allergic reactions observed")
    choking_incidents: Optional[bool] = Field(False, description="Choking incidents")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    recommendations: Optional[str] = Field(None, max_length=500, description="Recommendations")
    photo_urls: Optional[List[str]] = Field(None, description="Photo URLs")

class MealLogResponse(BaseModel):
    id: str
    client_id: str
    client_name: str
    staff_id: str
    staff_name: str
    meal_type: str
    meal_date: datetime
    meal_time: Optional[str]
    food_items: Optional[List[str]]
    intake_amount: Optional[str]
    percentage_consumed: Optional[int]
    calories: Optional[float]
    protein_grams: Optional[float]
    carbs_grams: Optional[float]
    fat_grams: Optional[float]
    water_intake_ml: Optional[int]
    other_fluids: Optional[str]
    appetite_level: Optional[str]
    dietary_preferences_followed: bool
    dietary_restrictions_followed: bool
    assistance_required: bool
    assistance_type: Optional[str]
    refusals: Optional[str]
    allergic_reactions: Optional[str]
    choking_incidents: bool
    notes: Optional[str]
    recommendations: Optional[str]
    photo_urls: Optional[List[str]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class MealLogUpdate(BaseModel):
    meal_type: Optional[MealType] = None
    meal_date: Optional[datetime] = None
    meal_time: Optional[str] = Field(None, max_length=10)
    food_items: Optional[List[str]] = None
    intake_amount: Optional[IntakeAmount] = None
    percentage_consumed: Optional[int] = Field(None, ge=0, le=100)
    calories: Optional[float] = Field(None, ge=0)
    protein_grams: Optional[float] = Field(None, ge=0)
    carbs_grams: Optional[float] = Field(None, ge=0)
    fat_grams: Optional[float] = Field(None, ge=0)
    water_intake_ml: Optional[int] = Field(None, ge=0)
    other_fluids: Optional[str] = Field(None, max_length=500)
    appetite_level: Optional[str] = Field(None, max_length=50)
    dietary_preferences_followed: Optional[bool] = None
    dietary_restrictions_followed: Optional[bool] = None
    assistance_required: Optional[bool] = None
    assistance_type: Optional[str] = Field(None, max_length=500)
    refusals: Optional[str] = Field(None, max_length=500)
    allergic_reactions: Optional[str] = Field(None, max_length=500)
    choking_incidents: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)
    recommendations: Optional[str] = Field(None, max_length=500)
    photo_urls: Optional[List[str]] = None

# Activity Logging Schemas
class ActivityType(str, Enum):
    RECREATION = "recreation"
    EXERCISE = "exercise"
    SOCIAL = "social"
    EDUCATIONAL = "educational"
    VOCATIONAL = "vocational"
    THERAPEUTIC = "therapeutic"
    COMMUNITY = "community"
    PERSONAL_CARE = "personal_care"
    OTHER = "other"

class ParticipationLevel(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    REFUSED = "refused"
    UNABLE = "unable"

class Mood(str, Enum):
    HAPPY = "happy"
    CONTENT = "content"
    NEUTRAL = "neutral"
    ANXIOUS = "anxious"
    IRRITABLE = "irritable"
    SAD = "sad"
    ANGRY = "angry"

class ActivityLogCreate(BaseModel):
    client_id: str = Field(..., description="Client ID")
    activity_type: ActivityType = Field(..., description="Type of activity")
    activity_name: str = Field(..., min_length=3, max_length=200, description="Activity name")
    activity_description: Optional[str] = Field(None, max_length=1000, description="Activity description")
    activity_date: Optional[datetime] = Field(None, description="Date and time of activity")
    start_time: Optional[str] = Field(None, max_length=10, description="Start time (e.g., '10:00 AM')")
    end_time: Optional[str] = Field(None, max_length=10, description="End time (e.g., '11:30 AM')")
    duration_minutes: Optional[int] = Field(None, ge=0, le=1440, description="Duration in minutes")
    location: Optional[str] = Field(None, max_length=200, description="Location")
    location_type: Optional[str] = Field(None, max_length=50, description="Location type")
    participation_level: Optional[ParticipationLevel] = Field(None, description="Participation level")
    independence_level: Optional[str] = Field(None, max_length=50, description="Independence level")
    assistance_required: Optional[bool] = Field(False, description="Assistance required")
    assistance_details: Optional[str] = Field(None, max_length=500, description="Assistance details")
    participants: Optional[List[str]] = Field(None, description="Other participants")
    peer_interaction: Optional[bool] = Field(False, description="Peer interaction occurred")
    peer_interaction_quality: Optional[str] = Field(None, max_length=50, description="Peer interaction quality")
    mood_before: Optional[Mood] = Field(None, description="Mood before activity")
    mood_during: Optional[Mood] = Field(None, description="Mood during activity")
    mood_after: Optional[Mood] = Field(None, description="Mood after activity")
    behavior_observations: Optional[str] = Field(None, max_length=1000, description="Behavior observations")
    challenging_behaviors: Optional[str] = Field(None, max_length=500, description="Challenging behaviors")
    skills_practiced: Optional[List[str]] = Field(None, description="Skills practiced")
    skills_progress: Optional[str] = Field(None, max_length=500, description="Skills progress notes")
    goals_addressed: Optional[List[str]] = Field(None, description="Care plan goals addressed")
    engagement_level: Optional[str] = Field(None, max_length=50, description="Engagement level")
    enjoyment_level: Optional[str] = Field(None, max_length=50, description="Enjoyment level")
    focus_attention: Optional[str] = Field(None, max_length=50, description="Focus and attention")
    physical_complaints: Optional[str] = Field(None, max_length=500, description="Physical complaints")
    fatigue_level: Optional[str] = Field(None, max_length=50, description="Fatigue level")
    injuries_incidents: Optional[str] = Field(None, max_length=500, description="Injuries or incidents")
    activity_completed: Optional[bool] = Field(True, description="Activity completed")
    completion_percentage: Optional[int] = Field(None, ge=0, le=100, description="Completion percentage")
    achievements: Optional[str] = Field(None, max_length=500, description="Achievements")
    challenges_faced: Optional[str] = Field(None, max_length=500, description="Challenges faced")
    staff_notes: Optional[str] = Field(None, max_length=1000, description="Staff notes")
    recommendations: Optional[str] = Field(None, max_length=500, description="Recommendations")
    follow_up_needed: Optional[bool] = Field(False, description="Follow-up needed")
    photo_urls: Optional[List[str]] = Field(None, description="Photo URLs")
    video_urls: Optional[List[str]] = Field(None, description="Video URLs")

class ActivityLogResponse(BaseModel):
    id: str
    client_id: str
    client_name: str
    staff_id: str
    staff_name: str
    activity_type: str
    activity_name: str
    activity_description: Optional[str]
    activity_date: datetime
    start_time: Optional[str]
    end_time: Optional[str]
    duration_minutes: Optional[int]
    location: Optional[str]
    location_type: Optional[str]
    participation_level: Optional[str]
    independence_level: Optional[str]
    assistance_required: bool
    assistance_details: Optional[str]
    participants: Optional[List[str]]
    peer_interaction: bool
    peer_interaction_quality: Optional[str]
    mood_before: Optional[str]
    mood_during: Optional[str]
    mood_after: Optional[str]
    behavior_observations: Optional[str]
    challenging_behaviors: Optional[str]
    skills_practiced: Optional[List[str]]
    skills_progress: Optional[str]
    goals_addressed: Optional[List[str]]
    engagement_level: Optional[str]
    enjoyment_level: Optional[str]
    focus_attention: Optional[str]
    physical_complaints: Optional[str]
    fatigue_level: Optional[str]
    injuries_incidents: Optional[str]
    activity_completed: bool
    completion_percentage: Optional[int]
    achievements: Optional[str]
    challenges_faced: Optional[str]
    staff_notes: Optional[str]
    recommendations: Optional[str]
    follow_up_needed: bool
    photo_urls: Optional[List[str]]
    video_urls: Optional[List[str]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class ActivityLogUpdate(BaseModel):
    activity_type: Optional[ActivityType] = None
    activity_name: Optional[str] = Field(None, min_length=3, max_length=200)
    activity_description: Optional[str] = Field(None, max_length=1000)
    activity_date: Optional[datetime] = None
    start_time: Optional[str] = Field(None, max_length=10)
    end_time: Optional[str] = Field(None, max_length=10)
    duration_minutes: Optional[int] = Field(None, ge=0, le=1440)
    location: Optional[str] = Field(None, max_length=200)
    location_type: Optional[str] = Field(None, max_length=50)
    participation_level: Optional[ParticipationLevel] = None
    independence_level: Optional[str] = Field(None, max_length=50)
    assistance_required: Optional[bool] = None
    assistance_details: Optional[str] = Field(None, max_length=500)
    participants: Optional[List[str]] = None
    peer_interaction: Optional[bool] = None
    peer_interaction_quality: Optional[str] = Field(None, max_length=50)
    mood_before: Optional[Mood] = None
    mood_during: Optional[Mood] = None
    mood_after: Optional[Mood] = None
    behavior_observations: Optional[str] = Field(None, max_length=1000)
    challenging_behaviors: Optional[str] = Field(None, max_length=500)
    skills_practiced: Optional[List[str]] = None
    skills_progress: Optional[str] = Field(None, max_length=500)
    goals_addressed: Optional[List[str]] = None
    engagement_level: Optional[str] = Field(None, max_length=50)
    enjoyment_level: Optional[str] = Field(None, max_length=50)
    focus_attention: Optional[str] = Field(None, max_length=50)
    physical_complaints: Optional[str] = Field(None, max_length=500)
    fatigue_level: Optional[str] = Field(None, max_length=50)
    injuries_incidents: Optional[str] = Field(None, max_length=500)
    activity_completed: Optional[bool] = None
    completion_percentage: Optional[int] = Field(None, ge=0, le=100)
    achievements: Optional[str] = Field(None, max_length=500)
    challenges_faced: Optional[str] = Field(None, max_length=500)
    staff_notes: Optional[str] = Field(None, max_length=1000)
    recommendations: Optional[str] = Field(None, max_length=500)
    follow_up_needed: Optional[bool] = None
    photo_urls: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None