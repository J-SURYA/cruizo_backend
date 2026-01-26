import enum


class RoleName(str, enum.Enum):
    """
    User roles in the system.
    """

    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"


class Tags(str, enum.Enum):
    """
    Tags for categorizing customers.
    """

    ROOKIE = "ROOKIE"
    TRAVELER = "TRAVELER"
    PRO = "PRO"


class TransmissionType(str, enum.Enum):
    """
    Types of car transmission.
    """

    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"


class NotificationType(str, enum.Enum):
    """
    Types of notifications.
    """

    SUPPORT = "SUPPORT"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    SYSTEM = "SYSTEM"
    BOOKING = "BOOKING"


class PaymentMethod(str, enum.Enum):
    """
    Types of payment methods.
    """

    CARD = "CARD"
    UPI = "UPI"
    NET_BANKING = "NET_BANKING"


class PaymentType(str, enum.Enum):
    """
    Types of payment transactions.
    """

    PAYMENT = "PAYMENT"
    ADD_PAYMENT = "ADD_PAYMENT"
    REFUND = "REFUND"
    CANCELLATION_REFUND = "CANCELLATION_REFUND"
    REJECTION_REFUND = "REJECTION_REFUND"


class PaymentStatusEnum(str, enum.Enum):
    """
    Payment transaction statuses.
    """

    PAID = "PAID"
    REFUNDING = "REFUNDING"
    REFUNDED = "REFUNDED"
    CHARGED = "CHARGED"
    INITIATED = "INITIATED"
    SETTLED = "SETTLED"


class QueryStatusEnum(str, enum.Enum):
    """
    Status of customer queries.
    """

    PENDING = "PENDING"
    RESPONDED = "RESPONDED"


class NotificationStatusEnum(str, enum.Enum):
    """Read status of notifications."""

    READ = "READ"
    UNREAD = "UNREAD"


class BookingStatusEnum(str, enum.Enum):
    """Booking states throughout its lifecycle."""

    BOOKED = "BOOKED"
    DELIVERED = "DELIVERED"
    RETURNING = "RETURNING"
    RETURNED = "RETURNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class CarStatusEnum(str, enum.Enum):
    """Car availability status in inventory."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class UserStatusEnum(str, enum.Enum):
    """User account state."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class StatusEnum(str, enum.Enum):
    """Unified status enum covering user, booking, payment, notifications, and system events."""

    # User
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

    # Booking
    BOOKED = "BOOKED"
    DELIVERED = "DELIVERED"
    RETURNING = "RETURNING"
    RETURNED = "RETURNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

    # Payment
    PAID = "PAID"
    REFUNDING = "REFUNDING"
    REFUNDED = "REFUNDED"
    CHARGED = "CHARGED"
    INITIATED = "INITIATED"
    SETTLED = "SETTLED"

    # Notification
    READ = "READ"
    UNREAD = "UNREAD"

    # Query
    PENDING = "PENDING"
    RESPONDED = "RESPONDED"


class PromotionTypeEnum(str, enum.Enum):
    """Types of promotions."""

    PROMOTION = "PROMOTION"
    OFFER = "OFFER"
