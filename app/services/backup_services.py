import os, tempfile, logging, subprocess
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.config import settings
from app import models, schemas
from app.crud import backup_crud
from app.collections.enums import (
    BackupType,
    BackupLogMode,
)
from app.utils.objectid_utils import PyObjectId
from app.utils.exception_utils import (
    NotFoundException,
    BadRequestException,
    ServerErrorException,
)
from app.core.dependencies import get_container_client


logger = logging.getLogger(__name__)


class BackupService:
    """
    Service class handling full database backup and recovery operations including manual backups, scheduled backups, and recovery processes to new databases.
    """
    def __init__(self):
        """
        Initialize backup service with PostgreSQL paths.
        """
        self.postgres_bin_paths = [
            r"C:\Program Files\PostgreSQL\17\bin",
            r"C:\Program Files\PostgreSQL\16\bin",
            r"C:\Program Files\PostgreSQL\15\bin",
            r"C:\Program Files\PostgreSQL\14\bin",
            r"C:\Program Files\PostgreSQL\13\bin",
        ]


    def _find_postgres_binary(self, binary_name: str) -> str:
        """
        Find PostgreSQL binary in common installation paths or system PATH.
        
        Args:
            binary_name: Name of the PostgreSQL binary (e.g., 'pg_dump', 'pg_restore')
        
        Returns:
            Full path to the PostgreSQL binary
        
        Raises:
            BadRequestException: If binary is not found in any location
        """
        import shutil

        path_result = shutil.which(binary_name)
        if path_result:
            return path_result

        for bin_path in self.postgres_bin_paths:
            binary_path = os.path.join(bin_path, f"{binary_name}.exe")
            if os.path.exists(binary_path):
                return binary_path

        raise BadRequestException(
            f"{binary_name} not found. Please ensure PostgreSQL is installed and "
            f"either add it to your PATH or update the postgres_bin_paths in backup_services.py. "
            f"Common locations: {', '.join(self.postgres_bin_paths)}"
        )


    async def create_manual_backup(
        self,
        db: AsyncSession,
        backup_data: schemas.BackupCreate,
        current_user: models.User,
    ) -> Dict[str, Any]:
        """
        Create a manual full database backup and upload to cloud storage.
        
        Args:
            db: Database session
            backup_data: Backup creation parameters including name
            current_user: User initiating the backup
        
        Returns:
            Backup log details including ID, status, and file information
        
        Raises:
            ServerErrorException: If backup generation or upload fails
        """
        try:
            backup_file_path = await self._generate_full_backup_file()

            blob_name = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{backup_data.name}.sql"
            file_size = await self._upload_to_blob(backup_file_path, blob_name)

            backup_log_data = {
                "name": backup_data.name,
                "mode": BackupLogMode.MANUAL.value,
                "type": backup_data.type.value,
                "status_id": 1,
                "size_in_mb": float(round(file_size / (1024 * 1024), 2)),
                "file_path": blob_name,
                "remarks": backup_data.remarks,
                "created_by": (str(current_user.id) if current_user else "U0001"),
                "created_at": datetime.now(),
            }

            backup_log = await backup_crud.create_backup_log(backup_log_data)

            if os.path.exists(backup_file_path):
                os.unlink(backup_file_path)

            return {
                "id": backup_log.id,
                "name": backup_log.name,
                "mode": BackupLogMode.MANUAL,
                "type": backup_data.type,
                "status_id": backup_log.status_id,
                "size_in_mb": backup_log.size_in_mb,
                "file_path": backup_log.file_path,
                "remarks": backup_log.remarks,
                "created_at": backup_log.created_at,
                "created_by": backup_log.created_by,
            }

        except Exception as e:
            logger.error(f"Full backup creation failed: {str(e)}", exc_info=True)
            backup_log_data = {
                "name": backup_data.name,
                "mode": BackupLogMode.MANUAL.value,
                "type": backup_data.type.value,
                "status_id": 2,
                "size_in_mb": 0.0,
                "file_path": "",
                "remarks": f"Full backup failed: {str(e)}",
                "created_by": (str(current_user.id) if current_user else "U0001"),
                "created_at": datetime.now(),
            }
            backup_log = await backup_crud.create_backup_log(backup_log_data)

            return {
                "id": backup_log.id,
                "name": backup_log.name,
                "mode": BackupLogMode.MANUAL,
                "type": backup_data.type,
                "status_id": backup_log.status_id,
                "size_in_mb": backup_log.size_in_mb,
                "file_path": backup_log.file_path,
                "remarks": backup_log.remarks,
                "created_at": backup_log.created_at,
                "created_by": backup_log.created_by,
            }


    async def create_scheduled_backup(
        self,
        db: AsyncSession,
        schedule_name: str,
        backup_type: BackupType,
        remarks: str = "",
    ) -> Dict[str, Any]:
        """
        Create a full database backup from a scheduled task using system user.
        
        Args:
            db: Database session
            schedule_name: Name of the backup schedule
            backup_type: Type of backup schedule
            remarks: Optional remarks for the backup
        
        Returns:
            Backup log details including ID, status, and file information
        
        Raises:
            ServerErrorException: If backup generation or upload fails
        """
        try:
            backup_file_path = await self._generate_full_backup_file()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"scheduled_{timestamp}_{schedule_name}.sql"
            file_size = await self._upload_to_blob(backup_file_path, blob_name)

            backup_log_data = {
                "name": f"Scheduled_{schedule_name}_{timestamp}",
                "mode": BackupLogMode.SCHEDULE.value,
                "type": backup_type.value,
                "status_id": 1,
                "size_in_mb": float(round(file_size / (1024 * 1024), 2)),
                "file_path": blob_name,
                "remarks": remarks,
                "created_by": "U0001",
                "created_at": datetime.now(),
            }

            backup_log = await backup_crud.create_backup_log(backup_log_data)

            if os.path.exists(backup_file_path):
                os.unlink(backup_file_path)

            return {
                "id": backup_log.id,
                "name": backup_log.name,
                "mode": BackupLogMode.SCHEDULE,
                "type": backup_type,
                "status_id": backup_log.status_id,
                "size_in_mb": backup_log.size_in_mb,
                "file_path": backup_log.file_path,
                "remarks": backup_log.remarks,
                "created_at": backup_log.created_at,
                "created_by": backup_log.created_by,
            }

        except Exception as e:
            logger.error(
                f"Scheduled full backup creation failed: {str(e)}", exc_info=True
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_log_data = {
                "name": f"Scheduled_{schedule_name}_{timestamp}",
                "mode": BackupLogMode.SCHEDULE.value,
                "type": backup_type.value,
                "status_id": 2,
                "size_in_mb": 0.0,
                "file_path": "",
                "remarks": f"Scheduled full backup failed: {str(e)}",
                "created_by": "U0001",
                "created_at": datetime.now(),
            }
            backup_log = await backup_crud.create_backup_log(backup_log_data)

            return {
                "id": backup_log.id,
                "name": backup_log.name,
                "mode": BackupLogMode.SCHEDULE,
                "type": backup_type,
                "status_id": backup_log.status_id,
                "size_in_mb": backup_log.size_in_mb,
                "file_path": backup_log.file_path,
                "remarks": backup_log.remarks,
                "created_at": backup_log.created_at,
                "created_by": backup_log.created_by,
            }


    async def _generate_full_backup_file(self) -> str:
        """
        Generate full PostgreSQL database backup file using pg_dump without database-specific commands.
        
        Returns:
            Path to the generated backup file
        
        Raises:
            ServerErrorException: If pg_dump execution fails or times out
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sql")
        temp_file.close()

        logger.info("Starting full database backup")
        logger.info(
            f"PostgreSQL connection: host={settings.POSTGRES_HOST}, db={settings.POSTGRES_DB}, user={settings.POSTGRES_USER}"
        )

        try:
            pg_dump_path = self._find_postgres_binary("pg_dump")
            logger.info(f"Found pg_dump at: {pg_dump_path}")

            env = os.environ.copy()
            env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

            cmd_args = [
                pg_dump_path,
                f"--host={settings.POSTGRES_HOST}",
                f"--port={settings.POSTGRES_PORT}",
                f"--username={settings.POSTGRES_USER}",
                f"--dbname={settings.POSTGRES_DB}",
                f"--file={temp_file.name}",
                "--verbose",
                "--no-password",
                "--no-owner",
                "--no-privileges",
                "--format=plain",
            ]

            logger.info(f"Executing pg_dump command: {' '.join(cmd_args)}")

            process = subprocess.Popen(
                cmd_args,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate(timeout=600)

            if process.returncode != 0:
                logger.error(f"pg_dump failed with return code: {process.returncode}")
                logger.error(f"pg_dump stderr: {stderr}")
                logger.error(f"pg_dump stdout: {stdout}")

                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)

                raise ServerErrorException(
                    f"Full database backup failed: {stderr or 'Unknown error'}"
                )

            if not os.path.exists(temp_file.name):
                raise ServerErrorException("Backup file was not created")

            file_size = os.path.getsize(temp_file.name)
            if file_size == 0:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
                raise ServerErrorException("Backup file was created but is empty")

            logger.info(
                f"Full backup file created successfully: {temp_file.name}, size: {file_size} bytes"
            )
            return temp_file.name

        except subprocess.TimeoutExpired:
            logger.error("pg_dump timed out after 10 minutes")
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise ServerErrorException(
                "Full database backup timed out after 10 minutes"
            )
        except Exception as e:
            logger.error(f"pg_dump execution failed: {str(e)}", exc_info=True)
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise ServerErrorException(
                f"Full database backup execution failed: {str(e)}"
            )


    async def _upload_to_blob(self, file_path: str, blob_name: str) -> int:
        """
        Upload backup file to Azure Blob Storage.
        
        Args:
            file_path: Local path to the backup file
            blob_name: Name for the blob in Azure storage
        
        Returns:
            Size of the uploaded file in bytes
        
        Raises:
            ServerErrorException: If upload to Azure Blob Storage fails
        """
        try:
            logger.info(f"Uploading backup file to Azure Blob: {blob_name}")

            container_client = await get_container_client(settings.BACKUP_CONTAINER_NAME)
            with open(file_path, "rb") as data:
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(data, overwrite=True)

            file_size = os.path.getsize(file_path)
            logger.info(
                f"Backup uploaded successfully to Azure Blob. Size: {file_size} bytes"
            )
            return file_size

        except Exception as e:
            logger.error(f"Blob upload failed: {e}", exc_info=True)
            raise ServerErrorException(
                f"Failed to upload backup to cloud storage: {str(e)}"
            )


    async def get_backup(
        self, db: AsyncSession, backup_id: PyObjectId
    ) -> Dict[str, Any]:
        """
        Get backup details by ID from MongoDB.
        
        Args:
            db: Database session
            backup_id: MongoDB ObjectId of the backup
        
        Returns:
            Backup details with enum values converted from strings
        
        Raises:
            NotFoundException: If backup with given ID is not found
        """
        backup_log = await backup_crud.get_backup_log(backup_id)
        if not backup_log:
            raise NotFoundException("Backup not found")

        return {
            "id": backup_log.id,
            "name": backup_log.name,
            "mode": BackupLogMode(backup_log.mode),
            "type": BackupType(backup_log.type),
            "status_id": backup_log.status_id,
            "size_in_mb": backup_log.size_in_mb,
            "file_path": backup_log.file_path,
            "remarks": backup_log.remarks,
            "created_at": backup_log.created_at,
            "created_by": backup_log.created_by,
        }


    async def get_all_backups(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        type: Optional[str] = None,
        status_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all backups with optional filtering by type and status.
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            type: Optional backup type filter
            status_id: Optional status ID filter
        
        Returns:
            List of backup details with enum conversions
        
        Raises:
            ServerErrorException: If retrieval from database fails
        """
        try:
            backup_logs = await backup_crud.get_all_backup_logs(
                skip, limit, type, status_id
            )

            results = []
            for log in backup_logs:
                results.append(
                    {
                        "id": log.id,
                        "name": log.name,
                        "mode": BackupLogMode(log.mode),
                        "type": BackupType(log.type),
                        "status_id": log.status_id,
                        "size_in_mb": log.size_in_mb,
                        "file_path": log.file_path,
                        "remarks": log.remarks,
                        "created_at": log.created_at,
                        "created_by": log.created_by,
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get backups: {e}")
            raise ServerErrorException("Failed to retrieve backup list")


    async def delete_backup(self, db: AsyncSession, backup_id: PyObjectId) -> None:
        """
        Delete backup from both MongoDB and Azure Blob Storage.
        
        Args:
            db: Database session
            backup_id: MongoDB ObjectId of the backup to delete
        
        Raises:
            NotFoundException: If backup with given ID is not found
            ServerErrorException: If deletion from storage or database fails
        """
        backup_log = await backup_crud.get_backup_log(backup_id)
        if not backup_log:
            raise NotFoundException("Backup not found")

        try:
            if backup_log.file_path:
                container_client = await get_container_client(settings.BACKUP_CONTAINER_NAME)
                blob_client = container_client.get_blob_client(
                    backup_log.file_path
                )
                blob_client.delete_blob()
                logger.info(
                    f"Deleted backup file from Azure Blob: {backup_log.file_path}"
                )

            success = await backup_crud.delete_backup_log(backup_id)
            if not success:
                raise ServerErrorException("Failed to delete backup from database")

            logger.info(f"Deleted backup log from database: {backup_id}")

        except Exception as e:
            logger.error(f"Backup deletion failed: {e}")
            raise ServerErrorException(f"Failed to delete backup: {str(e)}")


    async def create_backup_schedule(
        self,
        db: AsyncSession,
        schedule_data: schemas.BackupScheduleCreate,
        current_user: models.User,
    ) -> Dict[str, Any]:
        """
        Create a new backup schedule for automated full backups.
        
        Args:
            db: Database session
            schedule_data: Backup schedule creation parameters
            current_user: User creating the schedule
        
        Returns:
            Created backup schedule details
        
        Raises:
            ServerErrorException: If schedule creation fails
        """
        try:
            schedule_dict = schedule_data.dict()
            schedule_dict.update(
                {
                    "status_id": 1,
                    "last_modified_at": datetime.now(),
                    "last_modified_by_id": str(current_user.id),
                    "type": schedule_data.type.value,
                    "frequency": schedule_data.frequency.value,
                    "effective_from": datetime.now(),
                }
            )

            backup_schedule = await backup_crud.create_backup_schedule(schedule_dict)

            return {
                "id": backup_schedule.id,
                "name": backup_schedule.name,
                "type": schedule_data.type,
                "frequency": schedule_data.frequency,
                "scheduled_time": backup_schedule.scheduled_time,
                "status_id": backup_schedule.status_id,
                "effective_from": backup_schedule.effective_from,
                "last_modified_at": backup_schedule.last_modified_at,
                "last_modified_by_id": backup_schedule.last_modified_by_id,
            }

        except Exception as e:
            logger.error(f"Failed to create backup schedule: {e}")
            raise ServerErrorException(f"Failed to create backup schedule: {str(e)}")


    async def get_backup_schedule(
        self, db: AsyncSession, schedule_id: PyObjectId
    ) -> Dict[str, Any]:
        """
        Get backup schedule details by ID.
        
        Args:
            db: Database session
            schedule_id: MongoDB ObjectId of the schedule
        
        Returns:
            Backup schedule details with enum conversions
        
        Raises:
            NotFoundException: If schedule with given ID is not found
        """
        schedule = await backup_crud.get_backup_schedule(schedule_id)
        if not schedule:
            raise NotFoundException("Backup schedule not found")

        return {
            "id": schedule.id,
            "name": schedule.name,
            "type": BackupType(schedule.type),
            "frequency": schedule.frequency,
            "scheduled_time": schedule.scheduled_time,
            "status_id": schedule.status_id,
            "effective_from": schedule.effective_from,
            "last_modified_at": schedule.last_modified_at,
            "last_modified_by_id": schedule.last_modified_by_id,
        }


    async def get_all_backup_schedules(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        frequency: Optional[str] = None,
        status_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all backup schedules with optional filtering.
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            frequency: Optional frequency filter
            status_id: Optional status ID filter
        
        Returns:
            List of backup schedules with enum conversions
        
        Raises:
            ServerErrorException: If retrieval from database fails
        """
        try:
            schedules = await backup_crud.get_all_backup_schedules(
                skip, limit, frequency, status_id
            )

            results = []
            for schedule in schedules:
                results.append(
                    {
                        "id": schedule.id,
                        "name": schedule.name,
                        "type": BackupType(schedule.type),
                        "frequency": schedule.frequency,
                        "scheduled_time": schedule.scheduled_time,
                        "status_id": schedule.status_id,
                        "effective_from": schedule.effective_from,
                        "last_modified_at": schedule.last_modified_at,
                        "last_modified_by_id": schedule.last_modified_by_id,
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get backup schedules: {e}")
            raise ServerErrorException("Failed to retrieve backup schedules")


    async def update_backup_schedule(
        self,
        db: AsyncSession,
        schedule_id: PyObjectId,
        update_data: schemas.BackupScheduleUpdate,
        current_user: models.User,
    ) -> Dict[str, Any]:
        """
        Update an existing backup schedule.
        
        Args:
            db: Database session
            schedule_id: MongoDB ObjectId of the schedule to update
            update_data: Updated schedule parameters
            current_user: User updating the schedule
        
        Returns:
            Updated backup schedule details
        
        Raises:
            NotFoundException: If schedule with given ID is not found
            ServerErrorException: If update operation fails
        """
        try:
            update_dict = update_data.dict(exclude_unset=True)
            update_dict.update(
                {
                    "last_modified_at": datetime.now(),
                    "last_modified_by_id": str(current_user.id),
                }
            )

            if "type" in update_dict and hasattr(update_dict["type"], "value"):
                update_dict["type"] = update_dict["type"].value
            if "frequency" in update_dict and hasattr(
                update_dict["frequency"], "value"
            ):
                update_dict["frequency"] = update_dict["frequency"].value

            schedule = await backup_crud.update_backup_schedule(
                schedule_id, update_dict
            )
            if not schedule:
                raise NotFoundException("Backup schedule not found")

            return {
                "id": schedule.id,
                "name": schedule.name,
                "type": BackupType(schedule.type),
                "frequency": schedule.frequency,
                "scheduled_time": schedule.scheduled_time,
                "status_id": schedule.status_id,
                "effective_from": schedule.effective_from,
                "last_modified_at": schedule.last_modified_at,
                "last_modified_by_id": schedule.last_modified_by_id,
            }

        except Exception as e:
            logger.error(f"Failed to update backup schedule: {e}")
            raise ServerErrorException(f"Failed to update backup schedule: {str(e)}")


    async def delete_backup_schedule(
        self, db: AsyncSession, schedule_id: PyObjectId
    ) -> None:
        """
        Delete a backup schedule.
        
        Args:
            db: Database session
            schedule_id: MongoDB ObjectId of the schedule to delete
        
        Raises:
            NotFoundException: If schedule with given ID is not found
        """
        success = await backup_crud.delete_backup_schedule(schedule_id)
        if not success:
            raise NotFoundException("Backup schedule not found")


    async def _download_from_blob(self, blob_name: str) -> str:
        """
        Download file from Azure Blob Storage to local temporary file.
        
        Args:
            blob_name: Name of the blob to download
        
        Returns:
            Path to the downloaded local file
        
        Raises:
            ServerErrorException: If download from Azure Blob Storage fails
        """
        try:
            container_client = await get_container_client(settings.BACKUP_CONTAINER_NAME)
            blob_client = container_client.get_blob_client(blob_name)

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sql")
            temp_file.close()

            with open(temp_file.name, "wb") as download_file:
                download_stream = blob_client.download_blob()
                download_file.write(download_stream.readall())

            return temp_file.name

        except Exception as e:
            logger.error(f"Blob download failed: {e}")
            raise ServerErrorException(f"Failed to download backup file: {str(e)}")


    async def perform_recovery(
        self,
        db: AsyncSession,
        backup_id: PyObjectId,
        recovery_data: schemas.RecoveryCreate,
        current_user: models.User,
    ) -> Dict[str, Any]:
        """
        Perform full database recovery to a new database from a backup file.
        
        Args:
            db: Database session
            backup_id: MongoDB ObjectId of the backup to recover from
            recovery_data: Recovery parameters including new database name
            current_user: User performing the recovery
        
        Returns:
            Recovery log details
        
        Raises:
            NotFoundException: If backup is not found
            BadRequestException: If backup is failed or file path is missing
            ServerErrorException: If recovery process fails
        """
        try:
            backup_log = await backup_crud.get_backup_log(backup_id)
            if not backup_log:
                raise NotFoundException("Backup not found")

            if backup_log.status_id != 1:
                raise BadRequestException("Cannot recover from failed backup")

            if not backup_log.file_path:
                raise BadRequestException("Backup file path is missing")

            logger.info(f"Starting full recovery for backup: {backup_id}")

            local_file_path = await self._download_from_blob(backup_log.file_path)

            try:
                new_db_name = (
                    recovery_data.name
                    or f"recovery_{backup_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )

                await self._perform_full_recovery_to_new_db(
                    local_file_path, new_db_name
                )

                recovery_log_data = {
                    "name": recovery_data.name or f"Recovery_{backup_log.name}",
                    "backup_id": backup_id,
                    "status_id": 1,
                    "remarks": f"Recovered to new database: {new_db_name}. {recovery_data.remarks or ''}",
                    "recovered_by_id": str(current_user.id),
                    "recovered_at": datetime.now(),
                }

                recovery_log = await backup_crud.create_recovery_log(recovery_log_data)

                logger.info(
                    f"Successfully completed recovery {recovery_log.id} to database: {new_db_name}"
                )

                return {
                    "id": recovery_log.id,
                    "name": recovery_log.name,
                    "backup_id": recovery_log.backup_id,
                    "status_id": recovery_log.status_id,
                    "remarks": recovery_log.remarks,
                    "recovered_at": recovery_log.recovered_at,
                    "recovered_by_id": recovery_log.recovered_by_id,
                }

            finally:
                if os.path.exists(local_file_path):
                    os.unlink(local_file_path)

        except Exception as e:
            logger.error(f"Full recovery failed: {e}", exc_info=True)
            recovery_log_data = {
                "name": recovery_data.name or f"Recovery_attempt_{backup_id}",
                "backup_id": backup_id,
                "status_id": 2,
                "remarks": f"Full recovery failed: {str(e)}",
                "recovered_by_id": str(current_user.id),
                "recovered_at": datetime.now(),
            }
            await backup_crud.create_recovery_log(recovery_log_data)
            raise ServerErrorException(f"Full recovery failed: {str(e)}")


    async def _perform_full_recovery_to_new_db(self, file_path: str, new_db_name: str):
        """
        Perform full database recovery to a new database.
        
        Args:
            file_path: Path to the backup SQL file
            new_db_name: Name of the new database to create
        
        Raises:
            ServerErrorException: If recovery process fails or times out
        """
        try:
            psql_path = self._find_postgres_binary("psql")
            env = os.environ.copy()
            env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

            check_db_cmd = [
                psql_path,
                f"--host={settings.POSTGRES_HOST}",
                f"--port={settings.POSTGRES_PORT}",
                f"--username={settings.POSTGRES_USER}",
                "--dbname=postgres",
                "--command",
                f"SELECT 1 FROM pg_database WHERE datname = '{new_db_name}';",
                "--no-password",
                "-t",
            ]

            check_process = subprocess.Popen(
                check_db_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = check_process.communicate(timeout=30)

            if stdout.strip() == "1":
                logger.info(f"Database {new_db_name} already exists, dropping it first")

                terminate_cmd = [
                    psql_path,
                    f"--host={settings.POSTGRES_HOST}",
                    f"--port={settings.POSTGRES_PORT}",
                    f"--username={settings.POSTGRES_USER}",
                    "--dbname=postgres",
                    "--command",
                    f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{new_db_name}'
                    AND pid <> pg_backend_pid();
                    """,
                    "--no-password",
                ]
                subprocess.run(terminate_cmd, env=env, timeout=30)

                drop_cmd = [
                    psql_path,
                    f"--host={settings.POSTGRES_HOST}",
                    f"--port={settings.POSTGRES_PORT}",
                    f"--username={settings.POSTGRES_USER}",
                    "--dbname=postgres",
                    "--command",
                    f"DROP DATABASE {new_db_name};",
                    "--no-password",
                ]
                drop_process = subprocess.Popen(
                    drop_cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                drop_process.communicate(timeout=30)

            create_db_cmd = [
                psql_path,
                f"--host={settings.POSTGRES_HOST}",
                f"--port={settings.POSTGRES_PORT}",
                f"--username={settings.POSTGRES_USER}",
                "--dbname=postgres",
                "--command",
                f"CREATE DATABASE {new_db_name};",
                "--no-password",
            ]

            logger.info(f"Creating new database: {new_db_name}")
            create_process = subprocess.Popen(
                create_db_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = create_process.communicate(timeout=60)

            if create_process.returncode != 0:
                logger.error(f"Database creation failed: {stderr}")
                raise ServerErrorException(f"Failed to create new database: {stderr}")

            restore_cmd = [
                psql_path,
                f"--host={settings.POSTGRES_HOST}",
                f"--port={settings.POSTGRES_PORT}",
                f"--username={settings.POSTGRES_USER}",
                f"--dbname={new_db_name}",
                f"--file={file_path}",
                "--quiet",
                "--no-password",
            ]

            logger.info(f"Restoring backup to new database: {new_db_name}")
            start_time = datetime.now()

            process = subprocess.Popen(
                restore_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate(timeout=900)

            recovery_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Full recovery completed in {recovery_time:.2f} seconds")

            if process.returncode != 0:
                logger.error(f"Full recovery failed: {stderr}")
                drop_failed_cmd = [
                    psql_path,
                    f"--host={settings.POSTGRES_HOST}",
                    f"--port={settings.POSTGRES_PORT}",
                    f"--username={settings.POSTGRES_USER}",
                    "--dbname=postgres",
                    "--command",
                    f"DROP DATABASE IF EXISTS {new_db_name};",
                    "--no-password",
                ]
                subprocess.run(drop_failed_cmd, env=env, timeout=60)
                raise ServerErrorException(f"Full database recovery failed: {stderr}")

            logger.info(f"Successfully created and restored database: {new_db_name}")

        except subprocess.TimeoutExpired:
            try:
                drop_timeout_cmd = [
                    psql_path,
                    f"--host={settings.POSTGRES_HOST}",
                    f"--port={settings.POSTGRES_PORT}",
                    f"--username={settings.POSTGRES_USER}",
                    "--dbname=postgres",
                    "--command",
                    f"DROP DATABASE IF EXISTS {new_db_name};",
                    "--no-password",
                ]
                subprocess.run(drop_timeout_cmd, env=env, timeout=30)
            except:
                pass
            raise ServerErrorException("Full recovery timed out after 15 minutes")
        except Exception as e:
            try:
                drop_error_cmd = [
                    psql_path,
                    f"--host={settings.POSTGRES_HOST}",
                    f"--port={settings.POSTGRES_PORT}",
                    f"--username={settings.POSTGRES_USER}",
                    "--dbname=postgres",
                    "--command",
                    f"DROP DATABASE IF EXISTS {new_db_name};",
                    "--no-password",
                ]
                subprocess.run(drop_error_cmd, env=env, timeout=30)
            except:
                pass
            raise ServerErrorException(f"Full recovery execution failed: {str(e)}")


    async def get_recovery_logs(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all recovery logs with optional status filtering.
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            status_id: Optional status ID filter
        
        Returns:
            List of recovery logs with enum conversions
        
        Raises:
            ServerErrorException: If retrieval from database fails
        """
        try:
            recovery_logs = await backup_crud.get_all_recovery_logs(
                skip, limit, status_id
            )

            results = []
            for log in recovery_logs:
                results.append(
                    {
                        "id": log.id,
                        "name": log.name,
                        "backup_id": log.backup_id,
                        "status_id": log.status_id,
                        "remarks": log.remarks,
                        "recovered_at": log.recovered_at,
                        "recovered_by_id": log.recovered_by_id,
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get recovery logs: {e}")
            raise ServerErrorException("Failed to retrieve recovery logs")


    async def get_recovery_log(
        self, db: AsyncSession, log_id: PyObjectId
    ) -> Dict[str, Any]:
        """
        Get recovery log details by ID with backup information.
        
        Args:
            db: Database session
            log_id: MongoDB ObjectId of the recovery log
        
        Returns:
            Recovery log details with backup information
        
        Raises:
            NotFoundException: If recovery log with given ID is not found
        """
        recovery_log = await backup_crud.get_recovery_log(log_id)
        if not recovery_log:
            raise NotFoundException("Recovery log not found")

        backup_log = await backup_crud.get_backup_log(recovery_log.backup_id)

        return {
            "id": recovery_log.id,
            "name": recovery_log.name,
            "backup_id": recovery_log.backup_id,
            "status_id": recovery_log.status_id,
            "remarks": recovery_log.remarks,
            "recovered_at": recovery_log.recovered_at,
            "recovered_by_id": recovery_log.recovered_by_id,
            "backup_name": backup_log.name if backup_log else "Unknown",
            "backup_file_path": backup_log.file_path if backup_log else "",
        }


    async def delete_recovery_log(self, db: AsyncSession, log_id: PyObjectId) -> None:
        """
        Delete a recovery log from MongoDB.
        
        Args:
            db: Database session
            log_id: MongoDB ObjectId of the recovery log to delete
        
        Raises:
            NotFoundException: If recovery log with given ID is not found
        """
        success = await backup_crud.delete_recovery_log(log_id)
        if not success:
            raise NotFoundException("Recovery log not found")


backup_service = BackupService()
