from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.notification import Notification, NotificationTypeEnum, NotificationCategoryEnum
from app.schemas.notification import (
    NotificationResponse,
    NotificationCreate,
    NotificationUpdate,
    NotificationStats,
    BulkNotificationAction
)
from app.schemas.common import PaginatedResponse, PaginationMeta

router = APIRouter()

@router.get("/", response_model=PaginatedResponse[NotificationResponse])
async def get_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    type: Optional[str] = Query(None, description="Filter by notification type"),
    category: Optional[str] = Query(None, description="Filter by notification category"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of notifications per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notifications for the current user
    """
    try:
        query = db.query(Notification).filter(
            and_(
                Notification.user_id == current_user.id,
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > datetime.now(timezone.utc)
                )
            )
        )

        if is_read is not None:
            query = query.filter(Notification.is_read == is_read)

        if type:
            try:
                notification_type = NotificationTypeEnum(type)
                query = query.filter(Notification.type == notification_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid notification type: {type}")

        if category:
            try:
                notification_category = NotificationCategoryEnum(category)
                query = query.filter(Notification.category == notification_category)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid notification category: {category}")

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        notifications = query.order_by(
            Notification.is_read.asc(),  # Unread first
            Notification.created_at.desc()  # Most recent first
        ).offset(offset).limit(page_size).all()

        # Build response
        notification_responses = [
            NotificationResponse(
                id=str(notification.id),
                title=notification.title,
                message=notification.message,
                type=notification.type.value,
                category=notification.category.value,
                is_read=notification.is_read,
                read_at=notification.read_at,
                action_url=notification.action_url,
                action_text=notification.action_text,
                related_entity_type=notification.related_entity_type,
                related_entity_id=str(notification.related_entity_id) if notification.related_entity_id else None,
                metadata=notification.additional_data,
                created_at=notification.created_at,
                expires_at=notification.expires_at
            )
            for notification in notifications
        ]

        # Calculate total pages
        pages = (total + page_size - 1) // page_size

        return PaginatedResponse(
            data=notification_responses,
            pagination=PaginationMeta(
                total=total,
                page=page,
                page_size=page_size,
                pages=pages
            )
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve notifications: {str(e)}"
        )

@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notification statistics for the current user
    """
    try:
        base_query = db.query(Notification).filter(
            and_(
                Notification.user_id == current_user.id,
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > datetime.now(timezone.utc)
                )
            )
        )

        total_count = base_query.count()
        unread_count = base_query.filter(Notification.is_read == False).count()

        # Count by type
        critical_count = base_query.filter(
            and_(
                Notification.type == NotificationTypeEnum.CRITICAL,
                Notification.is_read == False
            )
        ).count()

        reminder_count = base_query.filter(
            and_(
                Notification.type == NotificationTypeEnum.REMINDER,
                Notification.is_read == False
            )
        ).count()

        info_count = base_query.filter(
            and_(
                Notification.type == NotificationTypeEnum.INFO,
                Notification.is_read == False
            )
        ).count()

        return NotificationStats(
            total_count=total_count,
            unread_count=unread_count,
            critical_count=critical_count,
            reminder_count=reminder_count,
            info_count=info_count
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve notification stats: {str(e)}"
        )

@router.post("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a specific notification as read
    """
    try:
        notification = db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id
            )
        ).first()

        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            db.commit()

        return {"message": "Notification marked as read", "id": notification_id}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark notification as read: {str(e)}"
        )

@router.post("/mark-all-read")
async def mark_all_notifications_as_read(
    type: Optional[str] = Query(None, description="Optional filter by type"),
    category: Optional[str] = Query(None, description="Optional filter by category"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark all notifications as read for the current user
    """
    try:
        query = db.query(Notification).filter(
            and_(
                Notification.user_id == current_user.id,
                Notification.is_read == False
            )
        )

        if type:
            try:
                notification_type = NotificationTypeEnum(type)
                query = query.filter(Notification.type == notification_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid notification type: {type}")

        if category:
            try:
                notification_category = NotificationCategoryEnum(category)
                query = query.filter(Notification.category == notification_category)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid notification category: {category}")

        updated_count = query.update({
            "is_read": True,
            "read_at": datetime.now(timezone.utc)
        })

        db.commit()

        return {"message": f"Marked {updated_count} notifications as read"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark all notifications as read: {str(e)}"
        )

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a specific notification
    """
    try:
        notification = db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id
            )
        ).first()

        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        db.delete(notification)
        db.commit()

        return {"message": "Notification deleted", "id": notification_id}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete notification: {str(e)}"
        )

@router.post("/clear-old")
async def clear_old_notifications(
    days_old: int = Query(30, ge=1, description="Delete notifications older than this many days"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear old notifications for the current user
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

        deleted_count = db.query(Notification).filter(
            and_(
                Notification.user_id == current_user.id,
                Notification.created_at < cutoff_date,
                Notification.is_read == True  # Only delete read notifications
            )
        ).delete()

        db.commit()

        return {"message": f"Deleted {deleted_count} old notifications"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear old notifications: {str(e)}"
        )

# Admin/System endpoints for creating notifications
@router.post("/create", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new notification (admin/system use)
    """
    try:
        # Check if user has permission to create notifications
        # This would typically require admin role or system permissions

        notification = Notification(
            user_id=notification_data.user_id,
            organization_id=current_user.organization_id,
            title=notification_data.title,
            message=notification_data.message,
            type=NotificationTypeEnum(notification_data.type),
            category=NotificationCategoryEnum(notification_data.category),
            action_url=notification_data.action_url,
            action_text=notification_data.action_text,
            related_entity_type=notification_data.related_entity_type,
            related_entity_id=notification_data.related_entity_id,
            additional_data=notification_data.metadata,
            expires_at=notification_data.expires_at
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)

        return NotificationResponse(
            id=str(notification.id),
            title=notification.title,
            message=notification.message,
            type=notification.type.value,
            category=notification.category.value,
            is_read=notification.is_read,
            read_at=notification.read_at,
            action_url=notification.action_url,
            action_text=notification.action_text,
            related_entity_type=notification.related_entity_type,
            related_entity_id=str(notification.related_entity_id) if notification.related_entity_id else None,
            metadata=notification.additional_data,
            created_at=notification.created_at,
            expires_at=notification.expires_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create notification: {str(e)}"
        )