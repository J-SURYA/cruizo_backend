from fastapi import APIRouter, Depends, Security, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional


from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import backup_service
from app.utils.objectid_utils import PyObjectId


router = APIRouter()


@router.post("/schedules", response_model=schemas.BackupSchedulePublic)
async def create_backup_schedule(
    schedule_data: schemas.BackupScheduleCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["backup_schedule:create"]
    ),
):
    """
    Create a new scheduled database backup configuration.

    Args:
        schedule_data: Backup schedule configuration including frequency and type
        db: Database session dependency
        current_user: Authenticated user with backup_schedule:create permission

    Returns:
        Newly created backup schedule details
    """
    return await backup_service.create_backup_schedule(db, schedule_data, current_user)


@router.get("/schedules", response_model=List[schemas.BackupSchedulePublic])
async def get_all_backup_schedules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    frequency: Optional[str] = Query(None),
    status_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["backup_schedule:read"]),
):
    """
    Retrieve all configured backup schedules with optional filtering.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        frequency: Optional filter by backup frequency
        status_id: Optional filter by schedule status
        db: Database session dependency

    Returns:
        List of backup schedule configurations
    """
    return await backup_service.get_all_backup_schedules(
        db, skip, limit, frequency, status_id
    )


@router.get("/schedules/{schedule_id}", response_model=schemas.BackupScheduleDetailed)
async def get_backup_schedule(
    schedule_id: PyObjectId,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["backup_schedule:read"]),
):
    """
    Retrieve detailed information for a specific backup schedule.

    Args:
        schedule_id: Unique identifier of the backup schedule
        db: Database session dependency

    Returns:
        Detailed backup schedule information including related backups
    """
    return await backup_service.get_backup_schedule(db, schedule_id)


@router.patch("/schedules/{schedule_id}", response_model=schemas.BackupSchedulePublic)
async def update_backup_schedule(
    schedule_id: PyObjectId,
    schedule_data: schemas.BackupScheduleUpdate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["backup_schedule:update"]
    ),
):
    """
    Update an existing backup schedule configuration.

    Args:
        schedule_id: Unique identifier of the schedule to update
        schedule_data: Partial schedule data with fields to update
        db: Database session dependency
        current_user: Authenticated user with backup_schedule:update permission

    Returns:
        Updated backup schedule information
    """
    return await backup_service.update_backup_schedule(
        db, schedule_id, schedule_data, current_user
    )


@router.delete("/schedules/{schedule_id}", response_model=schemas.Msg)
async def delete_backup_schedule(
    schedule_id: PyObjectId,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["backup_schedule:delete"]),
):
    """
    Delete a backup schedule and its associated configurations.

    Args:
        schedule_id: Unique identifier of the schedule to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await backup_service.delete_backup_schedule(db, schedule_id)
    return schemas.Msg(message="Schedule deleted successfully")


@router.post("/manual", response_model=schemas.BackupPublic)
async def create_manual_backup(
    backup_data: schemas.BackupCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["backup:create"]),
):
    """
    Manually trigger an immediate full database backup.

    Args:
        backup_data: Backup configuration and settings
        db: Database session dependency
        current_user: Authenticated user with backup:create permission

    Returns:
        Details of the created backup operation
    """
    return await backup_service.create_manual_backup(db, backup_data, current_user)


@router.get("", response_model=List[schemas.BackupPublic])
async def get_all_backups(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    type: Optional[str] = Query(None),
    status_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["backup:read"]),
):
    """
    Retrieve all backup records with pagination and filtering options.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        type: Optional filter by backup type
        status_id: Optional filter by backup status
        db: Database session dependency

    Returns:
        List of backup records with basic information
    """
    return await backup_service.get_all_backups(db, skip, limit, type, status_id)


@router.get("/{backup_id}", response_model=schemas.BackupDetailed)
async def get_backup(
    backup_id: PyObjectId,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["backup:read"]),
):
    """
    Retrieve detailed information for a specific backup record.

    Args:
        backup_id: Unique identifier of the backup record
        db: Database session dependency

    Returns:
        Complete backup details including file information and metadata
    """
    return await backup_service.get_backup(db, backup_id)


@router.delete("/{backup_id}", response_model=schemas.Msg)
async def delete_backup(
    backup_id: PyObjectId,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["backup:delete"]),
):
    """
    Permanently delete a backup record and its associated files.

    Args:
        backup_id: Unique identifier of the backup to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await backup_service.delete_backup(db, backup_id)
    return schemas.Msg(message="Backup deleted successfully")


@router.post("/recover/{backup_id}", response_model=schemas.RecoveryLogPublic)
async def perform_recovery(
    backup_id: PyObjectId,
    recovery_data: schemas.RecoveryCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["recovery:create"]),
):
    """
    Perform full database recovery to a new database using a specific backup.

    Args:
        backup_id: Unique identifier of the backup to restore from
        recovery_data: Recovery configuration and options
        db: Database session dependency
        current_user: Authenticated user with recovery:create permission

    Returns:
        Recovery log entry with operation details
    """
    return await backup_service.perform_recovery(
        db, backup_id, recovery_data, current_user
    )


@router.get("/recover/logs", response_model=List[schemas.RecoveryLogPublic])
async def get_recovery_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["recovery:read"]),
):
    """
    Retrieve all system recovery logs with pagination and filtering.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        status_id: Optional filter by recovery status
        db: Database session dependency

    Returns:
        List of recovery log entries
    """
    return await backup_service.get_recovery_logs(db, skip, limit, status_id)


@router.get("/recover/logs/{log_id}", response_model=schemas.RecoveryLogDetailed)
async def get_recovery_log(
    log_id: PyObjectId,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["recovery:read"]),
):
    """
    Retrieve detailed information for a specific recovery log entry.

    Args:
        log_id: Unique identifier of the recovery log
        db: Database session dependency

    Returns:
        Complete recovery log details including execution details
    """
    return await backup_service.get_recovery_log(db, log_id)


@router.delete("/logs/{log_id}", response_model=schemas.Msg)
async def delete_recovery_log(
    log_id: PyObjectId,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["backup_log:delete"]),
):
    """
    Delete a recovery log entry from the system.

    Args:
        log_id: Unique identifier of the log entry to delete
        db: Database session dependency

    Returns:
        Success message confirming log deletion
    """
    await backup_service.delete_recovery_log(db, log_id)
    return schemas.Msg(message="Recovery log deleted successfully")
