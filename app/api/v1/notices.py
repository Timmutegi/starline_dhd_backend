"""
Notices API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_manager_or_above
from app.models.user import User, UserStatus
from app.models.notice import Notice, NoticeReadReceipt, NoticePriority, NoticeCategory, NoticeTargetType
from app.models.staff import Staff, StaffAssignment
from app.models.client import Client
from app.models.location import Location
from app.schemas.notice import (
    NoticeCreate,
    NoticeUpdate,
    NoticeResponse,
    NoticeReadReceiptCreate,
    NoticeAcknowledgment,
    NoticesList,
    NoticeStatistics,
    NoticeAcknowledgmentDetail,
    TargetableUser,
    TargetableClient,
    TargetableLocation
)

router = APIRouter()


def _check_if_user_should_see_notice(notice: Notice, user: User, db: Session) -> bool:
    """Check if user should see this notice based on targeting"""

    # Check if notice is active and published
    if not notice.is_active:
        return False

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if notice.publish_date and notice.publish_date > now:
        return False

    if notice.expire_date and notice.expire_date < now:
        return False

    # Exclude clients from all notices
    if user.role and user.role.name.lower() == "client":
        return False

    # Handle targeting based on target_type
    target_type = notice.target_type

    if target_type == NoticeTargetType.ALL_USERS:
        return True  # All non-client users

    elif target_type == NoticeTargetType.SPECIFIC_USERS:
        if notice.target_users:
            return str(user.id) in notice.target_users
        return False

    elif target_type == NoticeTargetType.CLIENT_ASSIGNMENT:
        if notice.target_client_id:
            # Get staff record for this user
            staff = db.query(Staff).filter(
                Staff.user_id == user.id,
                Staff.organization_id == user.organization_id
            ).first()

            if not staff:
                return False

            # Check if staff is assigned to the target client
            assignment = db.query(StaffAssignment).filter(
                StaffAssignment.staff_id == staff.id,
                StaffAssignment.client_id == notice.target_client_id,
                StaffAssignment.is_active == True
            ).first()

            return assignment is not None
        return False

    elif target_type == NoticeTargetType.LOCATION:
        if notice.target_location_id:
            # Get staff record for this user
            staff = db.query(Staff).filter(
                Staff.user_id == user.id,
                Staff.organization_id == user.organization_id
            ).first()

            if not staff:
                return False

            # Check direct location assignment
            direct_assignment = db.query(StaffAssignment).filter(
                StaffAssignment.staff_id == staff.id,
                StaffAssignment.location_id == notice.target_location_id,
                StaffAssignment.is_active == True
            ).first()

            if direct_assignment:
                return True

            # Check via clients at location
            clients_at_location = db.query(Client.id).filter(
                Client.location_id == notice.target_location_id,
                Client.organization_id == user.organization_id
            ).all()

            if clients_at_location:
                client_ids = [c[0] for c in clients_at_location]
                client_assignment = db.query(StaffAssignment).filter(
                    StaffAssignment.staff_id == staff.id,
                    StaffAssignment.client_id.in_(client_ids),
                    StaffAssignment.is_active == True
                ).first()
                return client_assignment is not None
        return False

    # Legacy support for target_roles (if target_type is not set properly)
    if notice.target_roles:
        return str(user.role_id) in notice.target_roles

    return True


def _get_targeted_user_ids(notice: Notice, db: Session) -> List[str]:
    """Get list of all user IDs targeted by a notice"""
    org_id = notice.organization_id
    target_type = notice.target_type

    if target_type == NoticeTargetType.ALL_USERS:
        # All active users in organization excluding clients
        users = db.query(User).filter(
            User.organization_id == org_id,
            User.status == UserStatus.ACTIVE
        ).all()
        # Filter out clients
        return [str(u.id) for u in users if not (u.role and u.role.name.lower() == "client")]

    elif target_type == NoticeTargetType.SPECIFIC_USERS:
        return notice.target_users or []

    elif target_type == NoticeTargetType.CLIENT_ASSIGNMENT:
        if notice.target_client_id:
            # Get staff assigned to this client
            assignments = db.query(StaffAssignment).filter(
                StaffAssignment.client_id == notice.target_client_id,
                StaffAssignment.is_active == True
            ).all()

            # Get user IDs from staff records
            staff_ids = [a.staff_id for a in assignments]
            if staff_ids:
                staff_records = db.query(Staff).filter(Staff.id.in_(staff_ids)).all()
                return [str(s.user_id) for s in staff_records]
        return []

    elif target_type == NoticeTargetType.LOCATION:
        if notice.target_location_id:
            user_ids = set()

            # Get staff directly assigned to location
            direct_assignments = db.query(StaffAssignment).filter(
                StaffAssignment.location_id == notice.target_location_id,
                StaffAssignment.is_active == True
            ).all()

            for a in direct_assignments:
                staff = db.query(Staff).filter(Staff.id == a.staff_id).first()
                if staff:
                    user_ids.add(str(staff.user_id))

            # Get staff assigned to clients at location
            clients_at_location = db.query(Client.id).filter(
                Client.location_id == notice.target_location_id,
                Client.organization_id == org_id
            ).all()

            if clients_at_location:
                client_ids = [c[0] for c in clients_at_location]
                client_assignments = db.query(StaffAssignment).filter(
                    StaffAssignment.client_id.in_(client_ids),
                    StaffAssignment.is_active == True
                ).all()

                for a in client_assignments:
                    staff = db.query(Staff).filter(Staff.id == a.staff_id).first()
                    if staff:
                        user_ids.add(str(staff.user_id))

            return list(user_ids)

    return []


def _build_notice_response(notice: Notice, read_notice_ids: set, acknowledged_notice_ids: set, db: Session = None) -> NoticeResponse:
    """Helper to build NoticeResponse from Notice model"""
    # Get creator name if db is provided
    created_by_name = None
    if db and notice.created_by:
        creator = db.query(User).filter(User.id == notice.created_by).first()
        if creator:
            created_by_name = f"{creator.first_name} {creator.last_name}"

    return NoticeResponse(
        id=str(notice.id),
        organization_id=str(notice.organization_id),
        title=notice.title,
        content=notice.content,
        summary=notice.summary,
        priority=notice.priority,
        category=notice.category,
        target_type=notice.target_type,
        target_roles=notice.target_roles,
        target_users=notice.target_users,
        target_client_id=str(notice.target_client_id) if notice.target_client_id else None,
        target_location_id=str(notice.target_location_id) if notice.target_location_id else None,
        is_active=notice.is_active,
        publish_date=notice.publish_date,
        expire_date=notice.expire_date,
        requires_acknowledgment=notice.requires_acknowledgment,
        attachment_urls=notice.attachment_urls,
        created_at=notice.created_at,
        updated_at=notice.updated_at,
        created_by=str(notice.created_by),
        created_by_name=created_by_name,
        read=str(notice.id) in read_notice_ids,
        acknowledged=str(notice.id) in acknowledged_notice_ids
    )


# ============== List & Read Endpoints ==============

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
    """Get notices for current user (filtered by targeting rules)"""

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
        if _check_if_user_should_see_notice(notice, current_user, db)
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
            if str(notice.id) not in read_notice_ids
        ]

    # Count unread
    unread_count = sum(1 for notice in filtered_notices if str(notice.id) not in read_notice_ids)

    # Pagination
    total = len(filtered_notices)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_notices = filtered_notices[start:end]

    # Build response
    notices_response = [
        _build_notice_response(notice, read_notice_ids, acknowledged_notice_ids, db)
        for notice in paginated_notices
    ]

    return NoticesList(
        notices=notices_response,
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count
    )


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

    if not _check_if_user_should_see_notice(notice, current_user, db):
        raise HTTPException(status_code=403, detail="You don't have access to this notice")

    # Check if user has read this notice
    read_receipt = db.query(NoticeReadReceipt).filter(
        NoticeReadReceipt.notice_id == notice_id,
        NoticeReadReceipt.user_id == str(current_user.id)
    ).first()

    read_notice_ids = {str(notice_id)} if read_receipt else set()
    acknowledged_notice_ids = {str(notice_id)} if read_receipt and read_receipt.acknowledged_at else set()

    # Automatically mark as read if not already
    if not read_receipt:
        receipt = NoticeReadReceipt(
            notice_id=notice_id,
            user_id=str(current_user.id)
        )
        db.add(receipt)
        db.commit()
        read_notice_ids = {str(notice_id)}

    return _build_notice_response(notice, read_notice_ids, acknowledged_notice_ids, db)


# ============== Create, Update, Delete Endpoints (Manager+ Only) ==============

@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
def create_notice(
    notice_data: NoticeCreate,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Create a new notice (Managers and Admins only)"""

    # Validate targeting data
    if notice_data.target_type == NoticeTargetType.SPECIFIC_USERS:
        if not notice_data.target_users or len(notice_data.target_users) == 0:
            raise HTTPException(
                status_code=400,
                detail="target_users is required when target_type is 'specific_users'"
            )
    elif notice_data.target_type == NoticeTargetType.CLIENT_ASSIGNMENT:
        if not notice_data.target_client_id:
            raise HTTPException(
                status_code=400,
                detail="target_client_id is required when target_type is 'client_assignment'"
            )
        # Verify client exists in organization
        client = db.query(Client).filter(
            Client.id == notice_data.target_client_id,
            Client.organization_id == current_user.organization_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Target client not found")
    elif notice_data.target_type == NoticeTargetType.LOCATION:
        if not notice_data.target_location_id:
            raise HTTPException(
                status_code=400,
                detail="target_location_id is required when target_type is 'location'"
            )
        # Verify location exists in organization
        location = db.query(Location).filter(
            Location.id == notice_data.target_location_id,
            Location.organization_id == current_user.organization_id
        ).first()
        if not location:
            raise HTTPException(status_code=404, detail="Target location not found")

    # Create notice
    notice = Notice(
        organization_id=current_user.organization_id,
        title=notice_data.title,
        content=notice_data.content,
        summary=notice_data.summary,
        priority=notice_data.priority,
        category=notice_data.category,
        target_type=notice_data.target_type,
        target_roles=notice_data.target_roles,
        target_users=notice_data.target_users,
        target_client_id=notice_data.target_client_id,
        target_location_id=notice_data.target_location_id,
        is_active=True,
        publish_date=notice_data.publish_date,
        expire_date=notice_data.expire_date,
        requires_acknowledgment=notice_data.requires_acknowledgment,
        attachment_urls=notice_data.attachment_urls,
        created_by=current_user.id
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)

    return _build_notice_response(notice, set(), set(), db)


@router.put("/{notice_id}", response_model=NoticeResponse)
def update_notice(
    notice_id: str,
    notice_data: NoticeUpdate,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Update a notice (Managers and Admins only)"""

    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    # Update fields if provided
    update_data = notice_data.model_dump(exclude_unset=True)

    # Validate targeting if being changed
    if 'target_type' in update_data:
        target_type = update_data['target_type']
        if target_type == NoticeTargetType.SPECIFIC_USERS:
            target_users = update_data.get('target_users') or notice.target_users
            if not target_users or len(target_users) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="target_users is required when target_type is 'specific_users'"
                )
        elif target_type == NoticeTargetType.CLIENT_ASSIGNMENT:
            target_client_id = update_data.get('target_client_id') or notice.target_client_id
            if not target_client_id:
                raise HTTPException(
                    status_code=400,
                    detail="target_client_id is required when target_type is 'client_assignment'"
                )
        elif target_type == NoticeTargetType.LOCATION:
            target_location_id = update_data.get('target_location_id') or notice.target_location_id
            if not target_location_id:
                raise HTTPException(
                    status_code=400,
                    detail="target_location_id is required when target_type is 'location'"
                )

    for field, value in update_data.items():
        setattr(notice, field, value)

    db.commit()
    db.refresh(notice)

    return _build_notice_response(notice, set(), set(), db)


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(
    notice_id: str,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Delete (deactivate) a notice (Managers and Admins only)"""

    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    # Soft delete by setting is_active to False
    notice.is_active = False
    db.commit()

    return None


# ============== Mark Read / Acknowledge Endpoints ==============

@router.post("/{notice_id}/read", response_model=dict)
def mark_notice_as_read(
    notice_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notice as read"""

    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    if not _check_if_user_should_see_notice(notice, current_user, db):
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

    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    if not _check_if_user_should_see_notice(notice, current_user, db):
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


# ============== Statistics & Acknowledgment Tracking (Manager+ Only) ==============

@router.get("/{notice_id}/statistics", response_model=NoticeStatistics)
def get_notice_statistics(
    notice_id: str,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get notice statistics (Managers and Admins only)"""

    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    # Get targeted user IDs
    targeted_user_ids = _get_targeted_user_ids(notice, db)
    total_recipients = len(targeted_user_ids)

    # Get read receipts for this notice
    read_receipts = db.query(NoticeReadReceipt).filter(
        NoticeReadReceipt.notice_id == notice_id,
        NoticeReadReceipt.user_id.in_(targeted_user_ids) if targeted_user_ids else False
    ).all()

    read_count = len(read_receipts)
    acknowledged_count = sum(1 for r in read_receipts if r.acknowledged_at is not None)
    unread_count = total_recipients - read_count
    pending_acknowledgment_count = read_count - acknowledged_count if notice.requires_acknowledgment else 0

    read_percentage = (read_count / total_recipients * 100) if total_recipients > 0 else 0.0
    acknowledged_percentage = (acknowledged_count / total_recipients * 100) if total_recipients > 0 else 0.0

    return NoticeStatistics(
        notice_id=str(notice_id),
        total_recipients=total_recipients,
        read_count=read_count,
        acknowledged_count=acknowledged_count,
        unread_count=unread_count,
        pending_acknowledgment_count=pending_acknowledgment_count,
        read_percentage=round(read_percentage, 1),
        acknowledged_percentage=round(acknowledged_percentage, 1)
    )


@router.get("/{notice_id}/acknowledgments", response_model=List[NoticeAcknowledgmentDetail])
def get_notice_acknowledgments(
    notice_id: str,
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get detailed acknowledgment tracking (Managers and Admins only)"""

    notice = db.query(Notice).filter(
        Notice.id == notice_id,
        Notice.organization_id == current_user.organization_id
    ).first()

    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    # Get targeted user IDs
    targeted_user_ids = _get_targeted_user_ids(notice, db)

    # Get all targeted users with their read receipts
    acknowledgments = []

    for user_id in targeted_user_ids:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            continue

        receipt = db.query(NoticeReadReceipt).filter(
            NoticeReadReceipt.notice_id == notice_id,
            NoticeReadReceipt.user_id == user_id
        ).first()

        # Determine status
        if receipt and receipt.acknowledged_at:
            status = "acknowledged"
        elif receipt:
            status = "read"
        else:
            status = "pending"

        acknowledgments.append(NoticeAcknowledgmentDetail(
            user_id=str(user.id),
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            role_name=user.role.name if user.role else None,
            read_at=receipt.read_at if receipt else None,
            acknowledged_at=receipt.acknowledged_at if receipt else None,
            status=status
        ))

    # Sort by status (pending first, then read, then acknowledged)
    status_order = {"pending": 0, "read": 1, "acknowledged": 2}
    acknowledgments.sort(key=lambda x: status_order.get(x.status, 3))

    return acknowledgments


# ============== Targeting Helper Endpoints (Manager+ Only) ==============

@router.get("/targeting/users", response_model=List[TargetableUser])
def get_targetable_users(
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get list of users that can be targeted (excluding clients)"""

    query = db.query(User).filter(
        User.organization_id == current_user.organization_id,
        User.status == UserStatus.ACTIVE
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.first_name.ilike(search_term)) |
            (User.last_name.ilike(search_term)) |
            (User.email.ilike(search_term))
        )

    users = query.all()

    # Filter out clients
    return [
        TargetableUser(
            id=str(u.id),
            name=f"{u.first_name} {u.last_name}",
            email=u.email,
            role_name=u.role.name if u.role else None
        )
        for u in users
        if not (u.role and u.role.name.lower() == "client")
    ]


@router.get("/targeting/clients", response_model=List[TargetableClient])
def get_targetable_clients(
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get list of clients for targeting staff assignments"""

    query = db.query(Client).filter(
        Client.organization_id == current_user.organization_id,
        Client.status == "active"
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Client.first_name.ilike(search_term)) |
            (Client.last_name.ilike(search_term)) |
            (Client.client_id.ilike(search_term))
        )

    clients = query.all()

    return [
        TargetableClient(
            id=str(c.id),
            name=f"{c.first_name} {c.last_name}",
            client_id=c.client_id
        )
        for c in clients
    ]


@router.get("/activity/recent", response_model=List[dict])
def get_recent_notice_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get recent notice activity (reads, acknowledgments, creations)"""
    from sqlalchemy import desc, union_all, literal

    activities = []

    # Get recently created notices
    recent_notices = db.query(Notice).filter(
        Notice.organization_id == current_user.organization_id,
        Notice.is_active == True
    ).order_by(desc(Notice.created_at)).limit(5).all()

    for notice in recent_notices:
        creator = db.query(User).filter(User.id == notice.created_by).first()
        creator_name = f"{creator.first_name} {creator.last_name}" if creator else "Unknown"

        activities.append({
            "type": "created",
            "notice_id": str(notice.id),
            "notice_title": notice.title,
            "user_name": creator_name,
            "priority": notice.priority.value if notice.priority else "medium",
            "timestamp": notice.created_at.isoformat(),
            "message": f"created notice"
        })

    # Get recent read receipts
    recent_reads = db.query(NoticeReadReceipt).join(
        Notice, Notice.id == NoticeReadReceipt.notice_id
    ).filter(
        Notice.organization_id == current_user.organization_id,
        NoticeReadReceipt.acknowledged_at.isnot(None)
    ).order_by(desc(NoticeReadReceipt.acknowledged_at)).limit(5).all()

    for receipt in recent_reads:
        notice = db.query(Notice).filter(Notice.id == receipt.notice_id).first()
        user = db.query(User).filter(User.id == receipt.user_id).first()

        if notice and user:
            activities.append({
                "type": "acknowledged",
                "notice_id": str(notice.id),
                "notice_title": notice.title,
                "user_name": f"{user.first_name} {user.last_name}",
                "priority": notice.priority.value if notice.priority else "medium",
                "timestamp": receipt.acknowledged_at.isoformat() if receipt.acknowledged_at else receipt.read_at.isoformat(),
                "message": f"acknowledged notice"
            })

    # Sort all activities by timestamp descending
    activities.sort(key=lambda x: x["timestamp"], reverse=True)

    return activities[:limit]


@router.get("/targeting/locations", response_model=List[TargetableLocation])
def get_targetable_locations(
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_manager_or_above),
    db: Session = Depends(get_db)
):
    """Get list of locations for targeting"""

    query = db.query(Location).filter(
        Location.organization_id == current_user.organization_id,
        Location.is_active == True
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Location.name.ilike(search_term)) |
            (Location.address.ilike(search_term))
        )

    locations = query.all()

    return [
        TargetableLocation(
            id=str(loc.id),
            name=loc.name,
            address=loc.full_address
        )
        for loc in locations
    ]
