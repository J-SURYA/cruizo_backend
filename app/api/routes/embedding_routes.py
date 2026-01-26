from fastapi import (
    APIRouter,
    Depends,
    Security,
    HTTPException,
    status,
    Query,
    BackgroundTasks,
)
from sqlalchemy.ext.asyncio import AsyncSession


from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.models.user_models import User
from app.services import embedding_service
from app.schemas.utility_schemas import Msg
from app.utils.logger_utils import get_logger


router = APIRouter()
logger = get_logger(__name__)


@router.post("/rebuild", response_model=Msg)
async def rebuild_embeddings(
    background_tasks: BackgroundTasks,
    force_refresh: bool = Query(False, description="Force re-embedding of all cars"),
    include_documents: bool = Query(
        True, description="Also rebuild document embeddings"
    ),
    db: AsyncSession = Depends(get_sql_session),
    _: User = Security(get_current_user, scopes=["system:admin"]),
):
    """
    Admin endpoint to rebuild embeddings for all cars and documents.

    Args:
        background_tasks: FastAPI background tasks handler
        force_refresh: Force re-embedding of all cars
        include_documents: Also rebuild document embeddings
        db: Database session dependency

    Returns:
        Success message confirming background task started
    """
    try:

        async def rebuild_task():
            try:
                car_result = await embedding_service.embed_all_cars(
                    db, force_refresh=force_refresh
                )
                logger.info(f"Car embedding rebuild completed: {car_result}")

                if include_documents:
                    doc_result = await embedding_service.embed_all_documents(db)
                    logger.info(f"Document embedding rebuild completed: {doc_result}")

            except Exception as e:
                logger.error(f"Error in embedding rebuild task: {str(e)}")

        background_tasks.add_task(rebuild_task)

        return Msg(
            message=f"Embedding rebuild started in background (force_refresh={force_refresh}, include_documents={include_documents})"
        )

    except Exception as e:
        logger.error(f"Error starting embedding rebuild: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start embedding rebuild",
        )


@router.post("/car/{car_id}", response_model=Msg)
async def rebuild_car_embedding(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: User = Security(get_current_user, scopes=["system:admin"]),
):
    """
    Admin endpoint to rebuild embedding for a specific car.

    Args:
        car_id: Unique identifier of the car
        db: Database session dependency

    Returns:
        Success message confirming embedding update
    """
    await embedding_service.embed_car(db, car_id, force_refresh=True)
    return Msg(message=f"Embedding for car {car_id} updated successfully")


@router.delete("/car/{car_id}", response_model=Msg)
async def delete_car_embedding(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: User = Security(get_current_user, scopes=["system:admin"]),
):
    """
    Admin endpoint to delete embedding for a specific car.

    Args:
        car_id: Unique identifier of the car
        db: Database session dependency

    Returns:
        Success message confirming embedding deletion
    """
    try:
        deleted = await embedding_service.delete_car_embedding(db, car_id)

        if deleted:
            return Msg(message=f"Embedding for car {car_id} deleted successfully")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Embedding not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting car embedding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete car embedding",
        )


@router.post("/documents/refresh", response_model=Msg)
async def refresh_document_embeddings(
    db: AsyncSession = Depends(get_sql_session),
    _: User = Security(get_current_user, scopes=["system:admin"]),
):
    """
    Admin endpoint to refresh document embeddings immediately.

    Args:
        db: Database session dependency

    Returns:
        Success message with processing statistics
    """
    result = await embedding_service.embed_all_documents(db)
    return Msg(
        message=f"Document embeddings refreshed successfully. "
        f"Processed {result.total_processed} chunks "
        f"(Terms: {result.terms}, FAQ: {result.faq}, "
        f"Help: {result.help}, Privacy: {result.privacy})"
    )
