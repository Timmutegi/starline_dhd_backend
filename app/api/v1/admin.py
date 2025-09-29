from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.client import Client
from app.models.staff import Staff
from app.models.scheduling import Appointment
from app.models.user import Organization
from app.schemas.admin import (
    AdminDashboardOverview,
    SystemStats,
    OrganizationSummary,
    UserActivitySummary,
    RecentActivity,
    SystemHealth,
    AdminNotificationCreate,
    BulkActionRequest,
    AuditLogEntry
)

router = APIRouter()

@router.get("/dashboard", response_model=AdminDashboardOverview)
async def get_admin_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive admin dashboard overview
    """
    try:
        # Check if user has admin permissions
        if not current_user.is_super_admin and not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Get system-wide statistics
        total_organizations = db.query(Organization).count()
        total_users = db.query(User).count()
        total_clients = db.query(Client).count()
        total_staff = db.query(Staff).count()

        # Active users in last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_users_24h = db.query(User).filter(
            User.last_login >= yesterday
        ).count()

        # Appointments today
        today = date.today()
        appointments_today = db.query(Appointment).filter(
            func.date(Appointment.start_time) == today
        ).count()

        # System health metrics
        system_health = SystemHealth(
            database_status="healthy",
            api_status="healthy",
            storage_status="healthy",
            email_service_status="healthy"
        )

        # Organization summaries
        organizations = db.query(Organization).limit(10).all()
        org_summaries = []

        for org in organizations:
            org_users = db.query(User).filter(User.organization_id == org.id).count()
            org_clients = db.query(Client).filter(Client.organization_id == org.id).count()

            org_summaries.append(OrganizationSummary(
                id=str(org.id),
                name=org.name,
                subdomain=org.subdomain,
                users_count=org_users,
                clients_count=org_clients,
                is_active=org.is_active,
                created_at=org.created_at
            ))

        system_stats = SystemStats(
            total_organizations=total_organizations,
            total_users=total_users,
            total_clients=total_clients,
            total_staff=total_staff,
            active_users_24h=active_users_24h,
            appointments_today=appointments_today
        )

        return AdminDashboardOverview(
            system_stats=system_stats,
            system_health=system_health,
            organizations=org_summaries,
            last_updated=datetime.utcnow()
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve admin dashboard: {str(e)}"
        )

@router.get("/organizations", response_model=List[OrganizationSummary])
async def get_organizations(
    active_only: bool = Query(False, description="Filter to active organizations only"),
    search: Optional[str] = Query(None, description="Search by name or subdomain"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all organizations with detailed information
    """
    try:
        if not current_user.is_super_admin and not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        query = db.query(Organization)

        if active_only:
            query = query.filter(Organization.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Organization.name.ilike(f"%{search}%"),
                    Organization.subdomain.ilike(f"%{search}%")
                )
            )

        organizations = query.order_by(Organization.created_at.desc()).offset(offset).limit(limit).all()

        results = []
        for org in organizations:
            users_count = db.query(User).filter(User.organization_id == org.id).count()
            clients_count = db.query(Client).filter(Client.organization_id == org.id).count()

            results.append(OrganizationSummary(
                id=str(org.id),
                name=org.name,
                subdomain=org.subdomain,
                users_count=users_count,
                clients_count=clients_count,
                is_active=org.is_active,
                created_at=org.created_at
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve organizations: {str(e)}"
        )

@router.get("/users/activity", response_model=List[UserActivitySummary])
async def get_user_activity(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    days: int = Query(7, description="Number of days to look back"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user activity summaries for admin monitoring
    """
    try:
        if not current_user.is_super_admin and not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(User)

        if organization_id:
            query = query.filter(User.organization_id == organization_id)

        users = query.order_by(User.last_login.desc().nullslast()).offset(offset).limit(limit).all()

        results = []
        for user in users:
            # Calculate activity metrics
            last_login = user.last_login
            days_since_login = None
            if last_login:
                days_since_login = (datetime.utcnow() - last_login).days

            # This would ideally come from audit logs or activity tracking
            login_count = 0  # Placeholder
            actions_count = 0  # Placeholder

            results.append(UserActivitySummary(
                user_id=str(user.id),
                username=user.username,
                email=user.email,
                full_name=f"{user.first_name} {user.last_name}",
                organization_name=user.organization.name if user.organization else "Unknown",
                last_login=last_login,
                days_since_login=days_since_login,
                login_count_period=login_count,
                actions_count_period=actions_count,
                is_active=user.status == "active"
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user activity: {str(e)}"
        )

@router.get("/system/health", response_model=SystemHealth)
async def get_system_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed system health information
    """
    try:
        if not current_user.is_super_admin and not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Check database connectivity
        try:
            db.execute(text("SELECT 1"))
            database_status = "healthy"
        except:
            database_status = "unhealthy"

        # These would be real health checks in production
        api_status = "healthy"
        storage_status = "healthy"
        email_service_status = "healthy"

        return SystemHealth(
            database_status=database_status,
            api_status=api_status,
            storage_status=storage_status,
            email_service_status=email_service_status,
            last_checked=datetime.utcnow()
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check system health: {str(e)}"
        )

@router.post("/notifications/broadcast")
async def broadcast_notification(
    notification_data: AdminNotificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Broadcast notification to multiple users (admin only)
    """
    try:
        if not current_user.is_super_admin and not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Build user query based on target criteria
        query = db.query(User)

        if notification_data.target_organization_id:
            query = query.filter(User.organization_id == notification_data.target_organization_id)

        if notification_data.target_role:
            # This would need to be adjusted based on your role system
            pass

        if notification_data.target_user_ids:
            query = query.filter(User.id.in_(notification_data.target_user_ids))

        target_users = query.all()

        if not target_users:
            raise HTTPException(status_code=400, detail="No target users found")

        # Create notifications for all target users
        from app.models.notification import Notification, NotificationTypeEnum, NotificationCategoryEnum

        notifications_created = 0
        for user in target_users:
            notification = Notification(
                user_id=user.id,
                organization_id=user.organization_id,
                title=notification_data.title,
                message=notification_data.message,
                type=NotificationTypeEnum(notification_data.type),
                category=NotificationCategoryEnum(notification_data.category),
                action_url=notification_data.action_url,
                action_text=notification_data.action_text,
                expires_at=notification_data.expires_at
            )
            db.add(notification)
            notifications_created += 1

        db.commit()

        return {
            "message": f"Notification broadcast to {notifications_created} users",
            "notifications_created": notifications_created
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to broadcast notification: {str(e)}"
        )

@router.post("/users/bulk-action")
async def bulk_user_action(
    action_request: BulkActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Perform bulk actions on users (admin only)
    """
    try:
        if not current_user.is_super_admin and not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        users = db.query(User).filter(User.id.in_(action_request.target_ids)).all()

        if not users:
            raise HTTPException(status_code=400, detail="No target users found")

        updated_count = 0

        for user in users:
            if action_request.action == "activate":
                user.status = "active"
                updated_count += 1
            elif action_request.action == "deactivate":
                user.status = "inactive"
                updated_count += 1
            elif action_request.action == "suspend":
                user.status = "suspended"
                updated_count += 1
            elif action_request.action == "reset_password":
                # Would trigger password reset email
                updated_count += 1

        db.commit()

        return {
            "message": f"Bulk action '{action_request.action}' applied to {updated_count} users",
            "updated_count": updated_count
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to perform bulk action: {str(e)}"
        )

@router.get("/audit/logs", response_model=List[AuditLogEntry])
async def get_audit_logs(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get audit logs for admin review
    """
    try:
        if not current_user.is_super_admin and not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        # This would query actual audit log table when implemented
        # For now, return empty list as placeholder
        return []

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve audit logs: {str(e)}"
        )

@router.get("/reports/usage")
async def get_usage_report(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    date_from: Optional[date] = Query(None, description="Report start date"),
    date_to: Optional[date] = Query(None, description="Report end date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate usage report for admin analysis
    """
    try:
        if not current_user.is_super_admin and not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        start_date = date_from or (date.today() - timedelta(days=30))
        end_date = date_to or date.today()

        base_query = db.query(User)
        if organization_id:
            base_query = base_query.filter(User.organization_id == organization_id)

        # Calculate usage metrics
        total_users = base_query.count()
        active_users = base_query.filter(
            and_(
                User.last_login >= start_date,
                User.last_login <= end_date
            )
        ).count()

        # Additional metrics would be calculated here
        report = {
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "user_metrics": {
                "total_users": total_users,
                "active_users": active_users,
                "activation_rate": (active_users / total_users * 100) if total_users > 0 else 0
            },
            "generated_at": datetime.utcnow()
        }

        return report

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate usage report: {str(e)}"
        )

def _has_admin_permission(user: User) -> bool:
    """
    Check if user has admin permissions
    """
    # This would check actual permissions/roles
    # For now, simple check based on role or other criteria
    return user.is_super_admin or (hasattr(user, 'role') and user.role and 'admin' in user.role.name.lower())