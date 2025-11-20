"""
Notices API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.notice import Notice, NoticeReadReceipt, NoticePriority, NoticeCategory
from app.schemas.notice import (
    NoticeCreate,
    NoticeUpdate,
    NoticeResponse,
    NoticeReadReceiptCreate,
    NoticeAcknowledgment,
    NoticesList
)

router = APIRouter()


def _check_if_user_should_see_notice(notice: Notice, user: User) -> bool:
    """Check if user should see this notice based on targeting"""

    # Check if notice is active and published
    if not notice.is_active:
        return False

    if notice.publish_date and notice.publish_date > datetime.now(timezone.utc).replace(tzinfo=None):
        return False

    if notice.expire_date and notice.expire_date < datetime.now(timezone.utc).replace(tzinfo=None):
        return False

    # Check role targeting
    if notice.target_roles:
        if str(user.role_id) not in notice.target_roles:
            return False

    # Check user targeting
    if notice.target_users:
        if str(user.id) not in notice.target_users:
            return False

    return True


@router.get("", response_model=NoticesList)
def get_notices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    priority: Optional[NoticePriority] = Query(None),
    category: Optional[NoticeCategory] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notices for current user"""

    # Get all notices for user's organization
    query = db.query(Notice).filter(
        Notice.organization_id == current_user.organization_id,
        Notice.is_active == True
    )

    # Filter by priority
    if priority:
        query = query.filter(Notice.priority == priority)

    # Filter by category
    if category:
        query = query.filter(Notice.category == category)

    # Get all notices (we'll filter by targeting in Python)
    all_notices = query.order_by(Notice.created_at.desc()).all()

    # Filter notices based on targeting rules
    filtered_notices = [
        notice for notice in all_notices
        if _check_if_user_should_see_notice(notice, current_user)
    ]

    # Get user's read receipts
    read_notice_ids = db.query(NoticeReadReceipt.notice_id).filter(
        NoticeReadReceipt.user_id == str(current_user.id)
    ).all()
    read_notice_ids = {str(nid[0]) for nid in read_notice_ids}

    # Get user's acknowledged notices
    acknowledged_notice_ids = db.query(NoticeReadReceipt.notice_id).filter(
        NoticeReadReceipt.user_id == str(current_user.id),
        NoticeReadReceipt.acknowledged_at.isnot(None)
    ).all()
    acknowledged_notice_ids = {str(nid[0]) for nid in acknowledged_notice_ids}

    # Filter for unread only if requested
    if unread_only:
        filtered_notices = [
            notice for notice in filtered_notices
            if notice.id not in read_notice_ids
        ]

    # Count unread
    unread_count = sum(1 for notice in filtered_notices if notice.id not in read_notice_ids)

    # Pagination
    total = len(filtered_notices)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_notices = filtered_notices[start:end]

    # Build response with read status
    notices_response = []
    for notice in paginated_notices:
        notice_dict = {
            "id": str(notice.id),
            "organization_id": str(notice.organization_id),
            "title": notice.title,
            "content": notice.content,
            "summary": notice.summary,
            "priority": notice.priority,
            "category": notice.category,
            "target_roles": notice.target_roles,
            "target_users": notice.target_users,
            "is_active": notice.is_active,
            "publish_date": notice.publish_date,
            "expire_date": notice.expire_date,
            "requires_acknowledgment": notice.requires_acknowledgment,
            "attachment_urls": notice.attachment_urls,
            "created_at": notice.created_at,
            "updated_at": notice.updated_at,
            "created_by": str(notice.created_by),
            "read": notice.id in read_notice_ids,
            "acknowledged": notice.id in acknowledged_notice_ids
        }
        notices_response.append(NoticeResponse(**notice_dict))

    return NoticesList(
        notices=notices_response,
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count
    )


@router.post("", response_model=NoticeResponse)
def create_notice(
    notice_data: NoticeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new notice"""
    # Create notice
    notice = Notice(
        organization_id=current_user.organization_id,
        title=notice_data.title,
        content=notice_data.content,
        summary=notice_data.summary,
        priority=notice_data.priority,
        category=notice_data.category,
        target_roles=notice_data.target_roles,
        target_users=notice_data.target_users,
        is_active=True,  # Default to active
        publish_date=notice_data.publish_date,
        expire_date=notice_data.expire_date,
        requires_acknowledgment=notice_data.requires_acknowledgment,
        attachment_urls=notice_data.attachment_urls,
        created_by=current_user.id
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)

    return NoticeResponse(
        id=str(notice.id),
        organization_id=str(notice.organization_id),
        title=notice.title,
        content=notice.content,
        summary=notice.summary,
        priority=notice.priority.value,
        category=notice.category.value,
        target_roles=notice.target_roles,
        target_users=notice.target_users,
        is_active=notice.is_active,
        publish_date=notice.publish_date,
        expire_date=notice.expire_date,
        requires_acknowledgment=notice.requires_acknowledgment,
        attachment_urls=notice.attachment_urls,
        created_at=notice.created_at,
        updated_at=notice.updated_at,
        created_by=str(notice.created_by),
        read=False,
        acknowledged=False
    )


@router.post("/{notice_id}/read", response_model=dict)
def mark_notice_as_read(
    notice_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notice as read"""

    # Verify notice exists and user can see it
    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    if not _check_if_user_should_see_notice(notice, current_user):
        raise HTTPException(status_code=403, detail="You don't have access to this notice")

    # Check if already read
    existing_receipt = db.query(NoticeReadReceipt).filter(
        NoticeReadReceipt.notice_id == notice_id,
        NoticeReadReceipt.user_id == str(current_user.id)
    ).first()

    if existing_receipt:
        return {"message": "Notice already marked as read"}

    # Create read receipt
    receipt = NoticeReadReceipt(
        notice_id=notice_id,
        user_id=str(current_user.id)
    )
    db.add(receipt)
    db.commit()

    return {"message": "Notice marked as read"}


@router.post("/{notice_id}/acknowledge", response_model=dict)
def acknowledge_notice(
    notice_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Acknowledge a notice"""

    # Verify notice exists and user can see it
    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    if not _check_if_user_should_see_notice(notice, current_user):
        raise HTTPException(status_code=403, detail="You don't have access to this notice")

    # Get or create read receipt
    receipt = db.query(NoticeReadReceipt).filter(
        NoticeReadReceipt.notice_id == notice_id,
        NoticeReadReceipt.user_id == str(current_user.id)
    ).first()

    if not receipt:
        receipt = NoticeReadReceipt(
            notice_id=notice_id,
            user_id=str(current_user.id)
        )
        db.add(receipt)

    # Mark as acknowledged
    receipt.acknowledged_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    return {"message": "Notice acknowledged"}


@router.get("/{notice_id}", response_model=NoticeResponse)
def get_notice_by_id(
    notice_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific notice by ID"""

    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    if not _check_if_user_should_see_notice(notice, current_user):
        raise HTTPException(status_code=403, detail="You don't have access to this notice")

    # Check if user has read this notice
    read_receipt = db.query(NoticeReadReceipt).filter(
        NoticeReadReceipt.notice_id == notice_id,
        NoticeReadReceipt.user_id == str(current_user.id)
    ).first()

    notice_dict = {
        "id": notice.id,
        "organization_id": str(notice.organization_id),
        "title": notice.title,
        "content": notice.content,
        "summary": notice.summary,
        "priority": notice.priority,
        "category": notice.category,
        "target_roles": notice.target_roles,
        "target_users": notice.target_users,
        "is_active": notice.is_active,
        "publish_date": notice.publish_date,
        "expire_date": notice.expire_date,
        "requires_acknowledgment": notice.requires_acknowledgment,
        "attachment_urls": notice.attachment_urls,
        "created_at": notice.created_at,
        "updated_at": notice.updated_at,
        "created_by": str(notice.created_by),
        "read": read_receipt is not None,
        "acknowledged": read_receipt.acknowledged_at is not None if read_receipt else False
    }

    # Automatically mark as read if not already
    if not read_receipt:
        receipt = NoticeReadReceipt(
            notice_id=notice_id,
            user_id=str(current_user.id)
        )
        db.add(receipt)
        db.commit()

    return NoticeResponse(**notice_dict)


# Admin endpoints for creating/updating notices would go here
# For now, we'll use the seed script to create notices
