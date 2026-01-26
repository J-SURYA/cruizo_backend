from sqlalchemy import Column, Integer, Enum
from sqlalchemy.orm import relationship


from .base import Base
from .enums import StatusEnum


class Status(Base):
    """
    Lookup table for various status types.
    """

    __tablename__ = "status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Enum(StatusEnum, name="status_enum"), nullable=False, unique=True)

    users = relationship("User", back_populates="status", lazy="selectin")
    cars = relationship("Car", back_populates="status", lazy="selectin")

    bookings = relationship(
        "Booking",
        back_populates="booking_status",
        foreign_keys="[Booking.booking_status_id]",
        lazy="selectin",
    )
    booking_payment_statuses = relationship(
        "Booking",
        back_populates="payment_status",
        foreign_keys="[Booking.payment_status_id]",
        lazy="selectin",
    )
    payments = relationship("Payment", back_populates="status", lazy="selectin")
    notifications = relationship(
        "Notification", back_populates="status", lazy="selectin"
    )
    queries = relationship("Query", back_populates="status", lazy="selectin")
