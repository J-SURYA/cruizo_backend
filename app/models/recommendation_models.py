from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    Index,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship


from .base import Base


class UserRecommendation(Base):
    """
    Table to store car recommendations for users.
    """

    __tablename__ = "user_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)

    recommended_car_ids = Column(JSONB, nullable=False)
    based_on_bookings = Column(JSONB, nullable=True)
    confidence_score = Column(Float, nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_notified = Column(Boolean, default=False, nullable=False)
    notified_at = Column(DateTime(timezone=True), nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    user = relationship("User", backref="recommendations", lazy="selectin")

    __table_args__ = (
        Index("idx_user_recommendations_active", "user_id", "expires_at"),
    )
