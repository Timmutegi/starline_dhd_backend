from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class LocationBase(BaseModel):
    name: str = Field(..., max_length=255, description="Location name")
    address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=20)
    country: str = Field(default="USA", max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    location_type: Optional[str] = Field(None, max_length=50, description="Type of location")
    description: Optional[str] = Field(None, description="Location description")
    notes: Optional[str] = Field(None, description="Additional notes")
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    is_active: bool = Field(default=True)

class LocationCreate(LocationBase):
    pass

class LocationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    location_type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    notes: Optional[str] = None
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None

class LocationResponse(LocationBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
