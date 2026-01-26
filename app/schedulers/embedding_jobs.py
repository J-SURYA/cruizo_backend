from app.services.embedding_services import embedding_service
from app.core.dependencies import get_sql_session
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def refresh_document_embeddings():
    """
    Refresh all document embeddings for the chat assistant.
    
    Runs daily at 1:00 AM to ensure the chat assistant has access
    to the latest content with updated embeddings.

    Args:
        None
    
    Returns:
        None
    """
    try:
        logger.info("Starting daily document embedding refresh")

        async for db in get_sql_session():
            result = await embedding_service.embed_all_documents(db)

            logger.info(
                f"Document embedding refresh completed: "
                f"Total: {result['total_processed']}, "
                f"Terms: {result['terms']}, "
                f"FAQ: {result['faq']}, "
                f"Help: {result['help']}, "
                f"Privacy: {result['privacy']}, "
                f"Errors: {result['errors']}"
            )
            break

    except Exception as e:
        logger.error(f"Error in document embedding refresh job: {e}", exc_info=True)
