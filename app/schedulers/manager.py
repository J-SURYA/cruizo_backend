from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


from .backup_jobs import run_scheduled_backups
from .freeze_jobs import cleanup_expired_freezes
from .recommendation_generation_jobs import generate_daily_recommendations
from .recommendation_notification_jobs import send_recommendation_notifications
from .recommendation_cleanup_jobs import cleanup_expired_recommendations
from .embedding_jobs import refresh_document_embeddings
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class SchedulerManager:
    """
    Manages lifecycle and registration of all background scheduled jobs.
    """

    def __init__(self):
        """
        Initialize the scheduler manager with APScheduler instance.
        """
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    async def start(self):
        """
        Start the scheduler and register all jobs.
        
        Jobs are registered with CronTrigger for precise timing.
        Idempotent - safe to call multiple times.
        """
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        # Backup jobs - Check for scheduled backups every minute
        self.scheduler.add_job(
            run_scheduled_backups,
            trigger=CronTrigger(minute="*"),  # Every minute
            id="backup_scheduled",
            name="Check and Run Scheduled Backups",
            replace_existing=True,
        )

        # Freeze cleanup - Every 30 seconds via cron (runs twice per minute)
        self.scheduler.add_job(
            cleanup_expired_freezes,
            trigger=CronTrigger(second="0,30"),  # 0 and 30 seconds of each minute
            id="freeze_cleanup",
            name="Cleanup Expired Booking Freezes",
            replace_existing=True,
        )

        # Recommendation jobs
        self.scheduler.add_job(
            generate_daily_recommendations,
            trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM daily
            id="daily_recommendations",
            name="Generate Daily Recommendations",
            replace_existing=True,
        )

        self.scheduler.add_job(
            send_recommendation_notifications,
            trigger=CronTrigger(hour=10, minute=0),  # 10:00 AM daily
            id="send_notifications",
            name="Send Recommendation Notifications",
            replace_existing=True,
        )

        self.scheduler.add_job(
            cleanup_expired_recommendations,
            trigger=CronTrigger(hour=3, minute=0),  # 3:00 AM daily
            id="cleanup_expired",
            name="Cleanup Expired Recommendations",
            replace_existing=True,
        )

        # Embedding refresh - Daily at 1:00 AM
        self.scheduler.add_job(
            refresh_document_embeddings,
            trigger=CronTrigger(hour=1, minute=0),  # 1:00 AM daily
            id="refresh_documents",
            name="Refresh Document Embeddings",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("Scheduler manager started with all jobs registered")

    async def stop(self):
        """
        Stop the scheduler gracefully.
        
        Waits for running jobs to complete before shutting down.
        """
        if not self.is_running:
            logger.warning("Scheduler not running")
            return

        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Scheduler manager stopped")


scheduler_manager = SchedulerManager()
