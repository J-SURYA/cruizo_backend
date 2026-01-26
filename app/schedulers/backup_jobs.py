from datetime import datetime


from app.services.backup_services import backup_service
from app.crud import backup_crud
from app.collections.enums import BackupType
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def run_scheduled_backups():
    """
    Check for and execute any scheduled backups due at the current time.
    
    Runs every minute to check active backup schedules. If a schedule's
    configured time matches the current time, triggers the backup.

    Args:
        None
    
    Returns:
        None
    """
    try:
        schedules = await backup_crud.get_all_backup_schedules(status_id=1)
        current_time = datetime.now()

        for schedule in schedules:
            if _should_run_backup(schedule, current_time):
                logger.info(f"Executing scheduled backup: {schedule.name}")
                
                await backup_service.create_scheduled_backup(
                    db=None,
                    schedule_name=schedule.name,
                    backup_type=BackupType(schedule.type),
                    remarks=f"Automated backup from schedule: {schedule.name}",
                )
                
                logger.info(f"Completed scheduled backup: {schedule.name}")

    except Exception as e:
        logger.error(f"Error in scheduled backup job: {e}", exc_info=True)


def _should_run_backup(schedule, current_time: datetime) -> bool:
    """
    Determine if a backup schedule should execute now.
    
    Args:
        schedule: BackupSchedule instance with scheduled_time
        current_time: Current datetime to compare against
        
    Returns:
        True if backup should run, False otherwise
    """
    return (
        schedule.scheduled_time.hour == current_time.hour
        and schedule.scheduled_time.minute == current_time.minute
    )
