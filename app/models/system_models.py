from sqlalchemy import Column, String, Integer, ForeignKey, Enum, Text, DateTime, JSON
from sqlalchemy.orm import relationship


from .base import Base, TimestampMixin
from .enums import NotificationType


class Notification(Base, TimestampMixin):
    """
    Notification model to track messages sent between users.
    """

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(String(255), ForeignKey("users.id"), nullable=True, index=True)
    receiver_id = Column(
        String(255), ForeignKey("users.id"), nullable=False, index=True
    )
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    attachment_urls = Column(JSON, nullable=True)
    status_id = Column(Integer, ForeignKey("status.id"), nullable=False, index=True)
    type = Column(
        Enum(NotificationType, name="notification_type_enum"),
        nullable=False,
        index=True,
    )
    read_at = Column(DateTime(timezone=True), nullable=True)

    sender = relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="sent_notifications",
        lazy="selectin",
    )
    receiver = relationship(
        "User",
        foreign_keys=[receiver_id],
        back_populates="received_notifications",
        lazy="selectin",
    )
    status = relationship("Status", back_populates="notifications", lazy="selectin")


class Query(Base, TimestampMixin):
    """
    Customer query model.
    """

    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    status_id = Column(Integer, ForeignKey("status.id"), nullable=False, index=True)

    responded_at = Column(DateTime(timezone=True), nullable=True)
    responded_by = Column(String(255), ForeignKey("users.id"), nullable=True)
    status = relationship("Status", back_populates="queries", lazy="selectin")
    responder = relationship(
        "User",
        back_populates="responded_queries",
        foreign_keys=[responded_by],
        lazy="selectin",
    )
