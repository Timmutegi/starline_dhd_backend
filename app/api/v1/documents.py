"""
Documents API Endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("")
def get_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all documents for the current user's organization"""
    # For now, return empty list since documents aren't fully implemented
    return {"data": [], "total": 0, "page": 1, "page_size": 20}
