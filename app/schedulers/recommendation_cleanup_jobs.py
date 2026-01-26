from app.crud import recommendation_crud
from app.core.dependencies import get_sql_session
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def cleanup_expired_recommendations():
    """
    Remove expired recommendations from the database.
    
    Runs daily at 3:00 AM to maintain database hygiene and remove
    stale recommendation data.

    Args:
        None
    
    Returns:
        None
    """
    try:
        async for db in get_sql_session():
            deleted_count = await recommendation_crud.cleanup_expired_recommendations(db)
            logger.info(f"Deleted {deleted_count} expired recommendations")
            break

    except Exception as e:
        logger.error(f"Error in cleanup job: {e}", exc_info=True)
