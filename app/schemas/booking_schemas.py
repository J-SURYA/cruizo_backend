from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date, timezone
from decimal import Decimal


from .inventory_schemas import CarComplete
from app.models.enums import StatusEnum, PaymentStatusEnum, PaymentMethod, PaymentType


class LocationBase(BaseModel):
    """
    Base schema for location with latitude and longitude.
    """
    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)


class LocationCreate(LocationBase):
    """
    Schema for creating a location with latitude and longitude.
    """
    pass


class LocationPublic(LocationBase):
    """
    Public schema for location with ID and optional address.
    """
    id: int = Field(..., description="Location ID")
    address: Optional[str] = Field(None, description="Formatted address")
    model_config = ConfigDict(from_attributes=True)


class FreezeCreate(BaseModel):
    """
    Schema for creating a freeze booking.
    """
    car_id: int = Field(..., description="Specific Car ID to freeze")
    start_date: datetime = Field(..., description="Booking start time")
    end_date: datetime = Field(..., description="Booking end time")
    delivery_location: LocationCreate = Field(..., description="Delivery location")
    pickup_location: LocationCreate = Field(..., description="Pickup location")

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_time_intervals(cls, v: datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v.minute not in [0, 30]:
            raise ValueError("Booking times must be in :00 or :30 minute intervals")
        return v

    @model_validator(mode="after")
    def validate_dates(self):
        start = (
            self.start_date
            if self.start_date.tzinfo
            else self.start_date.replace(tzinfo=timezone.utc)
        )
        end = (
            self.end_date
            if self.end_date.tzinfo
            else self.end_date.replace(tzinfo=timezone.utc)
        )

        if end <= start:
            raise ValueError("End date must be after start date")

        duration_hours = (end - start).total_seconds() / 3600
        if duration_hours < 8:
            raise ValueError("Booking duration must be at least 8 hours")

        return self


class FreezeUpdate(BaseModel):
    """
    Schema for updating freeze booking locations.
    """
    delivery_location: Optional[LocationCreate] = Field(
        None, description="New delivery location"
    )
    pickup_location: Optional[LocationCreate] = Field(
        None, description="New pickup location"
    )


class FreezeResponse(BaseModel):
    """
    Schema for freeze booking response.
    """
    id: int = Field(..., description="Freeze ID")
    car_id: int = Field(..., description="Car ID")
    user_id: str = Field(..., description="User ID")
    start_date: datetime = Field(..., description="Freeze start time")
    end_date: datetime = Field(..., description="Freeze end time")
    freeze_expires_at: datetime = Field(..., description="When freeze expires")
    is_active: bool = Field(..., description="If freeze is active")
    delivery_longitude: float = Field(..., description="Delivery longitude")
    delivery_latitude: float = Field(..., description="Delivery latitude")
    pickup_longitude: float = Field(..., description="Pickup longitude")
    pickup_latitude: float = Field(..., description="Pickup latitude")
    model_config = ConfigDict(from_attributes=True)


class PaymentSummary(BaseModel):
    """
    Schema for detailed payment summary of a booking.
    """

    # Booking Details
    booking_details: Dict[str, Any] = Field(
        default_factory=lambda: {
            "duration_hours": 0.0,
            "start_date": None,
            "end_date": None,
            "car_model": "",
            "color": "",
            "car_no": "",
        }
    )

    # Distance Calculation
    distance_calculation: Dict[str, Any] = Field(
        default_factory=lambda: {
            "hub_to_delivery_km": 0.0,
            "hub_to_pickup_km": 0.0,
            "total_distance_km": 0.0,
            "delivery_charge_tier": "",
        }
    )

    # Charges Breakdown
    charges_breakdown: Dict[str, Any] = Field(
        default_factory=lambda: {
            "base_rental": 0.0,
            "delivery_charges": 0.0,
            "maintenance_charges": 500.0,
            "security_deposit": 0.0,
            "platform_fee": 100.0,
            "subtotal": 0.0,
            "total_payable": 0.0,
            "rookie_discount_applied": False,
            "rookie_discount_description": "",
            "offer_discount_applied": 0.0,
            "offer_discount_percentage": 0.0,
            "offer_title": "",
            "referral_benefit_applied": False,
            "referral_benefit_description": "",
        }
    )

    # Kilometer Allowance
    kilometer_allowance: Dict[str, Any] = Field(
        default_factory=lambda: {
            "free_kilometers": 0,
            "limit_per_hour": 0,
            "extra_kilometers": 0,
            "extra_km_charges": 0.0,
        }
    )

    # Delivery Verification
    delivery_verification: Dict[str, Any] = Field(
        default_factory=lambda: {
            "admin_video_url": None,
            "delivery_otp_generated_at": None,
            "start_kilometers": None,
            "delivered_at": None,
            "delivery_otp_verified": False,
            "delivery_otp_verified_at": None,
            "admin_verified": False,
            "video_uploaded_at": None,
        }
    )

    # Return Request
    return_request: Dict[str, Any] = Field(
        default_factory=lambda: {
            "requested_at": None,
            "expected_return_time": None,
            "remarks": None,
        }
    )

    # Return Verification
    return_verification: Dict[str, Any] = Field(
        default_factory=lambda: {
            "admin_video_url": None,
            "pickup_otp_generated_at": None,
            "end_kilometers": None,
            "returned_at": None,
            "expected_return_time": None,
            "actual_return_time": None,
            "late_hours": None,
            "pickup_otp_verified": False,
            "pickup_otp_verified_at": None,
        }
    )

    # Extra Charges Calculation
    extra_charges_calculation: Dict[str, Any] = Field(
        default_factory=lambda: {
            "extra_kilometers": 0,
            "extra_km_charges": 0.0,
            "damage_charges": 0.0,
            "late_return_charges": 0.0,
            "other_charges": 0.0,
            "charges_breakdown": [],
            "total_extra_charges": 0.0,
            "calculated_at": None,
        }
    )

    # Settlement
    settlement: Dict[str, Any] = Field(
        default_factory=lambda: {
            "scenario": None,  # "INITIATED", "REFUNDING", "SETTLED"
            "additional_amount_due": 0.0,
            "refund_amount": 0.0,
            "settlement_status": "PENDING",
            "settled_at": None,
            "settlement_remarks": None,
        }
    )

    # Cancellation Details
    cancellation_details: Dict[str, Any] = Field(
        default_factory=lambda: {
            "cancelled": False,
            "cancelled_at": None,
            "cancelled_by": None,
            "cancellation_reason": None,
            "admin_notes": None,
            "refund_eligible": False,
            "refund_percentage": 0,
            "refund_amount": 0.0,
            "cancellation_charges": 0.0,
            "cancellation_policy": ">2 hours before start: 50% refund of base amount | ≤2 hours: No refund",
        }
    )

    # Refund Policy
    refund_policy: Dict[str, Any] = Field(
        default_factory=lambda: {
            "refundable_items": ["security_deposit", "base_rental (50% if >2 hours)"],
            "non_refundable_items": [
                "platform_fee",
                "maintenance_charges",
                "delivery_charges",
            ],
            "cancellation_refund": ">2 hours: 50% of base rental only",
            "security_deposit_refund": "Fully refundable minus any charges",
        }
    )


class EstimateResponse(BaseModel):
    """
    Schema for estimate response including freeze details and payment summary.
    """
    freeze_id: int = Field(..., description="Freeze ID")
    freeze_expires_at: datetime = Field(..., description="Freeze expiry time")
    payment_summary: PaymentSummary = Field(..., description="Complete payment summary")
    car_details: Dict[str, Any] = Field(..., description="Car details")


class FreezeBookingResponse(BaseModel):
    """
    Schema for freeze booking response including freeze details, car details, and payment summary.
    """
    freeze_id: int = Field(..., description="Freeze ID")
    car_details: CarComplete = Field(..., description="Car details")
    start_time: datetime = Field(..., description="Start time")
    end_time: datetime = Field(..., description="End time")
    delivery_location: LocationBase = Field(..., description="Delivery location")
    pickup_location: LocationBase = Field(..., description="Pickup location")
    freeze_expires_at: datetime = Field(..., description="Freeze expiry time")
    payment_summary: PaymentSummary = Field(..., description="Complete payment summary")


class StatusGeneric(BaseModel):
    """
    Schema for generic status representation.
    """
    name: Union[StatusEnum, PaymentStatusEnum, str] = Field(
        ..., description="Status name"
    )
    model_config = ConfigDict(from_attributes=True)


class CarBookingDetails(BaseModel):
    """
    Schema for car details in booking context.
    """
    id: int = Field(..., description="Car ID")
    car_no: str = Field(..., description="Car number")
    color: str = Field(..., description="Car color")
    car_model: Dict[str, Any] = Field(..., description="Car model details")
    image_urls: Optional[List[str]] = Field(default=None, description="Car image URLs")
    model_config = ConfigDict(from_attributes=True)


class PaymentPublicBooking(BaseModel):
    """
    Schema for payment details in booking context.
    """
    id: int = Field(..., description="Payment ID")
    amount_inr: Decimal = Field(..., description="Amount")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    payment_type: PaymentType = Field(..., description="Payment type")
    status: StatusGeneric = Field(..., description="Payment status")
    transaction_id: str = Field(..., description="Transaction ID")
    razorpay_order_id: str = Field(..., description="Razorpay order ID")
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID")
    razorpay_signature: str = Field(..., description="Razorpay signature")
    created_at: datetime = Field(..., description="Created at")
    remarks: Optional[str] = Field(None, description="Remarks")
    model_config = ConfigDict(from_attributes=True)


class ReviewCreate(BaseModel):
    """
    Schema for creating a review for a booking.
    """
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    remarks: Optional[str] = Field(None, description="Review remarks")


class ReviewPublic(ReviewCreate):
    """
    Schema for public review details.
    """
    id: int = Field(..., description="Review ID")
    created_at: datetime = Field(..., description="Created at")
    created_by: str = Field(..., description="Created by")
    model_config = ConfigDict(from_attributes=True)


class UserBookingDetails(BaseModel):
    """
    Schema for user details in booking context.
    """
    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email")
    created_at: datetime = Field(..., description="User account created at")

    # Customer profile details
    name: Optional[str] = Field(None, description="Customer full name")
    phone: Optional[str] = Field(None, description="Customer phone number")
    dob: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[str] = Field(None, description="Gender")
    profile_url: Optional[str] = Field(None, description="Profile picture URL")

    # Address details
    address: Optional[Dict[str, Any]] = Field(
        None, description="Customer address details"
    )

    # KYC details
    aadhaar_no: Optional[str] = Field(None, description="Aadhaar number (masked)")
    license_no: Optional[str] = Field(None, description="License number")
    is_verified: Optional[bool] = Field(None, description="KYC verification status")

    # Customer category
    tag: Optional[str] = Field(None, description="Customer tag (ROOKIE/TRAVELER/PRO)")
    rookie_benefit_used: Optional[bool] = Field(
        None, description="Whether rookie benefit has been used"
    )

    # Referral info
    referral_code: Optional[str] = Field(None, description="User's referral code")
    total_referrals: Optional[int] = Field(
        None, description="Total successful referrals"
    )

    model_config = ConfigDict(from_attributes=True)


class BookingBase(BaseModel):
    """
    Schema for base booking information.
    """
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    remarks: Optional[str] = Field(None, description="Remarks")


class BookingPublic(BookingBase):
    """
    Schema for public booking information.
    """
    id: int = Field(..., description="Booking ID")
    car_id: int = Field(..., description="Car ID")
    booking_status: StatusGeneric = Field(..., description="Booking status")
    payment_status: Optional[StatusGeneric] = Field(None, description="Payment status")
    created_at: datetime = Field(..., description="Created at")
    model_config = ConfigDict(from_attributes=True)


class BookingResponse(BookingPublic):
    """
    Schema for booking response including payment summary, car details, and locations.
    """
    payment_summary: PaymentSummary = Field(..., description="Payment summary")
    car: CarBookingDetails = Field(..., description="Car details")
    pickup_location: LocationPublic = Field(..., description="Pickup location")
    delivery_location: LocationPublic = Field(..., description="Delivery location")


class BookingDetailed(BookingResponse):
    """
    Schema for detailed booking information including payments and review.
    """
    payments: List[PaymentPublicBooking] = Field(
        default_factory=list, description="Payments"
    )
    review: Optional[ReviewPublic] = Field(None, description="Review")
    delivery_otp: Optional[str] = Field(None, description="Delivery OTP")
    pickup_otp: Optional[str] = Field(None, description="Pickup OTP")


class BookingAdminDetailed(BookingDetailed):
    """
    Schema for admin detailed booking information including user and cancellation details.
    """
    booked_by: str = Field(..., description="Booked by user ID")
    booker: Optional[UserBookingDetails] = Field(None, description="Booker details")
    cancelled_at: Optional[datetime] = Field(None, description="Cancelled at")
    cancelled_by: Optional[str] = Field(None, description="Cancelled by")
    cancellation_reason: Optional[str] = Field(None, description="Cancellation reason")


class OTPResponse(BaseModel):
    """
    Schema for OTP response.
    """
    otp: str = Field(..., description="6-digit OTP")
    generated_at: datetime = Field(..., description="When OTP was generated")
    message: str = Field(..., description="Instruction message")


class VideoUpload(BaseModel):
    """
    Schema for video upload information.
    """
    video_url: str = Field(..., description="Video URL")


class VideoUploadSASResponse(BaseModel):
    """
    Schema for video upload SAS URL response.
    """
    sas_url: str = Field(
        ..., description="Short-lived SAS URL for uploading video (use this to upload)"
    )
    blob_url: str = Field(
        ...,
        description="Blob URL without SAS token (send this back to backend after upload)",
    )
    blob_name: str = Field(..., description="Blob name for the video")
    expires_at: datetime = Field(..., description="SAS URL expiration time")
    container_name: str = Field(..., description="Azure container name")


class OTPVerify(BaseModel):
    """
    Schema for verifying OTP.
    """
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP")


class ProcessDeliveryInput(BaseModel):
    """
    Schema for processing delivery input.
    """
    delivery_video_url: str = Field(..., description="Delivery video URL")
    start_kilometers: int = Field(..., ge=0, description="Start kilometers")


class ExtraChargeItem(BaseModel):
    """
    Schema for an extra charge item.
    """
    type: str = Field(..., description="Charge type")
    amount: Decimal = Field(..., ge=0, description="Amount")
    specification: str = Field(..., description="Charge specification")
    calculation_details: Optional[str] = Field(None, description="Calculation details")


class ReturnRequest(BaseModel):
    """
    Schema for requesting a return of the car.
    """
    expected_return_time: datetime = Field(..., description="Expected return time")
    remarks: Optional[str] = Field(
        None, max_length=500, description="Additional remarks"
    )

    @field_validator("expected_return_time")
    @classmethod
    def validate_time_interval(cls, v: datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v.minute not in [0, 30]:
            raise ValueError("Return time must be in :00 or :30 minute intervals")
        return v


class ReturnRequestResponse(BaseModel):
    """
    Schema for return request response.
    """
    message: str = Field(..., description="Success message")
    booking_id: int = Field(..., description="Booking ID")
    status: str = Field(..., description="New booking status")
    expected_return_time: datetime = Field(..., description="Expected return time")


class ProcessReturnInput(BaseModel):
    """
    Schema for processing return input.
    """
    pickup_video_url: str = Field(..., description="Pickup video URL")
    end_kilometers: int = Field(..., ge=0, description="End kilometers")
    returned_at: datetime = Field(..., description="Actual return timestamp")
    extra_charges: List[ExtraChargeItem] = Field(
        default_factory=list, description="Extra charges"
    )
    settlement_remarks: Optional[str] = Field(None, description="Settlement remarks")


class CancelBooking(BaseModel):
    """
    Schema for cancelling a booking.
    """
    reason: str = Field(
        ..., min_length=1, max_length=500, description="Cancellation reason"
    )


class AdminCancelBooking(CancelBooking):
    """
    Schema for admin cancelling a booking.
    """
    admin_notes: str = Field(..., description="Admin notes")


class PaymentInitiationRequest(BaseModel):
    """
    Schema for initiating a payment for a booking.
    """
    freeze_id: int = Field(..., description="Freeze ID from freeze-booking")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    transaction_id: str = Field(..., description="Transaction ID")
    razorpay_order_id: Optional[str] = Field(None, description="Razorpay order ID")
    razorpay_payment_id: Optional[str] = Field(None, description="Razorpay payment ID")
    razorpay_signature: Optional[str] = Field(None, description="Razorpay signature")
    remarks: Optional[str] = Field(None, description="Additional remarks")


class BookingFilterParams(BaseModel):
    """
    Schema for filtering bookings.
    """
    search: Optional[str] = None,
    payment_status: Optional[PaymentStatusEnum] = None,
    booking_status: Optional[StatusEnum] = None,
    review_rating: Optional[int] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "DESC",


class Msg(BaseModel):
    """
    Schema for generic message response.
    """
    message: str = Field(..., description="Message")


class LocationGeocodeRequest(BaseModel):
    """
    Schema for location geocode request.
    """
    booking_id: int = Field(..., description="Booking ID")


class LocationGeocodeResponse(BaseModel):
    """
    Schema for location geocode response.
    """
    booking_id: int = Field(..., description="Booking ID")
    latitude: float = Field(..., description="Latitude")
    longitude: float = Field(..., description="Longitude")
    address: Optional[str] = Field(None, description="Address")
    location_type: str = Field(..., description="pickup or delivery")


class PaginatedResponse(BaseModel):
    """
    Schema for paginated response.
    """
    total: int = Field(..., description="Total count")
    items: List[Any] = Field(..., description="List of items")
    skip: int = Field(..., description="Skip count")
    limit: int = Field(..., description="Limit count")
