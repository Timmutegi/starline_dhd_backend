from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models.user import User, Organization, Role, Permission, UserStatus
from app.models.location import Location  # Import location model BEFORE client model
from app.models.staff import Staff  # Import staff models to ensure tables are created
from app.models.special_requirement import SpecialRequirement, SpecialRequirementResponse  # Import BEFORE client due to relationship
from app.models.client import Client  # Import client models to ensure tables are created
from app.models.scheduling import *  # Import scheduling models to ensure tables are created
from app.models.audit_log import AuditLog, AuditSetting, AuditExport, ComplianceViolation  # Import audit models
from app.models.vitals_log import VitalsLog  # Import vitals log model
from app.models.incident_report import IncidentReport  # Import incident report model
from app.models.notification import Notification  # Import notification model
from app.models.shift_note import ShiftNote  # Import shift note model
from app.models.task import Task  # Import task model
from app.models.bowel_movement_log import BowelMovementLog  # Import bowel movement log model
from app.models.sleep_log import SleepLog  # Import sleep log model
from app.core.config import settings
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        default_org = db.query(Organization).filter(
            Organization.subdomain == "starline"
        ).first()

        if not default_org:
            default_org = Organization(
                name="Starline Organization",
                subdomain="starline",
                contact_email=settings.DEFAULT_ADMIN_EMAIL,
                timezone="UTC",
                is_active=True
            )
            db.add(default_org)
            db.commit()
            db.refresh(default_org)
            logger.info("Default organization created")

        permissions_data = [
            ("users", "create", "Create new users"),
            ("users", "read", "View users"),
            ("users", "update", "Update users"),
            ("users", "delete", "Delete users"),
            ("roles", "create", "Create new roles"),
            ("roles", "read", "View roles"),
            ("roles", "update", "Update roles"),
            ("roles", "delete", "Delete roles"),
            ("organizations", "create", "Create organizations"),
            ("organizations", "read", "View organizations"),
            ("organizations", "update", "Update organizations"),
            ("organizations", "delete", "Delete organizations"),
            ("clients", "create", "Create clients"),
            ("clients", "read", "View clients"),
            ("clients", "update", "Update clients"),
            ("clients", "delete", "Delete clients"),
            ("staff", "create", "Create staff members"),
            ("staff", "read", "View staff information"),
            ("staff", "update", "Update staff information"),
            ("staff", "delete", "Remove staff members"),
            ("staff", "terminate", "Terminate staff employment"),
            ("staff", "manage_training", "Manage staff training records"),
            ("staff", "manage_certifications", "Manage staff certifications"),
            ("staff", "manage_performance", "Manage staff performance reviews"),
            ("staff", "view_payroll", "View staff payroll information"),
            ("staff", "manage_assignments", "Manage staff assignments"),
            ("documentation", "create", "Create documentation"),
            ("documentation", "read", "View documentation"),
            ("documentation", "update", "Update documentation"),
            ("documentation", "delete", "Delete documentation"),
            ("reports", "create", "Generate reports"),
            ("reports", "read", "View reports"),
            ("reports", "export", "Export reports"),
            ("billing", "create", "Create billing records"),
            ("billing", "read", "View billing"),
            ("billing", "update", "Update billing"),
            ("billing", "process", "Process payments"),
            # Scheduling & Calendar permissions
            ("scheduling", "create", "Create schedules and shifts"),
            ("scheduling", "read", "View schedules and shifts"),
            ("scheduling", "update", "Update schedules and shifts"),
            ("scheduling", "delete", "Delete schedules and shifts"),
            ("appointments", "create", "Create appointments"),
            ("appointments", "read", "View appointments"),
            ("appointments", "update", "Update appointments"),
            ("appointments", "delete", "Delete appointments"),
            ("time_clock", "create", "Clock in/out and time tracking"),
            ("time_clock", "read", "View time entries"),
            ("time_clock", "update", "Adjust time entries"),
            ("calendar", "create", "Create calendar events"),
            ("calendar", "read", "View calendar events"),
            ("calendar", "update", "Update calendar events"),
            ("calendar", "delete", "Delete calendar events"),
            # Audit & Compliance permissions
            ("audit", "read", "View audit logs"),
            ("audit", "export", "Export audit logs"),
            ("audit", "manage_settings", "Manage audit settings"),
            ("compliance", "read", "View compliance reports"),
            ("compliance", "manage_violations", "Manage compliance violations"),
            ("compliance", "generate_reports", "Generate compliance reports"),
            # Notifications permissions
            ("notifications", "read", "View notifications"),
        ]

        permissions = {}
        for resource, action, description in permissions_data:
            perm = db.query(Permission).filter(
                Permission.resource == resource,
                Permission.action == action
            ).first()
            if not perm:
                perm = Permission(
                    resource=resource,
                    action=action,
                    description=description
                )
                db.add(perm)
                db.commit()
                db.refresh(perm)
            permissions[f"{resource}:{action}"] = perm

        logger.info(f"Created/verified {len(permissions)} permissions")

        roles_data = [
            ("Super Admin", "Full system access", True, list(permissions.values())),
            ("Organization Admin", "Manage organization, users, and staff", False, [
                permissions["users:create"], permissions["users:read"],
                permissions["users:update"], permissions["users:delete"],
                permissions["roles:read"], permissions["organizations:read"],
                permissions["organizations:update"], permissions["staff:create"],
                permissions["staff:read"], permissions["staff:update"],
                permissions["staff:delete"], permissions["staff:terminate"],
                permissions["staff:manage_training"], permissions["staff:manage_certifications"],
                permissions["staff:manage_performance"], permissions["staff:view_payroll"],
                permissions["staff:manage_assignments"], permissions["audit:read"],
                permissions["audit:export"], permissions["audit:manage_settings"],
                permissions["compliance:read"], permissions["compliance:manage_violations"],
                permissions["compliance:generate_reports"]
            ]),
            ("HR Manager", "Comprehensive staff management", False, [
                permissions["staff:create"], permissions["staff:read"],
                permissions["staff:update"], permissions["staff:terminate"],
                permissions["staff:manage_training"], permissions["staff:manage_certifications"],
                permissions["staff:manage_performance"], permissions["staff:view_payroll"],
                permissions["staff:manage_assignments"], permissions["users:read"],
                permissions["users:update"], permissions["reports:read"],
                permissions["clients:read"], permissions["clients:update"],
                permissions["appointments:read"], permissions["appointments:create"],
                permissions["appointments:update"], permissions["appointments:delete"],
                permissions["scheduling:read"], permissions["scheduling:create"],
                permissions["scheduling:update"], permissions["scheduling:delete"],
                permissions["calendar:read"], permissions["calendar:create"],
                permissions["calendar:update"], permissions["calendar:delete"],
                permissions["documentation:read"], permissions["notifications:read"]
            ]),
            ("Supervisor", "Staff oversight and performance management", False, [
                permissions["staff:read"], permissions["staff:update"],
                permissions["staff:manage_training"], permissions["staff:manage_performance"],
                permissions["staff:manage_assignments"], permissions["clients:read"],
                permissions["clients:update"], permissions["documentation:read"],
                permissions["documentation:create"], permissions["documentation:update"],
                permissions["reports:read"], permissions["appointments:read"],
                permissions["appointments:create"], permissions["appointments:update"],
                permissions["appointments:delete"], permissions["scheduling:read"],
                permissions["scheduling:create"], permissions["scheduling:update"],
                permissions["calendar:read"], permissions["calendar:create"],
                permissions["calendar:update"], permissions["notifications:read"]
            ]),
            ("Support Staff", "Client care and documentation", False, [
                permissions["clients:read"], permissions["clients:update"],
                permissions["documentation:create"], permissions["documentation:read"],
                permissions["documentation:update"], permissions["reports:read"],
                permissions["staff:read"],  # Can view basic staff info
                permissions["appointments:read"], permissions["appointments:create"],
                permissions["appointments:update"],  # Can manage appointments
                permissions["scheduling:read"],  # Can view schedules and shifts
                permissions["time_clock:create"],  # Can clock in/out
                permissions["notifications:read"]  # Can view notifications
            ]),
            ("Billing Admin", "Financial and billing access", False, [
                permissions["billing:create"], permissions["billing:read"],
                permissions["billing:update"], permissions["billing:process"],
                permissions["reports:read"], permissions["reports:export"],
                permissions["staff:read"], permissions["staff:view_payroll"]
            ]),
            ("Client", "Client self-service portal access", False, [
                permissions["clients:read"],  # Can view own profile
                permissions["documentation:read"],  # Can view own documentation
                permissions["appointments:read"],  # Can view own appointments
                permissions["notifications:read"]  # Can view notifications
            ]),
        ]

        roles = {}
        for role_name, description, is_system, perms in roles_data:
            role = db.query(Role).filter(
                Role.name == role_name,
                Role.is_system_role == is_system
            ).first()
            if not role:
                role = Role(
                    name=role_name,
                    description=description,
                    is_system_role=is_system,
                    organization_id=None if is_system else default_org.id
                )
                role.permissions = perms
                db.add(role)
                db.commit()
                db.refresh(role)
            roles[role_name] = role

        logger.info(f"Created/verified {len(roles)} roles")

        # Create default audit settings for the organization
        audit_setting = db.query(AuditSetting).filter(
            AuditSetting.organization_id == default_org.id
        ).first()

        if not audit_setting:
            audit_setting = AuditSetting(
                organization_id=default_org.id,
                retention_days=2555,  # 7 years for HIPAA compliance
                archive_after_days=90,
                enable_async_logging=True,
                batch_size=100,
                sampling_rate=100,  # Log everything by default
                alert_on_phi_access=True,
                alert_on_breach=True,
                alert_on_failed_login=True,
                alert_email_addresses=[settings.AUDIT_ALERT_EMAIL],
                require_consent_verification=True,
                mask_sensitive_data=True,
                enable_integrity_check=True,
                log_read_operations=True,
                log_administrative_actions=True,
                log_api_responses=False
            )
            db.add(audit_setting)
            db.commit()
            db.refresh(audit_setting)
            logger.info("Default audit settings created")

        admin_user = db.query(User).filter(
            User.email == settings.DEFAULT_ADMIN_EMAIL
        ).first()

        if not admin_user:
            admin_user = User(
                email=settings.DEFAULT_ADMIN_EMAIL,
                username=settings.DEFAULT_ADMIN_USERNAME,
                password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                first_name=settings.DEFAULT_ADMIN_FULL_NAME.split()[0] if settings.DEFAULT_ADMIN_FULL_NAME else "Admin",
                last_name=settings.DEFAULT_ADMIN_FULL_NAME.split()[-1] if settings.DEFAULT_ADMIN_FULL_NAME and len(settings.DEFAULT_ADMIN_FULL_NAME.split()) > 1 else "User",
                organization_id=default_org.id,
                role_id=roles["Super Admin"].id,
                status=UserStatus.ACTIVE,
                email_verified=True
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Admin user created with email: {settings.DEFAULT_ADMIN_EMAIL}")
            logger.info(f"Admin password: {settings.DEFAULT_ADMIN_PASSWORD}")
        else:
            logger.info("Admin user already exists")

        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialization complete!")