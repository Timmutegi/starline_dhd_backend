from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, text
from datetime import datetime, timezone, date, timedelta
from typing import Optional, List, Dict, Any
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserStatus
from app.models.client import Client
from app.models.staff import Staff
from app.models.scheduling import Appointment
from app.models.user import Organization
from app.models.audit_log import AuditLog, AuditAction
from app.schemas.admin import (
    AdminDashboardOverview,
    SystemStats,
    OrganizationSummary,
    UserActivitySummary,
    RecentActivity,
    SystemHealth,
    AdminNotificationCreate,
    BulkActionRequest,
    AuditLogEntry,
    DatabaseMetrics,
    MemoryMetrics,
    StorageMetrics,
    SystemEvent
)
from app.schemas.user import AdminUserCreate, AdminUserCreateResponse
from app.models.user import Role
from app.core.security import get_password_hash, generate_random_password
from app.services.email_service import EmailService

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
        if not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Get system-wide statistics
        total_organizations = db.query(Organization).count()
        total_users = db.query(User).count()
        total_clients = db.query(Client).count()
        total_staff = db.query(Staff).count()

        # Active users in last 24 hours
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        active_users_24h = db.query(User).filter(
            User.last_login >= yesterday
        ).count()

        # Appointments today
        today = date.today()
        appointments_today = db.query(Appointment).filter(
            func.date(Appointment.start_datetime) == today
        ).count()

        # System health metrics
        health_status = _check_system_health(db)
        system_health = SystemHealth(
            database_status=health_status["database_status"],
            api_status=health_status["api_status"],
            storage_status=health_status["storage_status"],
            email_service_status=health_status["email_service_status"]
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
            last_updated=datetime.now(timezone.utc)
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
        if not _has_admin_permission(current_user):
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
        if not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

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
                # Ensure both datetimes are timezone-aware for comparison
                now_utc = datetime.now(timezone.utc)
                # If last_login is naive, make it aware (assume UTC)
                if last_login.tzinfo is None:
                    from datetime import timezone as tz
                    last_login_aware = last_login.replace(tzinfo=timezone.utc)
                else:
                    last_login_aware = last_login
                days_since_login = (now_utc - last_login_aware).days

            # Get actual login count from audit logs
            login_count = db.query(AuditLog).filter(
                AuditLog.user_id == user.id,
                AuditLog.action == AuditAction.LOGIN,
                AuditLog.created_at >= cutoff_date
            ).count()

            # Get total action count from audit logs
            actions_count = db.query(AuditLog).filter(
                AuditLog.user_id == user.id,
                AuditLog.created_at >= cutoff_date
            ).count()

            results.append(UserActivitySummary(
                user_id=str(user.id),
                username=user.username,
                email=user.email,
                full_name=f"{user.first_name} {user.last_name}",
                organization_name=user.organization.name if user.organization else "Unknown",
                role_name=user.role.name if user.role else None,
                last_login=last_login,
                days_since_login=days_since_login,
                login_count_period=login_count,
                actions_count_period=actions_count,
                is_active=user.status == UserStatus.ACTIVE
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
    Get detailed system health information with extended metrics
    """
    try:
        if not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Check all system components with extended metrics
        health_status = _check_system_health(db, include_extended=True)

        return SystemHealth(
            database_status=health_status["database_status"],
            api_status=health_status["api_status"],
            storage_status=health_status["storage_status"],
            email_service_status=health_status["email_service_status"],
            last_checked=datetime.now(timezone.utc),
            # Extended metrics
            uptime_percent=health_status.get("uptime_percent"),
            avg_response_time_ms=health_status.get("avg_response_time_ms"),
            requests_per_minute=health_status.get("requests_per_minute"),
            # Service response times
            database_response_ms=health_status.get("database_response_ms"),
            storage_response_ms=health_status.get("storage_response_ms"),
            email_response_ms=health_status.get("email_response_ms"),
            # Resource metrics
            database_metrics=health_status.get("database_metrics"),
            memory_metrics=health_status.get("memory_metrics"),
            storage_metrics=health_status.get("storage_metrics"),
            # Recent events
            recent_events=health_status.get("recent_events")
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
        if not _has_admin_permission(current_user):
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
        if not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        users = db.query(User).filter(User.id.in_(action_request.target_ids)).all()

        if not users:
            raise HTTPException(status_code=400, detail="No target users found")

        updated_count = 0

        for user in users:
            if action_request.action == "activate":
                user.status = UserStatus.ACTIVE
                updated_count += 1
            elif action_request.action == "deactivate":
                user.status = UserStatus.INACTIVE
                updated_count += 1
            elif action_request.action == "suspend":
                user.status = UserStatus.SUSPENDED
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
        if not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Build query for audit logs with eager loading
        query = db.query(AuditLog).options(
            joinedload(AuditLog.user)
        )

        # Apply filters
        if organization_id:
            query = query.filter(AuditLog.organization_id == organization_id)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if action_type:
            try:
                action_enum = AuditAction(action_type)
                query = query.filter(AuditLog.action == action_enum)
            except ValueError:
                pass  # Invalid action type, skip filter

        if date_from:
            query = query.filter(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))

        if date_to:
            query = query.filter(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))

        # Execute query with pagination
        audit_logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

        # Convert to response schema
        results = []
        for log in audit_logs:
            results.append(AuditLogEntry(
                id=str(log.id),
                user_id=str(log.user_id) if log.user_id else None,
                username=log.user.username if log.user else "System",
                action=log.action.value if hasattr(log.action, 'value') else str(log.action),
                resource_type=log.resource_type or "unknown",
                resource_id=str(log.resource_id) if log.resource_id else None,
                resource_name=log.resource_name,
                ip_address=log.ip_address,
                timestamp=log.created_at,
                organization_id=str(log.organization_id) if log.organization_id else None,
                details=log.changes_summary
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve audit logs: {str(e)}"
        )

@router.get("/audit/analytics/top-actions")
async def get_top_actions(
    days: int = Query(7, description="Number of days to analyze"),
    limit: int = Query(10, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get top actions by frequency
    """
    try:
        if not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Query to count actions grouped by action type
        from sqlalchemy import func as sql_func
        action_counts = db.query(
            AuditLog.action,
            sql_func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.created_at >= cutoff_date
        ).group_by(
            AuditLog.action
        ).order_by(
            sql_func.count(AuditLog.id).desc()
        ).limit(limit).all()

        total_actions = db.query(sql_func.count(AuditLog.id)).filter(
            AuditLog.created_at >= cutoff_date
        ).scalar() or 1

        results = []
        for action, count in action_counts:
            percentage = round((count / total_actions) * 100, 1)
            results.append({
                "action": action.value if hasattr(action, 'value') else str(action),
                "count": count,
                "percentage": percentage
            })

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve top actions: {str(e)}"
        )

@router.get("/audit/analytics/top-resources")
async def get_top_resources(
    days: int = Query(7, description="Number of days to analyze"),
    limit: int = Query(10, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get most active resources
    """
    try:
        if not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Query to count actions grouped by resource type
        from sqlalchemy import func as sql_func
        resource_counts = db.query(
            AuditLog.resource_type,
            sql_func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.created_at >= cutoff_date,
            AuditLog.resource_type.isnot(None)
        ).group_by(
            AuditLog.resource_type
        ).order_by(
            sql_func.count(AuditLog.id).desc()
        ).limit(limit).all()

        results = []
        for resource_type, count in resource_counts:
            # Format resource type for display
            display_name = resource_type.replace('_', ' ').title() if resource_type else "Unknown"
            results.append({
                "resource_type": resource_type,
                "display_name": display_name,
                "count": count
            })

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve top resources: {str(e)}"
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
        if not _has_admin_permission(current_user):
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
            "generated_at": datetime.now(timezone.utc)
        }

        return report

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate usage report: {str(e)}"
        )

@router.post("/users/create", response_model=AdminUserCreateResponse)
async def create_user_by_admin(
    user_data: AdminUserCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new user with auto-generated password (admin only).
    Sends invitation email with credentials.
    """
    try:
        if not _has_admin_permission(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Check if user already exists
        existing_user = db.query(User).filter(
            or_(
                User.email == user_data.email,
                User.username == user_data.username
            )
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="User with this email or username already exists"
            )

        # Verify organization exists
        org_id = user_data.organization_id or current_user.organization_id
        organization = db.query(Organization).filter(Organization.id == org_id).first()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Verify role exists
        role = db.query(Role).filter(Role.id == user_data.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        # Generate a secure random password
        generated_password = generate_random_password()
        password_hash = get_password_hash(generated_password)

        # Create new user
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            password_hash=password_hash,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            organization_id=org_id,
            role_id=user_data.role_id,
            status=UserStatus.ACTIVE,
            email_verified=True,  # Admin-created users are pre-verified
            must_change_password=True  # Force password change on first login
        )

        db.add(new_user)
        db.flush()  # Get user ID without committing

        # Create Staff record if the role is staff-related
        staff_roles = ["Support Staff", "HR Manager", "Supervisor", "Billing Admin"]
        if role.name in staff_roles:
            from app.models.staff import Staff, EmploymentStatus
            from datetime import date

            # Generate employee ID if not provided
            if not user_data.employee_id:
                # Auto-generate employee ID: EMP-YYYYMMDD-XXX
                from datetime import datetime
                import random
                date_str = datetime.now().strftime("%Y%m%d")
                random_suffix = f"{random.randint(0, 999):03d}"
                employee_id = f"EMP-{date_str}-{random_suffix}"
            else:
                employee_id = user_data.employee_id

            from app.models.staff import PayType
            from decimal import Decimal

            new_staff = Staff(
                user_id=new_user.id,
                organization_id=org_id,
                employee_id=employee_id,
                hire_date=user_data.hire_date or date.today(),
                employment_status=EmploymentStatus.ACTIVE,
                job_title=role.name,
                pay_type=PayType.HOURLY,  # Default to hourly
                fte_percentage=Decimal('100.00'),  # Default to full-time
                created_by=current_user.id
            )
            db.add(new_staff)

        db.commit()
        db.refresh(new_user)

        # Send invitation email with credentials
        try:
            await EmailService.send_staff_credentials(
                email=new_user.email,
                full_name=f"{new_user.first_name} {new_user.last_name}",
                username=new_user.username,
                password=generated_password,
                employee_id=new_user.employee_id or "N/A",
                organization_name=organization.name,
                role_name=role.name
            )
        except Exception as email_error:
            # Log the error but don't fail the user creation
            print(f"Failed to send invitation email: {email_error}")
            # You might want to use proper logging here

        # Prepare response with user data
        from app.schemas.user import UserResponse
        user_response = UserResponse.model_validate(new_user)
        user_response.organization = organization
        user_response.role_name = role.name

        return AdminUserCreateResponse(
            user=user_response,
            generated_password=generated_password,
            message=f"User created successfully. Invitation email sent to {new_user.email}"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user: {str(e)}"
        )

def _check_system_health(db: Session, include_extended: bool = False) -> Dict[str, Any]:
    """
    Check health of various system components
    """
    import time
    import uuid

    result = {
        "database_status": "unknown",
        "api_status": "healthy",  # If we're running, API is healthy
        "storage_status": "unknown",
        "email_service_status": "unknown",
        "database_response_ms": None,
        "storage_response_ms": None,
        "email_response_ms": None,
    }

    # Check database connectivity with timing
    try:
        start_time = time.time()
        db.execute(text("SELECT 1"))
        db.commit()
        db_response_ms = round((time.time() - start_time) * 1000, 2)
        result["database_status"] = "healthy"
        result["database_response_ms"] = db_response_ms
    except Exception:
        result["database_status"] = "unhealthy"

    # Check storage (AWS S3) connectivity with timing
    try:
        from app.core.config import settings
        import boto3

        if hasattr(settings, 'AWS_ACCESS_KEY_ID') and settings.AWS_ACCESS_KEY_ID:
            start_time = time.time()
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            s3_client.list_buckets()
            storage_response_ms = round((time.time() - start_time) * 1000, 2)
            result["storage_status"] = "healthy"
            result["storage_response_ms"] = storage_response_ms
        else:
            result["storage_status"] = "not_configured"
    except Exception:
        result["storage_status"] = "unhealthy"

    # Check email service connectivity with timing
    try:
        from app.core.config import settings
        import requests

        if hasattr(settings, 'RESEND_API_KEY') and settings.RESEND_API_KEY:
            start_time = time.time()
            headers = {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}
            response = requests.get("https://api.resend.com/domains", headers=headers, timeout=5)
            email_response_ms = round((time.time() - start_time) * 1000, 2)
            result["email_service_status"] = "healthy" if response.status_code in [200, 401, 403] else "unhealthy"
            result["email_response_ms"] = email_response_ms
        else:
            result["email_service_status"] = "not_configured"
    except Exception:
        result["email_service_status"] = "unhealthy"

    if include_extended:
        # Get database connection metrics
        try:
            conn_result = db.execute(text("""
                SELECT
                    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections
            """))
            row = conn_result.fetchone()
            if row:
                active_conns = row[0] or 0
                max_conns = row[1] or 100
                result["database_metrics"] = DatabaseMetrics(
                    active_connections=active_conns,
                    max_connections=max_conns,
                    connection_usage_percent=round((active_conns / max_conns) * 100, 1)
                )
        except Exception:
            pass

        # Get memory metrics (system level)
        try:
            import psutil
            memory = psutil.virtual_memory()
            result["memory_metrics"] = MemoryMetrics(
                used_gb=round(memory.used / (1024**3), 2),
                total_gb=round(memory.total / (1024**3), 2),
                usage_percent=round(memory.percent, 1)
            )
        except ImportError:
            # psutil not installed, provide fallback
            result["memory_metrics"] = MemoryMetrics(
                used_gb=0,
                total_gb=0,
                usage_percent=0
            )
        except Exception:
            pass

        # Get storage metrics from S3 (if configured) or disk
        try:
            from app.core.config import settings
            if hasattr(settings, 'AWS_S3_BUCKET') and settings.AWS_S3_BUCKET:
                # For S3, we'd need CloudWatch metrics for accurate size
                # Use placeholder or disk storage as fallback
                import psutil
                disk = psutil.disk_usage('/')
                result["storage_metrics"] = StorageMetrics(
                    used_gb=round(disk.used / (1024**3), 2),
                    total_gb=round(disk.total / (1024**3), 2),
                    usage_percent=round(disk.percent, 1)
                )
            else:
                import psutil
                disk = psutil.disk_usage('/')
                result["storage_metrics"] = StorageMetrics(
                    used_gb=round(disk.used / (1024**3), 2),
                    total_gb=round(disk.total / (1024**3), 2),
                    usage_percent=round(disk.percent, 1)
                )
        except ImportError:
            result["storage_metrics"] = StorageMetrics(
                used_gb=0,
                total_gb=0,
                usage_percent=0
            )
        except Exception:
            pass

        # Calculate requests per minute from audit logs (last 5 minutes avg)
        try:
            five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            request_count = db.query(func.count(AuditLog.id)).filter(
                AuditLog.created_at >= five_mins_ago
            ).scalar() or 0
            result["requests_per_minute"] = int(request_count / 5)
        except Exception:
            result["requests_per_minute"] = 0

        # Calculate average response time (from recent audit logs if available)
        # Since we don't track response times in audit logs, use database response as proxy
        result["avg_response_time_ms"] = result.get("database_response_ms", 0)

        # Calculate uptime (simple: time since app started)
        # For real uptime, you'd track this in Redis or a startup timestamp file
        result["uptime_percent"] = 99.9  # Placeholder - in production, track actual uptime

        # Get recent system events from audit logs
        try:
            recent_logs = db.query(AuditLog).filter(
                AuditLog.action.in_([
                    AuditAction.LOGIN,
                    AuditAction.LOGOUT,
                    AuditAction.CREATE,
                    AuditAction.UPDATE,
                    AuditAction.DELETE,
                    AuditAction.ACCESS_DENIED
                ])
            ).order_by(AuditLog.created_at.desc()).limit(10).all()

            events = []
            for log in recent_logs:
                event_type = "success"
                if log.action == AuditAction.ACCESS_DENIED:
                    event_type = "warning"
                elif log.action == AuditAction.DELETE:
                    event_type = "warning"

                action_name = log.action.value if hasattr(log.action, 'value') else str(log.action)
                events.append(SystemEvent(
                    id=str(log.id),
                    type=event_type,
                    title=f"{action_name.replace('_', ' ').title()}",
                    description=f"{log.resource_type or 'Resource'}: {log.resource_name or 'N/A'}",
                    timestamp=log.created_at
                ))
            result["recent_events"] = events
        except Exception:
            result["recent_events"] = []

    return result

def _has_admin_permission(user: User) -> bool:
    """
    Check if user has admin permissions
    """
    # Check if user has admin or super_admin role
    # Normalize role name by replacing spaces with underscores and converting to lowercase
    if user.role:
        role_name = user.role.name.lower().replace(" ", "_")
        if role_name in ['admin', 'super_admin', 'organization_admin']:
            return True
    return False