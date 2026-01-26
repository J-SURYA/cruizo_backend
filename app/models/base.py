from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    """

    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


class TimestampMixin:
    """
    Mixin to add created_at timestamp columns.
    """

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
