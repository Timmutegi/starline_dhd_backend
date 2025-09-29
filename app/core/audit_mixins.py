"""
Audit Mixins for SQLAlchemy Models
Provides automatic audit logging capabilities for sensitive data models
"""
from sqlalchemy import event
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import json
import asyncio
import logging
from app.models.audit_log import AuditAction

logger = logging.getLogger(__name__)


class AuditMixin:
    """
    Mixin class that provides automatic audit logging for model changes
    Models that inherit from this mixin will automatically log CRUD operations
    """

    # Override these in the child class
    __audit_resource_type__ = "unknown"
    __audit_phi_fields__ = []  # Fields that contain PHI
    __audit_exclude_fields__ = ["password_hash", "created_at", "updated_at"]  # Fields to exclude from audit

    @classmethod
    def __declare_last__(cls):
        """Set up audit event listeners after the model is fully configured"""
        event.listen(cls, 'after_insert', cls._audit_after_insert)
        event.listen(cls, 'after_update', cls._audit_after_update)
        event.listen(cls, 'after_delete', cls._audit_after_delete)

    @classmethod
    def _audit_after_insert(cls, mapper, connection, target):
        """Audit log after insert"""
        cls._create_audit_log(
            target=target,
            action=AuditAction.CREATE,
            old_values=None,
            new_values=cls._get_audit_values(target)
        )

    @classmethod
    def _audit_after_update(cls, mapper, connection, target):
        """Audit log after update"""
        old_values = {}
        new_values = {}

        # Get changed values
        state = target.__dict__.copy()
        history = {}

        # Get the session and inspect the target for changes
        for attr in mapper.columns.keys():
            hist = getattr(target.__class__, attr).property.history
            if hasattr(target, attr):
                old_value = getattr(target, attr)
                # Check if attribute has changed
                if attr in state:
                    new_value = state[attr]
                    if old_value != new_value:
                        if attr not in cls.__audit_exclude_fields__:
                            old_values[attr] = cls._serialize_value(old_value)
                            new_values[attr] = cls._serialize_value(new_value)

        if old_values or new_values:
            cls._create_audit_log(
                target=target,
                action=AuditAction.UPDATE,
                old_values=old_values,
                new_values=new_values
            )

    @classmethod
    def _audit_after_delete(cls, mapper, connection, target):
        """Audit log after delete"""
        cls._create_audit_log(
            target=target,
            action=AuditAction.DELETE,
            old_values=cls._get_audit_values(target),
            new_values=None
        )

    @classmethod
    def _create_audit_log(cls, target, action: AuditAction, old_values: Optional[Dict], new_values: Optional[Dict]):
        """Create audit log entry"""
        try:
            # Create a new session for audit logging
            from app.core.database import SessionLocal
            # Lazy import to avoid circular dependencies
            from app.services.audit_service import AuditService

            audit_db = SessionLocal()

            try:
                audit_service = AuditService(audit_db)

                # Get resource information
                resource_id = str(getattr(target, 'id', None)) if hasattr(target, 'id') else None
                resource_name = cls._get_resource_name(target)
                organization_id = str(getattr(target, 'organization_id', None)) if hasattr(target, 'organization_id') else None

                # Check if this is PHI data
                phi_accessed = cls._contains_phi(old_values, new_values)

                audit_service.log_action(
                    action=action,
                    resource_type=cls.__audit_resource_type__,
                    organization_id=organization_id,
                    resource_id=resource_id,
                    resource_name=resource_name,
                    old_values=old_values,
                    new_values=new_values,
                    metadata={
                        "model_class": cls.__name__,
                        "phi_accessed": phi_accessed,
                        "audit_source": "model_trigger"
                    }
                )

            finally:
                audit_db.close()

        except Exception as e:
            logger.error(f"Failed to create audit log for {cls.__name__}: {e}")

    @classmethod
    def _get_audit_values(cls, target) -> Dict[str, Any]:
        """Extract audit-relevant values from the target object"""
        values = {}

        # Get all column values
        for column in target.__table__.columns:
            attr_name = column.name
            if attr_name not in cls.__audit_exclude_fields__:
                value = getattr(target, attr_name, None)
                values[attr_name] = cls._serialize_value(value)

        return values

    @classmethod
    def _serialize_value(cls, value) -> Any:
        """Serialize a value for JSON storage in audit logs"""
        if value is None:
            return None
        elif hasattr(value, 'isoformat'):  # datetime objects
            return value.isoformat()
        elif hasattr(value, '__dict__'):  # Complex objects
            return str(value)
        else:
            return value

    @classmethod
    def _get_resource_name(cls, target) -> Optional[str]:
        """Get a human-readable name for the resource"""
        # Try common name fields
        name_fields = ['name', 'title', 'full_name', 'email', 'username', 'first_name']

        for field in name_fields:
            if hasattr(target, field):
                value = getattr(target, field)
                if value:
                    return str(value)

        # Fall back to ID
        if hasattr(target, 'id'):
            return f"{cls.__audit_resource_type__}:{getattr(target, 'id')}"

        return None

    @classmethod
    def _contains_phi(cls, old_values: Optional[Dict], new_values: Optional[Dict]) -> bool:
        """Check if the changes involve PHI fields"""
        phi_fields = cls.__audit_phi_fields__

        if not phi_fields:
            return False

        # Check if any PHI fields are in the changed values
        for values in [old_values, new_values]:
            if values:
                for field in phi_fields:
                    if field in values:
                        return True

        return False


class PHIAuditMixin(AuditMixin):
    """
    Enhanced audit mixin for models that contain PHI data
    Provides additional compliance monitoring and alerts
    """

    @classmethod
    def _create_audit_log(cls, target, action: AuditAction, old_values: Optional[Dict], new_values: Optional[Dict]):
        """Create audit log with enhanced PHI monitoring"""
        try:
            from app.core.database import SessionLocal
            # Lazy import to avoid circular dependencies
            from app.services.audit_service import AuditService

            audit_db = SessionLocal()

            try:
                audit_service = AuditService(audit_db)

                # Get resource information
                resource_id = str(getattr(target, 'id', None)) if hasattr(target, 'id') else None
                resource_name = cls._get_resource_name(target)
                organization_id = str(getattr(target, 'organization_id', None)) if hasattr(target, 'organization_id') else None

                # Always mark as PHI for this mixin
                phi_accessed = True

                # Log PHI access specifically
                if action == AuditAction.READ:
                    audit_service.log_phi_access(
                        user_id=None,  # Will be set by middleware if available
                        client_id=resource_id if cls.__audit_resource_type__ == "client" else None,
                        data_type=cls.__audit_resource_type__,
                        purpose="Model access",
                        organization_id=organization_id
                    )
                else:
                    audit_service.log_action(
                        action=action,
                        resource_type=cls.__audit_resource_type__,
                        organization_id=organization_id,
                        resource_id=resource_id,
                        resource_name=resource_name,
                        old_values=old_values,
                        new_values=new_values,
                        metadata={
                            "model_class": cls.__name__,
                            "phi_data": True,
                            "audit_source": "phi_model_trigger"
                        }
                    )

            finally:
                audit_db.close()

        except Exception as e:
            logger.error(f"Failed to create PHI audit log for {cls.__name__}: {e}")


def audit_decorator(resource_type: str, phi_fields: list = None, exclude_fields: list = None):
    """
    Decorator to add audit logging to existing models

    Usage:
    @audit_decorator("client", phi_fields=["medical_record", "ssn"])
    class Client(Base):
        ...
    """
    def decorator(cls):
        # Set audit configuration
        cls.__audit_resource_type__ = resource_type
        cls.__audit_phi_fields__ = phi_fields or []
        cls.__audit_exclude_fields__ = (exclude_fields or []) + ["password_hash", "created_at", "updated_at"]

        # Add audit methods to the class
        cls._audit_after_insert = classmethod(AuditMixin._audit_after_insert.__func__)
        cls._audit_after_update = classmethod(AuditMixin._audit_after_update.__func__)
        cls._audit_after_delete = classmethod(AuditMixin._audit_after_delete.__func__)
        cls._create_audit_log = classmethod(AuditMixin._create_audit_log.__func__)
        cls._get_audit_values = classmethod(AuditMixin._get_audit_values.__func__)
        cls._serialize_value = classmethod(AuditMixin._serialize_value.__func__)
        cls._get_resource_name = classmethod(AuditMixin._get_resource_name.__func__)
        cls._contains_phi = classmethod(AuditMixin._contains_phi.__func__)

        # Set up event listeners
        event.listen(cls, 'after_insert', cls._audit_after_insert)
        event.listen(cls, 'after_update', cls._audit_after_update)
        event.listen(cls, 'after_delete', cls._audit_after_delete)

        return cls

    return decorator


def log_phi_access(model_instance, user_id: str, purpose: str = "Data access"):
    """
    Manually log PHI access for read operations
    Call this when PHI data is accessed outside of model changes
    """
    try:
        from app.core.database import SessionLocal
        # Lazy import to avoid circular dependencies
        from app.services.audit_service import AuditService

        audit_db = SessionLocal()

        try:
            audit_service = AuditService(audit_db)

            resource_id = str(getattr(model_instance, 'id', None)) if hasattr(model_instance, 'id') else None
            organization_id = str(getattr(model_instance, 'organization_id', None)) if hasattr(model_instance, 'organization_id') else None

            # Determine client ID for PHI access
            client_id = None
            if hasattr(model_instance, '__audit_resource_type__'):
                if model_instance.__audit_resource_type__ == "client":
                    client_id = resource_id
                elif hasattr(model_instance, 'client_id'):
                    client_id = str(getattr(model_instance, 'client_id'))

            audit_service.log_phi_access(
                user_id=user_id,
                client_id=client_id or resource_id,
                data_type=getattr(model_instance, '__audit_resource_type__', model_instance.__class__.__name__.lower()),
                purpose=purpose,
                organization_id=organization_id
            )

        finally:
            audit_db.close()

    except Exception as e:
        logger.error(f"Failed to log PHI access: {e}")