from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_manager_or_above
from app.models.user import User
from app.models.location import Location
from app.schemas.location import LocationCreate, LocationUpdate, LocationResponse

router = APIRouter(prefix="/locations", tags=["locations"])

@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    location_data: LocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_or_above)
):
    """
    Create a new location (Manager or above)
    """
    try:
        new_location = Location(
            organization_id=current_user.organization_id,
            name=location_data.name,
            address=location_data.address,
            city=location_data.city,
            state=location_data.state,
            zip_code=location_data.zip_code,
            country=location_data.country,
            phone=location_data.phone,
            email=location_data.email,
            location_type=location_data.location_type,
            description=location_data.description,
            notes=location_data.notes,
            latitude=location_data.latitude,
            longitude=location_data.longitude,
            is_active=location_data.is_active
        )

        db.add(new_location)
        db.commit()
        db.refresh(new_location)

        return LocationResponse.model_validate(new_location)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create location: {str(e)}"
        )

@router.get("", response_model=List[LocationResponse])
async def get_locations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_active: Optional[bool] = None,
    location_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all locations for the organization
    """
    try:
        query = db.query(Location).filter(
            Location.organization_id == current_user.organization_id
        )

        # Apply filters
        if is_active is not None:
            query = query.filter(Location.is_active == is_active)

        if location_type:
            query = query.filter(Location.location_type == location_type)

        if search:
            query = query.filter(
                Location.name.ilike(f"%{search}%") |
                Location.address.ilike(f"%{search}%") |
                Location.city.ilike(f"%{search}%")
            )

        locations = query.order_by(Location.name).offset(skip).limit(limit).all()

        return [LocationResponse.model_validate(loc) for loc in locations]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve locations: {str(e)}"
        )

@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific location by ID
    """
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.organization_id == current_user.organization_id
    ).first()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )

    return LocationResponse.model_validate(location)

@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: UUID,
    location_data: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_or_above)
):
    """
    Update a location (Manager or above)
    """
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.organization_id == current_user.organization_id
    ).first()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )

    try:
        # Update fields
        update_data = location_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(location, field, value)

        db.commit()
        db.refresh(location)

        return LocationResponse.model_validate(location)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update location: {str(e)}"
        )

@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_manager_or_above)
):
    """
    Delete a location (Manager or above)
    """
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.organization_id == current_user.organization_id
    ).first()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )

    try:
        db.delete(location)
        db.commit()
        return None

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete location: {str(e)}"
        )
