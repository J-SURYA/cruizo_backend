from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    Enum,
    Numeric,
    Text,
    DateTime,
    Float,
    Boolean,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone


from .base import Base, TimestampMixin
from .enums import PaymentMethod, PaymentType


class Location(Base):
    """
    Stores geographical coordinates for delivery/pickup.
    """

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    address = Column(String(500), nullable=True)

    __table_args__ = (Index("idx_locations_coords", "latitude", "longitude"),)


class BookingFreeze(Base, TimestampMixin):
    """
    Table to manage temporary holds on car bookings.
    """

    __tablename__ = "booking_freezes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    user_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)

    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    freeze_expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    delivery_longitude = Column(Float, nullable=False)
    delivery_latitude = Column(Float, nullable=False)
    pickup_longitude = Column(Float, nullable=False)
    pickup_latitude = Column(Float, nullable=False)

    car = relationship("Car", backref="freezes", lazy="selectin")
    user = relationship("User", backref="booking_freezes", lazy="selectin")

    __table_args__ = (
        Index("idx_freezes_car_time", "car_id", "start_date", "end_date"),
    )

    @property
    def is_expired(self):
        return datetime.now(timezone.utc) > self.freeze_expires_at


class Booking(Base, TimestampMixin):
    """
    Table to manage car bookings.
    """

    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    start_date = Column(DateTime(timezone=True), nullable=False, index=True)
    end_date = Column(DateTime(timezone=True), nullable=False, index=True)

    delivery_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    pickup_id = Column(Integer, ForeignKey("locations.id"), nullable=False)

    booking_status_id = Column(
        Integer, ForeignKey("status.id"), nullable=False, index=True
    )
    payment_status_id = Column(
        Integer, ForeignKey("status.id"), nullable=True, index=True
    )

    booked_by = Column(String(255), ForeignKey("users.id"), nullable=False)
    remarks = Column(String(500), nullable=True)

    payment_summary = Column(JSONB, nullable=False, default={})

    delivery_video_url = Column(String(512), nullable=True)
    delivery_otp = Column(String(6), nullable=True)
    delivery_otp_generated_at = Column(DateTime(timezone=True), nullable=True)
    delivery_otp_verified = Column(Boolean, default=False, nullable=False)
    delivery_otp_verified_at = Column(DateTime(timezone=True), nullable=True)
    start_kilometers = Column(Integer, nullable=True)

    pickup_video_url = Column(String(512), nullable=True)
    pickup_otp = Column(String(6), nullable=True)
    pickup_otp_generated_at = Column(DateTime(timezone=True), nullable=True)
    pickup_otp_verified = Column(Boolean, default=False, nullable=False)
    pickup_otp_verified_at = Column(DateTime(timezone=True), nullable=True)
    end_kilometers = Column(Integer, nullable=True)

    return_requested_at = Column(DateTime(timezone=True), nullable=True)

    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by = Column(String(255), ForeignKey("users.id"), nullable=True)
    cancellation_reason = Column(String(500), nullable=True)

    referral_benefit = Column(Boolean, default=False, nullable=False)

    car = relationship("Car", back_populates="bookings", lazy="selectin")
    delivery_location = relationship(
        "Location", foreign_keys=[delivery_id], lazy="selectin"
    )
    pickup_location = relationship(
        "Location", foreign_keys=[pickup_id], lazy="selectin"
    )
    booking_status = relationship(
        "Status", foreign_keys=[booking_status_id], lazy="selectin"
    )
    payment_status = relationship(
        "Status", foreign_keys=[payment_status_id], lazy="selectin"
    )
    booker = relationship("User", foreign_keys=[booked_by], lazy="selectin")
    canceller = relationship("User", foreign_keys=[cancelled_by], lazy="selectin")
    payments = relationship("Payment", back_populates="booking", lazy="selectin")
    review = relationship(
        "Review", back_populates="booking", uselist=False, lazy="selectin"
    )

    __table_args__ = (
        Index("idx_bookings_dates", "start_date", "end_date"),
        Index("idx_bookings_user", "booked_by"),
        Index("idx_bookings_status", "booking_status_id", "payment_status_id"),
    )

    @property
    def is_cancellable_by_customer(self):
        if self.booking_status.name in ["CANCELLED", "COMPLETED"]:
            return False
        time_to_start = (
            self.start_date - datetime.now(timezone.utc)
        ).total_seconds() / 3600
        return time_to_start > 0


class Payment(Base, TimestampMixin):
    """
    Payment details of bookings.
    """

    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)

    amount_inr = Column(Numeric(10, 2), nullable=False)
    payment_method = Column(
        Enum(PaymentMethod, name="payment_method_enum"), nullable=False
    )
    payment_type = Column(Enum(PaymentType, name="payment_type_enum"), nullable=False)

    status_id = Column(Integer, ForeignKey("status.id"), nullable=False, index=True)

    transaction_id = Column(String(255), unique=True, nullable=False)
    razorpay_order_id = Column(String(255), unique=True, nullable=False)
    razorpay_payment_id = Column(String(255), unique=True, nullable=False)
    razorpay_signature = Column(String(255), unique=True, nullable=False)

    remarks = Column(String(500), nullable=True)

    booking = relationship("Booking", back_populates="payments", lazy="selectin")
    status = relationship("Status", back_populates="payments", lazy="selectin")

    __table_args__ = (
        Index("idx_payments_booking", "booking_id", "status_id"),
        Index("idx_payments_transaction", "transaction_id"),
    )


class Review(Base, TimestampMixin):
    """
    Reviews of completed bookings.
    """

    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(
        Integer, ForeignKey("bookings.id"), unique=True, nullable=False, index=True
    )
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)

    rating = Column(Integer, nullable=False)  # 1-5
    remarks = Column(Text, nullable=True)
    created_by = Column(String(255), ForeignKey("users.id"), nullable=False)

    booking = relationship("Booking", back_populates="review", lazy="selectin")
    car = relationship("Car", back_populates="reviews", lazy="selectin")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
