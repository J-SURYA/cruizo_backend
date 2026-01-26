from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


from app.collections.enums import (
    BackupType,
    BackupFrequency,
    BackupLogMode,
)
from app.utils.objectid_utils import PyObjectId


class BackupScheduleBase(BaseModel):
    """
    Schema for backup schedule base fields.
    """

    name: str = Field(
        ..., max_length=255, description="Unique name for the backup schedule"
    )
    type: BackupType = Field(..., description="Type of backup schedule")
    frequency: BackupFrequency = Field(..., description="How often the backup runs")
    scheduled_time: datetime = Field(
        ..., description="Specific time when backup should run"
    )


class BackupCreate(BaseModel):
    """
    Schema for creating a backup operation.
    """

    name: str = Field(
        ..., max_length=255, description="Descriptive name for the backup"
    )
    type: BackupType = Field(..., description="Type of backup being created")
    remarks: Optional[str] = Field(
        None, description="Additional notes about the backup"
    )


class RecoveryCreate(BaseModel):
    """
    Schema for initiating a recovery operation.
    """

    name: str = Field(
        ..., max_length=255, description="Name for the new recovery database"
    )
    remarks: Optional[str] = Field(
        None, description="Additional notes about the recovery"
    )


class BackupScheduleCreate(BackupScheduleBase):
    """
    Schema for creating a new backup schedule.
    """

    status_id: int = Field(..., description="Initial status ID for the schedule")


class BackupManualCreate(BackupCreate):
    """
    Schema for manually triggering a backup operation.
    """

    pass



class BackupScheduleUpdate(BaseModel):
    """
    Schema for updating an existing backup schedule.
    """

    name: Optional[str] = Field(
        None, max_length=255, description="Updated schedule name"
    )
    frequency: Optional[BackupFrequency] = Field(
        None, description="Updated backup frequency"
    )
    scheduled_time: Optional[datetime] = Field(
        None, description="Updated scheduled time"
    )
    status_id: Optional[int] = Field(None, description="Updated status ID")


class BackupSchedulePublic(BackupScheduleBase):
    """
    Schema for backup schedule information.
    """

    id: PyObjectId = Field(..., description="Unique identifier for the schedule")
    status_id: int = Field(..., description="Current status of the schedule")
    effective_from: datetime = Field(
        ..., description="When the schedule becomes active"
    )
    last_modified_at: datetime = Field(..., description="Last modification timestamp")
    last_modified_by_id: str = Field(
        ..., description="ID of user who last modified the schedule"
    )

    class Config:
        from_attributes = True
        json_encoders = {PyObjectId: str}


class BackupScheduleDetailed(BackupSchedulePublic):
    """
    Schema for backup schedule including runtime information.
    """

    next_run: Optional[datetime] = Field(
        None, description="Next scheduled execution time"
    )
    last_backup: Optional[datetime] = Field(
        None, description="Timestamp of last successful backup"
    )


class BackupPublic(BaseModel):
    """
    Schema for backup operation information.
    """

    id: PyObjectId = Field(..., description="Unique identifier for the backup")
    name: str = Field(..., description="Backup operation name")
    mode: BackupLogMode = Field(..., description="Backup mode (manual/scheduled)")
    type: BackupType = Field(..., description="Type of backup performed")
    status_id: int = Field(..., description="Current status of the backup")
    size_in_mb: Decimal = Field(..., description="Size of backup file in megabytes")
    file_path: str = Field(..., description="Storage path of the backup file")
    created_at: datetime = Field(..., description="Backup creation timestamp")
    created_by: str = Field(..., description="User who initiated the backup")

    class Config:
        from_attributes = True
        json_encoders = {PyObjectId: str}


class BackupDetailed(BackupPublic):
    """
    Schema for backup operation including additional metadata.
    """

    remarks: Optional[str] = Field(None, description="Additional backup notes")
    schedule_name: Optional[str] = Field(
        None, description="Name of associated schedule if applicable"
    )


class RecoveryLogPublic(BaseModel):
    """
    Schema for recovery operation log.
    """

    id: PyObjectId = Field(..., description="Unique identifier for the recovery log")
    name: str = Field(..., description="Recovery operation name")
    backup_id: PyObjectId = Field(..., description="ID of backup used for recovery")
    status_id: int = Field(..., description="Current status of the recovery")
    recovered_at: datetime = Field(..., description="Recovery completion timestamp")
    recovered_by_id: str = Field(
        ..., description="ID of user who performed the recovery"
    )

    class Config:
        from_attributes = True
        json_encoders = {PyObjectId: str}


class RecoveryLogDetailed(RecoveryLogPublic):
    """
    Schema for recovery operation log including backup information.
    """

    remarks: Optional[str] = Field(None, description="Additional recovery notes")
    backup_name: str = Field(..., description="Name of the backup used")
    backup_file_path: str = Field(..., description="File path of the backup used")


class BackupFilterParams:
    """
    Schema for filtering backup operations.
    """

    def __init__(
        self,
        search: Optional[str] = None,
        type: Optional[BackupType] = None,
        status_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ):
        self.search = search
        self.type = type
        self.status_id = status_id
        self.date_from = date_from
        self.date_to = date_to


class ScheduleFilterParams:
    """
    Schema for filtering backup schedules.
    """

    def __init__(
        self,
        search: Optional[str] = None,
        frequency: Optional[BackupFrequency] = None,
        status_id: Optional[int] = None,
    ):
        self.search = search
        self.frequency = frequency
        self.status_id = status_id


class RecoveryFilterParams:
    """
    Schema for filtering recovery operations.
    """

    def __init__(
        self,
        search: Optional[str] = None,
        status_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ):
        self.search = search
        self.status_id = status_id
        self.date_from = date_from
        self.date_to = date_to


class PaginatedBackupResponse(BaseModel):
    """
    Schema for paginated backup response.
    """

    total: int = Field(..., description="Total number of backup records")
    items: List[BackupPublic] = Field(..., description="List of backup records")


class PaginatedScheduleResponse(BaseModel):
    """
    Schema for paginated schedule response.
    """

    total: int = Field(..., description="Total number of schedule records")
    items: List[BackupSchedulePublic] = Field(
        ..., description="List of schedule records"
    )


class PaginatedRecoveryResponse(BaseModel):
    """
    Schema for paginated recovery response.
    """

    total: int = Field(..., description="Total number of recovery records")
    items: List[RecoveryLogPublic] = Field(..., description="List of recovery records")
