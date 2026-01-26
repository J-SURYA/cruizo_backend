from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any, Dict
from datetime import datetime, date
from decimal import Decimal


from app.models.enums import PaymentMethod, PaymentType, PaymentStatusEnum


class PaymentBase(BaseModel):
    """
    Schema for payment transaction information.
    """
    amount_inr: Decimal = Field(
        ..., gt=0, decimal_places=2, description="Payment amount in Indian Rupees"
    )
    payment_method: PaymentMethod = Field(
        ..., description="Method used for payment processing"
    )
    payment_type: PaymentType = Field(..., description="Type of payment transaction")
    transaction_id: str = Field(
        ..., max_length=255, description="Unique transaction identifier"
    )
    razorpay_order_id: str = Field(
        ..., max_length=255, description="Razorpay order identifier"
    )
    razorpay_payment_id: str = Field(
        ..., max_length=255, description="Razorpay payment identifier"
    )
    razorpay_signature: str = Field(
        ..., max_length=255, description="Razorpay payment signature"
    )
    remarks: Optional[str] = Field(
        None, max_length=500, description="Additional payment notes or description"
    )


class PaymentCreate(PaymentBase):
    """
    Schema for creating a new payment transaction.
    """
    booking_id: int = Field(..., description="Booking ID associated with this payment")
    status_id: Optional[int] = Field(
        None, description="Initial payment status ID for auto-payments"
    )


class PaymentPublic(PaymentBase):
    """
    Schema for payment transaction details.
    """
    id: int = Field(..., description="Payment unique identifier")
    status: PaymentStatusEnum = Field(..., description="Current payment status")
    created_at: datetime = Field(..., description="Payment creation timestamp")
    model_config = ConfigDict(from_attributes=True)


class PaymentInitiationRequest(BaseModel):
    """
    Schema for initiating payment from a freeze.
    """
    freeze_id: int = Field(..., description="Freeze ID from freeze-booking")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    transaction_id: str = Field(..., description="Transaction ID")
    razorpay_order_id: Optional[str] = Field(None, description="Razorpay order ID")
    razorpay_payment_id: Optional[str] = Field(None, description="Razorpay payment ID")
    razorpay_signature: Optional[str] = Field(None, description="Razorpay signature")
    remarks: Optional[str] = Field(None, description="Additional remarks")


class PaymentBookingCar(BaseModel):
    """
    Schema for minimal car details for payment booking information.
    """
    id: int = Field(..., description="Car unique identifier")
    car_no: str = Field(..., description="Vehicle registration number")
    car_model: Dict[str, Any] = Field(..., description="Car model details")
    created_at: datetime = Field(..., description="Car creation timestamp")
    model_config = ConfigDict(from_attributes=True)


class PaymentBookingUser(BaseModel):
    """
    Schema for minimal user details for payment booking information.
    """
    id: str = Field(..., description="User unique identifier")
    email: str = Field(..., description="User's email address")
    username: str = Field(..., description="User's username")
    customer_name: Optional[str] = Field(
        None, description="Customer's full name if available"
    )
    created_at: datetime = Field(..., description="User account creation timestamp")
    model_config = ConfigDict(from_attributes=True)


class PaymentBookingInfo(BaseModel):
    """
    Schema for booking information associated with a payment.
    """
    id: int = Field(..., description="Booking unique identifier")
    booked_by: str = Field(..., description="User ID who created the booking")
    booking_status: Optional[str] = Field(None, description="Current booking status")
    payment_status: Optional[str] = Field(None, description="Current payment status")
    car: PaymentBookingCar = Field(..., description="Car details for the booking")
    booker: PaymentBookingUser = Field(
        ..., description="User details who created the booking"
    )
    created_at: datetime = Field(..., description="Booking creation timestamp")
    model_config = ConfigDict(from_attributes=True)


class PaymentDetailed(PaymentPublic):
    """
    Schema for detailed payment information including associated booking details.
    """
    booking: PaymentBookingInfo = Field(
        ..., description="Booking information associated with this payment"
    )
    model_config = ConfigDict(from_attributes=True)


class PaymentFilterParams:
    """
    Schema for filter parameters helper class for payment queries.
    """
    def __init__(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        payment_type: Optional[PaymentType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sort: Optional[str] = "created_at_desc",
    ):
        self.search = search
        self.status = status
        self.payment_type = payment_type
        self.start_date = start_date
        self.end_date = end_date
        self.sort = sort


class PaginatedResponse(BaseModel):
    """
    Schema for generic paginated response schema for payment lists.
    """
    total: int = Field(..., description="Total number of records matching filters")
    items: List[Any] = Field(..., description="List of payment records")
    skip: int = Field(..., description="Number of records skipped for pagination")
    limit: int = Field(..., description="Maximum number of records returned")


class Msg(BaseModel):
    """
    Schema for simple message response.
    """
    message: str = Field(..., description="Response message")


class PaymentConfirmRequest(BaseModel):
    """
    Schema for confirming a payment with Razorpay details.
    """
    payment_method: Optional[PaymentMethod] = Field(None, description="Payment method")
    transaction_id: Optional[str] = Field(None, description="Transaction ID")
    razorpay_order_id: Optional[str] = Field(
        None, description="Razorpay order identifier"
    )
    razorpay_payment_id: Optional[str] = Field(
        None, description="Razorpay payment identifier"
    )
    razorpay_signature: Optional[str] = Field(
        None, description="Razorpay payment signature"
    )
    remarks: Optional[str] = Field(None, description="Remarks")
