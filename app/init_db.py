from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models.user import User, Organization, Role, Permission, UserStatus
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
            ("Organization Admin", "Manage organization and users", False, [
                permissions["users:create"], permissions["users:read"],
                permissions["users:update"], permissions["users:delete"],
                permissions["roles:read"], permissions["organizations:read"],
                permissions["organizations:update"]
            ]),
            ("Support Staff", "Client care and documentation", False, [
                permissions["clients:read"], permissions["clients:update"],
                permissions["documentation:create"], permissions["documentation:read"],
                permissions["documentation:update"], permissions["reports:read"]
            ]),
            ("Billing Admin", "Financial and billing access", False, [
                permissions["billing:create"], permissions["billing:read"],
                permissions["billing:update"], permissions["billing:process"],
                permissions["reports:read"], permissions["reports:export"]
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