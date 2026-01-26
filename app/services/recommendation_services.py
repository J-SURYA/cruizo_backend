from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone, timedelta


from app.crud import recommendation_crud
from app.schemas.recommendation_schemas import RecommendationResponse
from app.schemas.retrieval_schemas import BookingHistoryRequest
from app.models.recommendation_models import UserRecommendation
from app.core.config import get_settings
from app.models.booking_models import Booking
from .retrieval_services import retrieval_service
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)
settings = get_settings()


class RecommendationService:
    """
    Service for managing car recommendations based on user booking history.
    """
    async def generate_recommendations(
        self, db: AsyncSession, user_id: str, force_refresh: bool = False
    ) -> RecommendationResponse:
        """
        Generate personalized car recommendations for a user based on their booking history.
        
        Args:
            db: Database session
            user_id: ID of the user to generate recommendations for
            force_refresh: Force regeneration of recommendations even if cached version exists
        
        Returns:
            RecommendationResponse containing recommended cars and metadata
        """
        try:
            if not force_refresh:
                existing = await recommendation_crud.get_active_recommendation(
                    db, user_id
                )
                if existing:
                    logger.info(f"Using cached recommendations for user {user_id}")
                    return await self._build_recommendation_response(existing)

            cutoff_date = datetime.now(timezone.utc) - timedelta(
                days=settings.RECOMMENDATION_DAYS_LOOKBACK
            )

            from app.models.utility_models import Status

            completed_status = await db.scalar(
                select(Status).where(Status.name == "COMPLETED")
            )
            booked_status = await db.scalar(
                select(Status).where(Status.name == "BOOKED")
            )
            delivered_status = await db.scalar(
                select(Status).where(Status.name == "DELIVERED")
            )
            returning_status = await db.scalar(
                select(Status).where(Status.name == "RETURNING")
            )
            returned_status = await db.scalar(
                select(Status).where(Status.name == "RETURNED")
            )

            status_ids = [
                s.id
                for s in [
                    completed_status,
                    booked_status,
                    delivered_status,
                    returning_status,
                    returned_status,
                ]
                if s
            ]

            stmt = (
                select(Booking)
                .where(
                    and_(
                        Booking.booked_by == user_id,
                        Booking.created_at >= cutoff_date,
                        (
                            Booking.booking_status_id.in_(status_ids)
                            if status_ids
                            else True
                        ),
                    )
                )
                .order_by(Booking.created_at.desc())
                .limit(10)
            )

            result = await db.execute(stmt)
            bookings = result.scalars().all()

            if not bookings:
                logger.info(f"No booking history found for user {user_id}")
                return RecommendationResponse(
                    recommendations=[],
                    based_on=[],
                    generated_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                )

            request = BookingHistoryRequest(
                user_id=user_id,
                recent_bookings_count=10,
                limit=settings.RECOMMENDATION_LIMIT,
                exclude_current_bookings=True,
            )

            booking_history_response = (
                await retrieval_service.generate_inventory_from_booking_history(
                    db=db, request=request
                )
            )

            recommendations = []
            for result_item in booking_history_response.recommendations:
                recommendations.append(
                    {
                        "car_id": result_item.car_id,
                        "score": result_item.score,
                        "reason": f"Similar to cars you've booked before",
                        "details": {
                            "brand": result_item.brand,
                            "model": result_item.model,
                            "year": result_item.metadata.get("manufacture_year"),
                            "category": result_item.metadata.get("category"),
                            "rental_per_hr": result_item.metadata.get("rental_per_hr"),
                            "status": result_item.metadata.get("status"),
                            "color": result_item.metadata.get("color"),
                        },
                    }
                )

            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

            recommendation = await recommendation_crud.create_recommendation(
                db=db,
                user_id=user_id,
                recommended_car_ids=recommendations,
                based_on_bookings=[str(b.id) for b in bookings],
                expires_at=expires_at,
                confidence_score=(
                    sum(r["score"] for r in recommendations) / len(recommendations)
                    if recommendations
                    else 0
                ),
            )

            logger.info(
                f"Generated {len(recommendations)} recommendations for user {user_id}"
            )
            return await self._build_recommendation_response(recommendation)

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            raise


    async def _build_recommendation_response(
        self, recommendation: UserRecommendation
    ) -> RecommendationResponse:
        """
        Build a recommendation response from a UserRecommendation model.
        
        Args:
            recommendation: UserRecommendation model instance
        
        Returns:
            RecommendationResponse containing formatted recommendation data
        """
        return RecommendationResponse(
            recommendations=recommendation.recommended_car_ids,
            based_on=recommendation.based_on_bookings,
            generated_at=recommendation.updated_at,
            expires_at=recommendation.expires_at,
            confidence_score=recommendation.confidence_score,
        )


recommendation_service = RecommendationService()
