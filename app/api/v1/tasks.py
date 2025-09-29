from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from datetime import datetime, date
from typing import Optional, List
import uuid
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.client import Client
from app.models.task import Task, TaskStatusEnum, TaskPriorityEnum
from app.schemas.documentation import (
    TaskCreate,
    TaskResponse,
    TaskUpdate
)
from app.schemas.dashboard import TaskSummary

router = APIRouter()

@router.post("/", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new task for a client
    """
    try:
        # Verify client exists and user has access
        client = db.query(Client).filter(
            and_(
                Client.id == task_data.client_id,
                Client.organization_id == current_user.organization_id
            )
        ).first()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Verify assigned user exists if provided
        assigned_to_user = None
        if task_data.assigned_to:
            assigned_to_user = db.query(User).filter(
                and_(
                    User.id == task_data.assigned_to,
                    User.organization_id == current_user.organization_id
                )
            ).first()

            if not assigned_to_user:
                raise HTTPException(status_code=404, detail="Assigned user not found")

        # Create task
        task = Task(
            id=uuid.uuid4(),
            client_id=task_data.client_id,
            organization_id=current_user.organization_id,
            assigned_to=task_data.assigned_to,
            created_by=current_user.id,
            title=task_data.title,
            description=task_data.description,
            priority=TaskPriorityEnum(task_data.priority),
            due_date=task_data.due_date
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        return TaskResponse(
            id=str(task.id),
            client_id=str(task.client_id),
            client_name=f"{client.first_name} {client.last_name}",
            title=task.title,
            description=task.description,
            priority=task.priority.value,
            status=task.status.value,
            due_date=task.due_date,
            assigned_to=str(task.assigned_to) if task.assigned_to else None,
            assigned_to_name=f"{assigned_to_user.first_name} {assigned_to_user.last_name}" if assigned_to_user else None,
            created_by=str(task.created_by),
            created_by_name=f"{current_user.first_name} {current_user.last_name}",
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create task: {str(e)}"
        )

@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user ID"),
    status: Optional[str] = Query(None, description="Filter by task status"),
    priority: Optional[str] = Query(None, description="Filter by task priority"),
    due_date_from: Optional[date] = Query(None, description="Filter by due date from"),
    due_date_to: Optional[date] = Query(None, description="Filter by due date to"),
    overdue_only: bool = Query(False, description="Show only overdue tasks"),
    limit: int = Query(50, le=100, description="Number of tasks to retrieve"),
    offset: int = Query(0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get tasks with optional filtering
    """
    try:
        query = db.query(Task).filter(
            Task.organization_id == current_user.organization_id
        )

        if client_id:
            query = query.filter(Task.client_id == client_id)

        if assigned_to:
            query = query.filter(Task.assigned_to == assigned_to)

        if status:
            try:
                task_status = TaskStatusEnum(status)
                query = query.filter(Task.status == task_status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid task status: {status}")

        if priority:
            try:
                task_priority = TaskPriorityEnum(priority)
                query = query.filter(Task.priority == task_priority)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid task priority: {priority}")

        if due_date_from:
            query = query.filter(func.date(Task.due_date) >= due_date_from)

        if due_date_to:
            query = query.filter(func.date(Task.due_date) <= due_date_to)

        if overdue_only:
            query = query.filter(
                and_(
                    Task.due_date < datetime.utcnow(),
                    Task.status.in_([TaskStatusEnum.PENDING, TaskStatusEnum.IN_PROGRESS])
                )
            )

        tasks = query.order_by(
            Task.priority.desc(),  # Higher priority first
            Task.due_date.asc(),   # Earlier due date first
            Task.created_at.desc() # Most recent first
        ).offset(offset).limit(limit).all()

        results = []
        for task in tasks:
            client = db.query(Client).filter(Client.id == task.client_id).first()
            assigned_to_user = db.query(User).filter(User.id == task.assigned_to).first() if task.assigned_to else None
            created_by_user = db.query(User).filter(User.id == task.created_by).first()

            results.append(TaskResponse(
                id=str(task.id),
                client_id=str(task.client_id),
                client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
                title=task.title,
                description=task.description,
                priority=task.priority.value,
                status=task.status.value,
                due_date=task.due_date,
                assigned_to=str(task.assigned_to) if task.assigned_to else None,
                assigned_to_name=f"{assigned_to_user.first_name} {assigned_to_user.last_name}" if assigned_to_user else None,
                created_by=str(task.created_by),
                created_by_name=f"{created_by_user.first_name} {created_by_user.last_name}" if created_by_user else "Unknown",
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at
            ))

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve tasks: {str(e)}"
        )

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific task by ID
    """
    try:
        task = db.query(Task).filter(
            and_(
                Task.id == task_id,
                Task.organization_id == current_user.organization_id
            )
        ).first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        client = db.query(Client).filter(Client.id == task.client_id).first()
        assigned_to_user = db.query(User).filter(User.id == task.assigned_to).first() if task.assigned_to else None
        created_by_user = db.query(User).filter(User.id == task.created_by).first()

        return TaskResponse(
            id=str(task.id),
            client_id=str(task.client_id),
            client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
            title=task.title,
            description=task.description,
            priority=task.priority.value,
            status=task.status.value,
            due_date=task.due_date,
            assigned_to=str(task.assigned_to) if task.assigned_to else None,
            assigned_to_name=f"{assigned_to_user.first_name} {assigned_to_user.last_name}" if assigned_to_user else None,
            created_by=str(task.created_by),
            created_by_name=f"{created_by_user.first_name} {created_by_user.last_name}" if created_by_user else "Unknown",
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve task: {str(e)}"
        )

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a task
    """
    try:
        task = db.query(Task).filter(
            and_(
                Task.id == task_id,
                Task.organization_id == current_user.organization_id
            )
        ).first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Update fields if provided
        if task_update.title is not None:
            task.title = task_update.title
        if task_update.description is not None:
            task.description = task_update.description
        if task_update.priority is not None:
            task.priority = TaskPriorityEnum(task_update.priority)
        if task_update.status is not None:
            old_status = task.status
            task.status = TaskStatusEnum(task_update.status)

            # Set completed_at when task is marked as completed
            if task.status == TaskStatusEnum.COMPLETED and old_status != TaskStatusEnum.COMPLETED:
                task.completed_at = datetime.utcnow()
            elif task.status != TaskStatusEnum.COMPLETED:
                task.completed_at = None

        if task_update.due_date is not None:
            task.due_date = task_update.due_date
        if task_update.assigned_to is not None:
            # Verify assigned user exists
            if task_update.assigned_to:
                assigned_user = db.query(User).filter(
                    and_(
                        User.id == task_update.assigned_to,
                        User.organization_id == current_user.organization_id
                    )
                ).first()
                if not assigned_user:
                    raise HTTPException(status_code=404, detail="Assigned user not found")

            task.assigned_to = task_update.assigned_to
        if task_update.notes is not None:
            task.notes = task_update.notes

        task.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(task)

        # Return updated task
        client = db.query(Client).filter(Client.id == task.client_id).first()
        assigned_to_user = db.query(User).filter(User.id == task.assigned_to).first() if task.assigned_to else None
        created_by_user = db.query(User).filter(User.id == task.created_by).first()

        return TaskResponse(
            id=str(task.id),
            client_id=str(task.client_id),
            client_name=f"{client.first_name} {client.last_name}" if client else "Unknown",
            title=task.title,
            description=task.description,
            priority=task.priority.value,
            status=task.status.value,
            due_date=task.due_date,
            assigned_to=str(task.assigned_to) if task.assigned_to else None,
            assigned_to_name=f"{assigned_to_user.first_name} {assigned_to_user.last_name}" if assigned_to_user else None,
            created_by=str(task.created_by),
            created_by_name=f"{created_by_user.first_name} {created_by_user.last_name}" if created_by_user else "Unknown",
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update task: {str(e)}"
        )

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a task
    """
    try:
        task = db.query(Task).filter(
            and_(
                Task.id == task_id,
                Task.organization_id == current_user.organization_id
            )
        ).first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        db.delete(task)
        db.commit()

        return {"message": "Task deleted successfully", "id": task_id}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete task: {str(e)}"
        )

@router.get("/summary/stats", response_model=TaskSummary)
async def get_task_summary(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get task summary statistics
    """
    try:
        base_query = db.query(Task).filter(
            Task.organization_id == current_user.organization_id
        )

        if client_id:
            base_query = base_query.filter(Task.client_id == client_id)

        if assigned_to:
            base_query = base_query.filter(Task.assigned_to == assigned_to)

        total_tasks = base_query.count()
        completed_tasks = base_query.filter(Task.status == TaskStatusEnum.COMPLETED).count()
        pending_tasks = base_query.filter(Task.status == TaskStatusEnum.PENDING).count()
        overdue_tasks = base_query.filter(
            and_(
                Task.due_date < datetime.utcnow(),
                Task.status.in_([TaskStatusEnum.PENDING, TaskStatusEnum.IN_PROGRESS])
            )
        ).count()

        completion_rate = 0.0 if total_tasks == 0 else (completed_tasks / total_tasks) * 100

        return TaskSummary(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            pending_tasks=pending_tasks,
            overdue_tasks=overdue_tasks,
            completion_rate=completion_rate
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve task summary: {str(e)}"
        )