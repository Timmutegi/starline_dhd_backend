"""
Audit Middleware for HIPAA-Compliant Request/Response Logging
Automatically captures API activity for comprehensive audit trails
"""
import json
import time
import uuid
import asyncio
from typing import Callable, Optional, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.audit_service import AuditService
from app.models.audit_log import AuditAction, DataClassification
from app.models.user import User
from app.core.security import decode_token
import logging

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic audit logging of API requests and responses"""

    def __init__(self, app: ASGIApp, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs", "/openapi.json", "/health", "/favicon.ico",
            "/api/v1/audit/logs"  # Prevent recursive logging
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response for audit logging"""

        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Extract request information
        request_info = await self._extract_request_info(request)

        # Process the request
        response = await call_next(request)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Extract response information
        response_info = self._extract_response_info(response)

        # Log the audit event asynchronously
        asyncio.create_task(
            self._log_audit_event(
                request_info=request_info,
                response_info=response_info,
                request_id=request_id,
                duration_ms=duration_ms
            )
        )

        return response

    async def _extract_request_info(self, request: Request) -> Dict[str, Any]:
        """Extract relevant information from the request"""
        info = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent"),
            "user_id": None,
            "organization_id": None,
            "body": None
        }

        # Extract user information from JWT token
        authorization = request.headers.get("authorization")
        if authorization and authorization.startswith("Bearer "):
            try:
                token = authorization.split(" ")[1]
                payload = decode_token(token)
                info["user_id"] = payload.get("sub")
                info["organization_id"] = payload.get("organization_id")
            except Exception as e:
                logger.debug(f"Could not decode token: {e}")

        # Extract request body for write operations
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            try:
                # Read body without consuming it
                body = await request.body()
                if body:
                    # Try to parse as JSON
                    try:
                        info["body"] = json.loads(body.decode())
                    except json.JSONDecodeError:
                        info["body"] = body.decode()[:1000]  # Limit body size
            except Exception as e:
                logger.debug(f"Could not read request body: {e}")

        return info

    def _extract_response_info(self, response: Response) -> Dict[str, Any]:
        """Extract relevant information from the response"""
        info = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "media_type": getattr(response, "media_type", None)
        }

        # For JSON responses, try to extract response body size
        if hasattr(response, "body"):
            try:
                info["body_size"] = len(response.body)
            except Exception:
                pass

        return info

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address considering proxies"""
        # Check for X-Forwarded-For header (from load balancers/proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Check for X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client host
        return request.client.host if request.client else "unknown"

    async def _log_audit_event(
        self,
        request_info: Dict[str, Any],
        response_info: Dict[str, Any],
        request_id: str,
        duration_ms: int
    ) -> None:
        """Create audit log entry for the request/response"""
        try:
            # Get database session
            db = next(get_db())
            audit_service = AuditService(db)

            # Determine the audit action based on HTTP method
            action_map = {
                "GET": AuditAction.READ,
                "POST": AuditAction.CREATE,
                "PUT": AuditAction.UPDATE,
                "PATCH": AuditAction.UPDATE,
                "DELETE": AuditAction.DELETE
            }
            action = action_map.get(request_info["method"], AuditAction.READ)

            # Extract resource information from the URL path
            resource_info = self._extract_resource_info(request_info["path"], request_info.get("body"))

            # Determine if this is an error
            error_message = None
            if response_info["status_code"] >= 400:
                error_message = f"HTTP {response_info['status_code']} error"

            # Create the audit log
            audit_service.log_action(
                action=action,
                resource_type=resource_info["type"],
                user_id=request_info["user_id"],
                organization_id=request_info["organization_id"],
                resource_id=resource_info["id"],
                resource_name=resource_info["name"],
                old_values=None,  # Will be set by model-level triggers
                new_values=request_info.get("body") if action != AuditAction.READ else None,
                ip_address=request_info["client_ip"],
                user_agent=request_info["user_agent"],
                request_id=request_id,
                http_method=request_info["method"],
                endpoint=request_info["path"],
                response_status=response_info["status_code"],
                duration_ms=duration_ms,
                error_message=error_message
            )

            db.close()

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

    def _extract_resource_info(self, path: str, body: Optional[Dict]) -> Dict[str, Optional[str]]:
        """Extract resource type and ID from the URL path"""
        # Default values
        resource_type = "unknown"
        resource_id = None
        resource_name = None

        # Parse common API patterns
        path_parts = [p for p in path.split("/") if p]

        # Skip /api/v1 prefix
        if len(path_parts) >= 2 and path_parts[0] == "api" and path_parts[1] == "v1":
            path_parts = path_parts[2:]

        if path_parts:
            # First part is typically the resource type
            resource_type = path_parts[0]

            # Check for resource ID in path
            if len(path_parts) >= 2:
                potential_id = path_parts[1]
                # Check if it looks like a UUID
                if len(potential_id) == 36 and potential_id.count("-") == 4:
                    resource_id = potential_id

            # Extract resource name from body if available
            if body and isinstance(body, dict):
                # Common name fields
                name_fields = ["name", "title", "full_name", "email", "username"]
                for field in name_fields:
                    if field in body:
                        resource_name = str(body[field])
                        break

        # Map specific endpoints to better resource types
        resource_type_map = {
            "auth": "authentication",
            "users": "user",
            "clients": "client",
            "staff": "staff",
            "vitals": "vitals",
            "medications": "medication",
            "appointments": "appointment",
            "schedules": "schedule",
            "incidents": "incident_report",
            "billing": "billing",
            "reports": "report"
        }

        resource_type = resource_type_map.get(resource_type, resource_type)

        return {
            "type": resource_type,
            "id": resource_id,
            "name": resource_name
        }


class AuditRequestMiddleware:
    """Additional request middleware for setting audit context"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        """Set audit context for the request"""
        if scope["type"] == "http":
            # Add request ID to scope for use in other parts of the application
            scope["request_id"] = str(uuid.uuid4())

        await self.app(scope, receive, send)


# Utility functions for manual audit logging

def get_current_request_id() -> Optional[str]:
    """Get the current request ID from context (if available)"""
    try:
        from contextvars import ContextVar
        # This would need to be set up with proper context management
        return None
    except ImportError:
        return None


def audit_decorator(
    action: AuditAction,
    resource_type: str,
    extract_resource_id: Optional[Callable] = None,
    log_response: bool = False
):
    """Decorator for adding audit logging to specific functions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            result = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                duration_ms = int((time.time() - start_time) * 1000)

                # Extract resource ID if function provided
                resource_id = None
                if extract_resource_id:
                    try:
                        resource_id = extract_resource_id(*args, **kwargs)
                    except Exception:
                        pass

                # Log the audit event
                try:
                    db = next(get_db())
                    audit_service = AuditService(db)

                    # Extract user info from kwargs if available
                    user_id = None
                    if "current_user" in kwargs:
                        user = kwargs["current_user"]
                        if hasattr(user, "id"):
                            user_id = str(user.id)

                    audit_service.log_action(
                        action=action,
                        resource_type=resource_type,
                        user_id=user_id,
                        resource_id=resource_id,
                        new_values={"function": func.__name__, "args": str(args)[:500]},
                        duration_ms=duration_ms,
                        error_message=error,
                        response_status=500 if error else 200
                    )

                    db.close()
                except Exception as audit_error:
                    logger.error(f"Audit logging failed: {audit_error}")

        return wrapper
    return decorator