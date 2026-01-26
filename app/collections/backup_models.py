from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


from app.utils.objectid_utils import PyObjectId


class BaseMongoModel(BaseModel):
    """
    Base model for all MongoDB documents with ObjectId support.
    """

    id: PyObjectId = Field(alias="_id", default_factory=PyObjectId)

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            PyObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        }


class BackupSchedule(BaseMongoModel):
    """
    Table representing backup schedules for PostgreSQL databases.
    """

    name: str = Field(..., max_length=255)
    type: str
    frequency: str
    scheduled_time: datetime
    status_id: int = Field(..., description="References PostgreSQL status.id")
    effective_from: datetime
    last_modified_at: datetime
    last_modified_by_id: str = Field(..., description="References PostgreSQL users.id")


class BackupLog(BaseMongoModel):
    """
    Table for logging backup operations performed on PostgreSQL databases.
    """

    name: str = Field(..., max_length=255)
    mode: str
    schedule_id: Optional[PyObjectId] = Field(
        None, description="References backup_schedules._id (for scheduled backups)"
    )
    type: str
    status_id: int = Field(..., description="References PostgreSQL status.id")
    size_in_mb: float
    file_path: str = Field(..., max_length=1024)
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(..., description="References PostgreSQL users.id")


class RecoveryLog(BaseMongoModel):
    """
    Table for logging recovery operations performed using backups.
    """

    name: str = Field(..., max_length=255)
    backup_id: PyObjectId = Field(..., description="References backup_logs._id")
    status_id: int = Field(..., description="References PostgreSQL status.id")
    remarks: Optional[str] = None
    recovered_at: datetime = Field(default_factory=datetime.now)
    recovered_by_id: str = Field(..., description="References PostgreSQL users.id")
