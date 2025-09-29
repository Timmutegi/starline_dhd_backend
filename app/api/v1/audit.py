"""
Audit API Endpoints for HIPAA-Compliant Audit Log Management
Provides secure access to audit trails, compliance reporting, and violation management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_admin_or_above, get_super_admin
from app.models.user import User
from app.models.audit_log import AuditLog, AuditExport, AuditSetting, ComplianceViolation, AuditAction, DataClassification
from app.services.audit_service import AuditService
from app.schemas.audit import (
    AuditLogResponse, AuditLogListResponse, ComplianceReportResponse,
    ComplianceViolationResponse, AuditSettingsResponse, AuditSettingsUpdate,
    AuditExportRequest, AuditExportResponse, AuditFilterParams
)
import csv
import json
import io
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse, dependencies=[Depends(get_admin_or_above)])
async def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    phi_access_only: Optional[bool] = Query(False),
    data_classification: Optional[str] = Query(None)
):
    """
    Get paginated audit logs with optional filtering
    Requires admin permissions for organization-level access
    """
    audit_service = AuditService(db)

    # Build base query
    query = db.query(AuditLog).options(
        joinedload(AuditLog.user),
        joinedload(AuditLog.organization)
    )

    # Filter by organization (non-super-admins can only see their org)
    if current_user.role.name != "super_admin":
        query = query.filter(AuditLog.organization_id == current_user.organization_id)

    # Apply filters
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)

    if action:
        try:
            action_enum = AuditAction(action)
            query = query.filter(AuditLog.action == action_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {action}"
            )

    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    if phi_access_only:
        query = query.filter(AuditLog.phi_accessed == True)

    if data_classification:
        try:
            classification_enum = DataClassification(data_classification)
            query = query.filter(AuditLog.data_classification == classification_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid data classification: {data_classification}"
            )

    # Get total count for pagination
    total = query.count()

    # Apply pagination and ordering
    logs = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit).all()

    return AuditLogListResponse(
        logs=[AuditLogResponse.from_orm(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/logs/{log_id}", response_model=AuditLogResponse, dependencies=[Depends(get_admin_or_above)])
async def get_audit_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific audit log by ID"""
    query = db.query(AuditLog).options(
        joinedload(AuditLog.user),
        joinedload(AuditLog.organization)
    ).filter(AuditLog.id == log_id)

    # Filter by organization for non-super-admins
    if current_user.role.name != "super_admin":
        query = query.filter(AuditLog.organization_id == current_user.organization_id)

    log = query.first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )

    return AuditLogResponse.from_orm(log)


@router.get("/user/{user_id}/activity", response_model=List[AuditLogResponse], dependencies=[Depends(get_admin_or_above)])
async def get_user_activity(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get user activity history"""
    audit_service = AuditService(db)

    start_date = datetime.utcnow() - timedelta(days=days)
    organization_id = None if current_user.role.name == "super_admin" else current_user.organization_id

    logs = audit_service.get_user_activity(
        user_id=user_id,
        start_date=start_date,
        organization_id=organization_id,
        limit=limit
    )

    return [AuditLogResponse.from_orm(log) for log in logs]


@router.get("/resource/{resource_type}/{resource_id}/history", response_model=List[AuditLogResponse], dependencies=[Depends(get_admin_or_above)])
async def get_resource_history(
    resource_type: str,
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get complete change history for a specific resource"""
    audit_service = AuditService(db)

    organization_id = None if current_user.role.name == "super_admin" else current_user.organization_id

    logs = audit_service.get_resource_history(
        resource_type=resource_type,
        resource_id=resource_id,
        organization_id=organization_id
    )

    return [AuditLogResponse.from_orm(log) for log in logs]


@router.get("/phi-access", response_model=List[AuditLogResponse], dependencies=[Depends(get_admin_or_above)])
async def get_phi_access_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    client_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get PHI access logs for compliance monitoring"""
    audit_service = AuditService(db)

    start_date = datetime.utcnow() - timedelta(days=days)
    organization_id = None if current_user.role.name == "super_admin" else current_user.organization_id

    logs = audit_service.get_phi_access_logs(
        client_id=client_id,
        start_date=start_date,
        organization_id=organization_id
    )

    return [AuditLogResponse.from_orm(log) for log in logs[:limit]]


@router.get("/compliance/report", response_model=ComplianceReportResponse, dependencies=[Depends(get_admin_or_above)])
async def generate_compliance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    report_type: str = Query("hipaa")
):
    """Generate comprehensive compliance report"""
    audit_service = AuditService(db)

    organization_id = current_user.organization_id
    if current_user.role.name == "super_admin" and not organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization ID required for compliance reports"
        )

    report = audit_service.generate_compliance_report(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
        report_type=report_type
    )

    return ComplianceReportResponse(**report)


@router.get("/violations", response_model=List[ComplianceViolationResponse], dependencies=[Depends(get_admin_or_above)])
async def get_compliance_violations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365)
):
    """Get compliance violations"""
    query = db.query(ComplianceViolation).options(
        joinedload(ComplianceViolation.audit_log),
        joinedload(ComplianceViolation.acknowledger)
    )

    # Filter by organization
    if current_user.role.name != "super_admin":
        query = query.filter(ComplianceViolation.organization_id == current_user.organization_id)

    # Apply filters
    if status_filter:
        query = query.filter(ComplianceViolation.status == status_filter)

    if severity:
        query = query.filter(ComplianceViolation.severity == severity)

    # Filter by date
    start_date = datetime.utcnow() - timedelta(days=days)
    query = query.filter(ComplianceViolation.detected_at >= start_date)

    violations = query.order_by(desc(ComplianceViolation.detected_at)).all()

    return [ComplianceViolationResponse.from_orm(violation) for violation in violations]


@router.patch("/violations/{violation_id}/acknowledge", dependencies=[Depends(get_admin_or_above)])
async def acknowledge_violation(
    violation_id: str,
    resolution_notes: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge and provide resolution for a compliance violation"""
    query = db.query(ComplianceViolation).filter(ComplianceViolation.id == violation_id)

    # Filter by organization
    if current_user.role.name != "super_admin":
        query = query.filter(ComplianceViolation.organization_id == current_user.organization_id)

    violation = query.first()
    if not violation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found"
        )

    violation.status = "acknowledged"
    violation.acknowledged_at = datetime.utcnow()
    violation.acknowledged_by = current_user.id
    violation.resolution_notes = resolution_notes

    db.commit()

    return {"message": "Violation acknowledged successfully"}


@router.get("/settings", response_model=AuditSettingsResponse, dependencies=[Depends(get_admin_or_above)])
async def get_audit_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get audit settings for the organization"""
    if current_user.role.name == "super_admin" and not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context required"
        )

    settings = db.query(AuditSetting).filter(
        AuditSetting.organization_id == current_user.organization_id
    ).first()

    if not settings:
        # Create default settings
        settings = AuditSetting(organization_id=current_user.organization_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return AuditSettingsResponse.from_orm(settings)


@router.put("/settings", response_model=AuditSettingsResponse, dependencies=[Depends(get_admin_or_above)])
async def update_audit_settings(
    settings_update: AuditSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update audit settings for the organization"""
    if current_user.role.name == "super_admin" and not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context required"
        )

    settings = db.query(AuditSetting).filter(
        AuditSetting.organization_id == current_user.organization_id
    ).first()

    if not settings:
        settings = AuditSetting(organization_id=current_user.organization_id)
        db.add(settings)

    # Update settings
    update_data = settings_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)

    return AuditSettingsResponse.from_orm(settings)


@router.post("/export", response_model=AuditExportResponse, dependencies=[Depends(get_admin_or_above)])
async def export_audit_logs(
    export_request: AuditExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export audit logs for external audit or compliance"""
    audit_service = AuditService(db)

    # Create export record
    export_record = AuditExport(
        organization_id=current_user.organization_id,
        exported_by=current_user.id,
        export_format=export_request.format,
        date_from=export_request.start_date,
        date_to=export_request.end_date,
        filters_applied=export_request.filters.dict() if export_request.filters else {},
        purpose=export_request.purpose,
        authorized_by=export_request.authorized_by,
        external_audit_ref=export_request.audit_reference,
        record_count=0  # Will be updated after export
    )

    db.add(export_record)
    db.commit()
    db.refresh(export_record)

    # Schedule background export task
    background_tasks.add_task(
        _process_audit_export,
        export_record.id,
        export_request,
        current_user.organization_id
    )

    return AuditExportResponse(
        export_id=str(export_record.id),
        status="processing",
        message="Export initiated. You will be notified when complete.",
        created_at=export_record.created_at
    )


@router.get("/export/{export_id}/status", dependencies=[Depends(get_admin_or_above)])
async def get_export_status(
    export_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get status of an audit log export"""
    query = db.query(AuditExport).filter(AuditExport.id == export_id)

    if current_user.role.name != "super_admin":
        query = query.filter(AuditExport.organization_id == current_user.organization_id)

    export_record = query.first()
    if not export_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found"
        )

    status = "completed" if export_record.file_path else "processing"

    return {
        "export_id": str(export_record.id),
        "status": status,
        "record_count": export_record.record_count,
        "file_size_bytes": export_record.file_size_bytes,
        "created_at": export_record.created_at,
        "expires_at": export_record.expires_at
    }


@router.get("/export/{export_id}/download", dependencies=[Depends(get_admin_or_above)])
async def download_export(
    export_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download exported audit logs"""
    query = db.query(AuditExport).filter(AuditExport.id == export_id)

    if current_user.role.name != "super_admin":
        query = query.filter(AuditExport.organization_id == current_user.organization_id)

    export_record = query.first()
    if not export_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found"
        )

    if not export_record.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export not yet complete"
        )

    # Check if export has expired
    if export_record.expires_at and export_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Export has expired"
        )

    # Return file stream (implementation would depend on storage system)
    # For now, return a placeholder response
    return {"message": "File download would be implemented here", "file_path": export_record.file_path}


async def _process_audit_export(export_id: str, export_request: AuditExportRequest, organization_id: str):
    """Background task to process audit log export"""
    try:
        db = next(get_db())
        audit_service = AuditService(db)

        # Build query with filters
        query = db.query(AuditLog).filter(
            and_(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= export_request.start_date,
                AuditLog.created_at <= export_request.end_date
            )
        )

        # Apply additional filters if provided
        if export_request.filters:
            if export_request.filters.user_id:
                query = query.filter(AuditLog.user_id == export_request.filters.user_id)
            if export_request.filters.resource_type:
                query = query.filter(AuditLog.resource_type == export_request.filters.resource_type)
            if export_request.filters.phi_access_only:
                query = query.filter(AuditLog.phi_accessed == True)

        logs = query.order_by(AuditLog.created_at).all()

        # Generate file content based on format
        if export_request.format == "csv":
            file_content = _generate_csv_export(logs)
            file_extension = "csv"
        elif export_request.format == "json":
            file_content = _generate_json_export(logs)
            file_extension = "json"
        else:
            raise ValueError(f"Unsupported export format: {export_request.format}")

        # Save file (implementation would save to S3 or file system)
        file_path = f"exports/audit_{export_id}.{file_extension}"
        file_size = len(file_content.encode())

        # Update export record
        export_record = db.query(AuditExport).filter(AuditExport.id == export_id).first()
        if export_record:
            export_record.file_path = file_path
            export_record.file_size_bytes = file_size
            export_record.record_count = len(logs)
            export_record.expires_at = datetime.utcnow() + timedelta(days=7)  # Expire in 7 days
            db.commit()

        db.close()

    except Exception as e:
        logger.error(f"Failed to process audit export {export_id}: {e}")


def _generate_csv_export(logs: List[AuditLog]) -> str:
    """Generate CSV export of audit logs"""
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "ID", "Timestamp", "User ID", "Action", "Resource Type", "Resource ID",
        "IP Address", "User Agent", "Response Status", "Error Message", "PHI Accessed"
    ])

    # Write data
    for log in logs:
        writer.writerow([
            str(log.id),
            log.created_at.isoformat(),
            str(log.user_id) if log.user_id else "",
            log.action.value,
            log.resource_type,
            str(log.resource_id) if log.resource_id else "",
            log.ip_address or "",
            log.user_agent or "",
            log.response_status or "",
            log.error_message or "",
            log.phi_accessed
        ])

    return output.getvalue()


def _generate_json_export(logs: List[AuditLog]) -> str:
    """Generate JSON export of audit logs"""
    export_data = []

    for log in logs:
        export_data.append({
            "id": str(log.id),
            "timestamp": log.created_at.isoformat(),
            "user_id": str(log.user_id) if log.user_id else None,
            "action": log.action.value,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "resource_name": log.resource_name,
            "data_classification": log.data_classification.value,
            "phi_accessed": log.phi_accessed,
            "consent_verified": log.consent_verified,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "http_method": log.http_method,
            "endpoint": log.endpoint,
            "response_status": log.response_status,
            "error_message": log.error_message,
            "duration_ms": log.duration_ms,
            "changes_summary": log.changes_summary
        })

    return json.dumps(export_data, indent=2)