from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from datetime import datetime, timezone


from app.models.recommendation_models import UserRecommendation
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class RecommendationCRUD:
    """
    Class for managing user recommendations.
    """
    async def create_recommendation(
        self,
        db: AsyncSession,
        user_id: str,
        recommended_car_ids: List[Dict[str, Any]],
        based_on_bookings: List[str],
        expires_at: datetime,
        confidence_score: Optional[float] = None,
    ) -> UserRecommendation:
        """
        Create a new recommendation.

        Args:
            db: Database session
            user_id: User identifier
            recommended_car_ids: List of recommended car IDs with metadata
            based_on_bookings: List of booking IDs used for recommendation
            expires_at: Expiration datetime for the recommendation
            confidence_score: Optional confidence score for the recommendation

        Returns:
            Newly created UserRecommendation object
        """
        try:
            recommendation = UserRecommendation(
                user_id=user_id,
                recommended_car_ids=recommended_car_ids,
                based_on_bookings=based_on_bookings,
                expires_at=expires_at,
                confidence_score=confidence_score,
            )

            db.add(recommendation)
            await db.commit()
            await db.refresh(recommendation)

            logger.info(f"Created recommendation for user {user_id}")
            return recommendation

        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating recommendation: {str(e)}")
            raise


    async def get_active_recommendation(
        self, db: AsyncSession, user_id: str
    ) -> Optional[UserRecommendation]:
        """
        Get active recommendation for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Active UserRecommendation if found, None otherwise
        """
        try:
            now = datetime.now(timezone.utc)

            stmt = (
                select(UserRecommendation)
                .where(
                    and_(
                        UserRecommendation.user_id == user_id,
                        UserRecommendation.expires_at > now,
                    )
                )
                .order_by(UserRecommendation.updated_at.desc())
            )

            result = await db.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting recommendation: {str(e)}")
            raise


    async def mark_as_notified(self, db: AsyncSession, recommendation_id: int) -> None:
        """
        Mark recommendation as notified.

        Args:
            db: Database session
            recommendation_id: Recommendation identifier to mark as notified
        """
        try:
            stmt = select(UserRecommendation).where(
                UserRecommendation.id == recommendation_id
            )
            result = await db.execute(stmt)
            recommendation = result.scalar_one_or_none()

            if recommendation:
                recommendation.is_notified = True
                recommendation.notified_at = datetime.now(timezone.utc)
                await db.commit()

        except Exception as e:
            await db.rollback()
            logger.error(f"Error marking recommendation as notified: {str(e)}")
            raise


    async def delete_user_recommendations(self, db: AsyncSession, user_id: str) -> int:
        """
        Delete all recommendations for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Number of recommendations deleted
        """
        try:
            stmt = delete(UserRecommendation).where(
                UserRecommendation.user_id == user_id
            )

            result = await db.execute(stmt)
            await db.commit()

            return result.rowcount

        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting recommendations: {str(e)}")
            raise


    async def cleanup_expired_recommendations(self, db: AsyncSession) -> int:
        """
        Delete expired recommendations.

        Args:
            db: Database session

        Returns:
            Number of expired recommendations deleted
        """
        try:
            now = datetime.now(timezone.utc)

            stmt = delete(UserRecommendation).where(UserRecommendation.expires_at < now)

            result = await db.execute(stmt)
            await db.commit()

            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} expired recommendations")
            return deleted_count

        except Exception as e:
            await db.rollback()
            logger.error(f"Error cleaning up recommendations: {str(e)}")
            raise


recommendation_crud = RecommendationCRUD()
