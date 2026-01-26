from typing import List, Optional, Dict, Any
from bson import ObjectId


from app.database.session_mongo import mongo_manager
from app.collections.backup_models import BackupSchedule, BackupLog, RecoveryLog
from app.utils.objectid_utils import PyObjectId


class BackupCRUD:
    """
    Class for managing backup and recovery operations in MongoDB.
    """
    async def create_backup_schedule(
        self, schedule_data: Dict[str, Any]
    ) -> BackupSchedule:
        """
        Create a new backup schedule configuration.

        Args:
            schedule_data: Backup schedule configuration data

        Returns:
            Newly created BackupSchedule object
        """
        result = await mongo_manager.db.backup_schedules.insert_one(schedule_data)
        created_schedule = await mongo_manager.db.backup_schedules.find_one(
            {"_id": result.inserted_id}
        )
        return BackupSchedule(**created_schedule)


    async def get_backup_schedule(
        self, schedule_id: PyObjectId
    ) -> Optional[BackupSchedule]:
        """
        Retrieve a backup schedule by its unique identifier.

        Args:
            schedule_id: Unique identifier of the backup schedule

        Returns:
            BackupSchedule object if found, None otherwise
        """
        schedule = await mongo_manager.db.backup_schedules.find_one(
            {"_id": ObjectId(schedule_id)}
        )
        return BackupSchedule(**schedule) if schedule else None


    async def get_all_backup_schedules(
        self,
        skip: int = 0,
        limit: int = 100,
        frequency: Optional[str] = None,
        status_id: Optional[int] = None,
    ) -> List[BackupSchedule]:
        """
        Retrieve all backup schedules with optional filtering.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            frequency: Optional filter by backup frequency
            status_id: Optional filter by schedule status

        Returns:
            List of BackupSchedule objects matching the criteria
        """
        query = {}
        if frequency:
            query["frequency"] = frequency
        if status_id:
            query["status_id"] = status_id

        cursor = mongo_manager.db.backup_schedules.find(query).skip(skip).limit(limit)
        schedules = await cursor.to_list(length=limit)
        return [BackupSchedule(**schedule) for schedule in schedules]

    async def update_backup_schedule(
        self, schedule_id: PyObjectId, update_data: Dict[str, Any]
    ) -> Optional[BackupSchedule]:
        """
        Update an existing backup schedule configuration.

        Args:
            schedule_id: Unique identifier of the schedule to update
            update_data: Dictionary containing fields to update

        Returns:
            Updated BackupSchedule object if found, None otherwise
        """
        await mongo_manager.db.backup_schedules.update_one(
            {"_id": ObjectId(schedule_id)}, {"$set": update_data}
        )
        return await self.get_backup_schedule(schedule_id)


    async def delete_backup_schedule(self, schedule_id: PyObjectId) -> bool:
        """
        Delete a backup schedule from the system.

        Args:
            schedule_id: Unique identifier of the schedule to delete

        Returns:
            True if schedule was deleted, False if not found
        """
        result = await mongo_manager.db.backup_schedules.delete_one(
            {"_id": ObjectId(schedule_id)}
        )
        return result.deleted_count > 0


    async def create_backup_log(self, log_data: Dict[str, Any]) -> BackupLog:
        """
        Create a new backup log entry for tracking backup operations.

        Args:
            log_data: Backup operation details and metadata

        Returns:
            Newly created BackupLog object
        """
        result = await mongo_manager.db.backup_logs.insert_one(log_data)
        created_log = await mongo_manager.db.backup_logs.find_one(
            {"_id": result.inserted_id}
        )
        return BackupLog(**created_log)


    async def get_backup_log(self, backup_id: PyObjectId) -> Optional[BackupLog]:
        """
        Retrieve a backup log entry by its unique identifier.

        Args:
            backup_id: Unique identifier of the backup log

        Returns:
            BackupLog object if found, None otherwise
        """
        backup_log = await mongo_manager.db.backup_logs.find_one(
            {"_id": ObjectId(backup_id)}
        )
        return BackupLog(**backup_log) if backup_log else None


    async def get_all_backup_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        type: Optional[str] = None,
        status_id: Optional[int] = None,
    ) -> List[BackupLog]:
        """
        Retrieve all backup log entries with optional filtering.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            type: Optional filter by backup type
            status_id: Optional filter by backup status

        Returns:
            List of BackupLog objects matching the criteria, sorted by creation date
        """
        query = {}
        if type:
            query["type"] = type
        if status_id:
            query["status_id"] = status_id

        cursor = (
            mongo_manager.db.backup_logs.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        logs = await cursor.to_list(length=limit)
        return [BackupLog(**log) for log in logs]


    async def delete_backup_log(self, backup_id: PyObjectId) -> bool:
        """
        Delete a backup log entry from the system.

        Args:
            backup_id: Unique identifier of the backup log to delete

        Returns:
            True if backup log was deleted, False if not found
        """
        result = await mongo_manager.db.backup_logs.delete_one(
            {"_id": ObjectId(backup_id)}
        )
        return result.deleted_count > 0


    async def create_recovery_log(self, log_data: Dict[str, Any]) -> RecoveryLog:
        """
        Create a new recovery log entry for tracking recovery operations.

        Args:
            log_data: Recovery operation details and metadata

        Returns:
            Newly created RecoveryLog object
        """
        result = await mongo_manager.db.recovery_logs.insert_one(log_data)
        created_log = await mongo_manager.db.recovery_logs.find_one(
            {"_id": result.inserted_id}
        )
        return RecoveryLog(**created_log)


    async def get_recovery_log(self, log_id: PyObjectId) -> Optional[RecoveryLog]:
        """
        Retrieve a recovery log entry by its unique identifier.

        Args:
            log_id: Unique identifier of the recovery log

        Returns:
            RecoveryLog object if found, None otherwise
        """
        recovery_log = await mongo_manager.db.recovery_logs.find_one(
            {"_id": ObjectId(log_id)}
        )
        return RecoveryLog(**recovery_log) if recovery_log else None


    async def get_all_recovery_logs(
        self, skip: int = 0, limit: int = 100, status_id: Optional[int] = None
    ) -> List[RecoveryLog]:
        """
        Retrieve all recovery log entries with optional filtering.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            status_id: Optional filter by recovery status

        Returns:
            List of RecoveryLog objects matching the criteria, sorted by recovery date
        """
        query = {}
        if status_id:
            query["status_id"] = status_id

        cursor = (
            mongo_manager.db.recovery_logs.find(query)
            .sort("recovered_at", -1)
            .skip(skip)
            .limit(limit)
        )
        logs = await cursor.to_list(length=limit)
        return [RecoveryLog(**log) for log in logs]


    async def delete_recovery_log(self, log_id: PyObjectId) -> bool:
        """
        Delete a recovery log entry from the system.

        Args:
            log_id: Unique identifier of the recovery log to delete

        Returns:
            True if recovery log was deleted, False if not found
        """
        result = await mongo_manager.db.recovery_logs.delete_one(
            {"_id": ObjectId(log_id)}
        )
        return result.deleted_count > 0


backup_crud = BackupCRUD()
