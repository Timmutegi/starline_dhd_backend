from pydantic import BaseModel
from typing import Generic, TypeVar, List
from datetime import datetime

# Generic type for paginated data
DataT = TypeVar('DataT')

class PaginationMeta(BaseModel):
    """Pagination metadata"""
    total: int
    page: int
    page_size: int
    pages: int

    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel, Generic[DataT]):
    """Standardized paginated response wrapper for all list endpoints"""
    data: List[DataT]
    pagination: PaginationMeta

    class Config:
        from_attributes = True
