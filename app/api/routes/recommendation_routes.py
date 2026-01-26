from fastapi import APIRouter, Depends, Security, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession


from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.models.user_models import User
from app.services import recommendation_service
from app.schemas.recommendation_schemas import RecommendationResponse
from app.utils.logger_utils import get_logger


router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=RecommendationResponse)
async def get_recommendations(
    force_refresh: bool = Query(
        False, description="Force regeneration of recommendations"
    ),
    db: AsyncSession = Depends(get_sql_session),
    current_user: User = Security(get_current_user, scopes=["chats:read"]),
):
    """
    Get personalized car recommendations based on booking history.

    Args:
        force_refresh: Force regeneration of recommendations
        db: Database session dependency
        current_user: Authenticated user with chats:read permission

    Returns:
        Personalized recommendations with scores and reasons
    """
    try:
        recommendations = await recommendation_service.generate_recommendations(
            db, current_user.id, force_refresh
        )
        return recommendations

    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recommendations",
        )
