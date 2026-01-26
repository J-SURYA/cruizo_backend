from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_


from app.crud import recommendation_crud
from app.models.recommendation_models import UserRecommendation
from app.core.dependencies import get_sql_session
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


async def send_recommendation_notifications():
    """
    Send notifications to users for new unnotified recommendations.
    
    Runs daily at 10:00 AM. Notifies users about personalized car
    recommendations generated during the night.

    Args:
        None
    
    Returns:
        None
    """
    try:
        async for db in get_sql_session():
            stmt = (
                select(UserRecommendation)
                .where(
                    and_(
                        UserRecommendation.is_notified.is_(False),
                        UserRecommendation.expires_at > datetime.now(timezone.utc),
                    )
                )
                .limit(500)
            )

            result = await db.execute(stmt)
            recommendations = result.scalars().all()

            logger.info(f"Found {len(recommendations)} recommendations to notify")

            from app.crud import system_crud

            sent_count = 0
            error_count = 0

            for rec in recommendations:
                try:
                    message = await _build_recommendation_message(db, rec)

                    await system_crud.create_notification(
                        db=db,
                        receiver_id=rec.user_id,
                        sender_id="U0001",
                        title="New Car Recommendations for You!",
                        message=message,
                        notification_type="RECOMMENDATION",
                        metadata={
                            "recommendation_id": rec.id,
                            "car_count": len(rec.recommended_car_ids),
                            "action_url": "/recommendations",
                        },
                    )

                    await recommendation_crud.mark_as_notified(db, rec.id)
                    sent_count += 1

                except Exception as e:
                    logger.error(
                        f"Error sending notification for recommendation {rec.id}: {e}"
                    )
                    error_count += 1

            logger.info(
                f"Notification delivery completed: {sent_count} sent, {error_count} errors"
            )
            break

    except Exception as e:
        logger.error(f"Error in notification delivery job: {e}", exc_info=True)


async def _build_recommendation_message(
    db: AsyncSession, recommendation: UserRecommendation
) -> str:
    """
    Build a personalized notification message for recommendations.
    
    Args:
        db: Database session
        recommendation: UserRecommendation instance
        
    Returns:
        Formatted message string
    """
    try:
        car_ids = recommendation.recommended_car_ids

        if not car_ids:
            return "We have new car recommendations for you based on your preferences."

        top_cars = car_ids[:3]
        car_names = []

        for car_data in top_cars:
            details = car_data.get("details", {})
            name = f"{details.get('year', '')} {details.get('brand', 'Car')} {details.get('model', '')}"
            car_names.append(name.strip())

        if len(car_names) == 1:
            return f"Based on your rental history, we think you'll love the {car_names[0]}!"
        elif len(car_names) == 2:
            return f"Based on your rental history, check out the {car_names[0]} and {car_names[1]}!"
        else:
            return (
                f"Based on your rental history, we recommend the {car_names[0]}, "
                f"{car_names[1]}, and {car_names[2]}!"
            )

    except Exception as e:
        logger.error(f"Error building recommendation message: {e}")
        return "We have new car recommendations for you!"
