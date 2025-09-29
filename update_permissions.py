from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.models.user import User, Organization, Role, Permission

def update_super_admin_permissions():
    db = SessionLocal()
    try:
        # Get Super Admin role
        super_admin_role = db.query(Role).filter(
            Role.name == "Super Admin",
            Role.is_system_role == True
        ).first()

        if not super_admin_role:
            print("Super Admin role not found!")
            return

        print(f"Found Super Admin role with {len(super_admin_role.permissions)} permissions")

        # Get all permissions
        all_permissions = db.query(Permission).all()

        print(f"Found {len(all_permissions)} total permissions in database")

        # Update Super Admin to have all permissions
        super_admin_role.permissions = all_permissions

        db.commit()
        db.refresh(super_admin_role)

        print(f"Updated Super Admin role to have {len(super_admin_role.permissions)} permissions")

        # Print scheduling permissions specifically
        scheduling_perms = [p for p in all_permissions if p.resource in ['scheduling', 'appointments', 'time_clock', 'calendar']]
        print(f"Scheduling-related permissions: {len(scheduling_perms)}")
        for p in scheduling_perms:
            print(f"  - {p.resource}:{p.action}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_super_admin_permissions()