import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_


from app.services.recommendation_services import recommendation_service
from app.core.config import get_settings
from app.models.user_models import User
from app.models.booking_models import Booking
from app.models.utility_models import Status
from app.core.dependencies import get_sql_session
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)
settings = get_settings()


async def generate_daily_recommendations():
    """
    Generate personalized recommendations for all active users.
    
    Runs daily at 2:00 AM. Identifies users with recent booking history
    and generates recommendations based on their preferences and patterns.
    
    Args:
        None

    Returns:
        None
    """
    try:
        async for db in get_sql_session():
            cutoff_date = datetime.now(timezone.utc) - timedelta(
                days=settings.RECOMMENDATION_DAYS_LOOKBACK
            )

            # Get active users with recent bookings
            active_status = await db.scalar(
                select(Status).where(Status.name == "ACTIVE")
            )

            if active_status:
                stmt = (
                    select(User.id)
                    .join(Booking)
                    .where(
                        and_(
                            Booking.created_at >= cutoff_date,
                            User.status_id == active_status.id,
                        )
                    )
                    .distinct()
                )
            else:
                stmt = (
                    select(User.id)
                    .join(Booking)
                    .where(Booking.created_at >= cutoff_date)
                    .distinct()
                )

            result = await db.execute(stmt)
            user_ids = [row[0] for row in result.all()]

            logger.info(f"Found {len(user_ids)} active users for recommendations")

            batch_size = settings.RECOMMENDATION_BATCH_SIZE
            total_processed = 0
            total_errors = 0

            for i in range(0, len(user_ids), batch_size):
                batch = user_ids[i : i + batch_size]

                for user_id in batch:
                    try:
                        await recommendation_service.generate_recommendations(
                            db=db, user_id=user_id, force_refresh=True
                        )
                        total_processed += 1
                    except Exception as e:
                        logger.error(
                            f"Error generating recommendations for user {user_id}: {e}"
                        )
                        total_errors += 1

                logger.info(f"Processed {total_processed}/{len(user_ids)} users")
                await asyncio.sleep(1)

            logger.info(
                f"Daily recommendation generation completed: "
                f"{total_processed} successful, {total_errors} errors"
            )
            break

    except Exception as e:
        logger.error(f"Error in daily recommendation generation job: {e}", exc_info=True)
