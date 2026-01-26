from app.crud import booking_crud
from app.core.dependencies import get_sql_session
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def cleanup_expired_freezes():
    """
    Remove expired booking freezes from the database.
    
    Runs every 30 seconds to ensure timely release of frozen bookings,
    making them available for other users.

    Args:
        None
    
    Returns:
        None
    """
    try:
        async for db in get_sql_session():
            await booking_crud.cleanup_expired_freezes(db)
            break

    except Exception as e:
        logger.error(f"Error in freeze cleanup job: {e}", exc_info=True)
