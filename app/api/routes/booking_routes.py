from fastapi import APIRouter, Depends, Security, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional


from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import booking_service


router = APIRouter()


@router.post("/freeze-booking", response_model=schemas.EstimateResponse)
async def freeze_booking(
    freeze_in: schemas.FreezeCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["bookings-freeze:create"]
    ),
):
    """
    Freeze a booking with initial booking details and get estimate.

    Args:
        freeze_in: Freeze booking data with car and time details
        db: Database session dependency
        current_user: Authenticated user with bookings-freeze:create permission

    Returns:
        Booking estimate with pricing and freeze details
    """
    return await booking_service.freeze_booking(db, freeze_in, current_user.id)


@router.get("", response_model=schemas.PaginatedResponse)
async def get_my_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(
        None, description="Search in car info (color, model, car_no)"
    ),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    booking_status: Optional[str] = Query(None, description="Filter by booking status"),
    review_rating: Optional[int] = Query(
        None, ge=1, le=5, description="Filter by review rating (1-5)"
    ),
    sort_by: str = Query(
        "start_time", description="Sort by field: start_time, end_time, created_at"
    ),
    sort_order: str = Query("DESC", description="Sort order: ASC or DESC"),
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:read"]),
):
    """
    Get paginated bookings for current user with filtering and sorting.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search in car info
        payment_status: Filter by payment status
        booking_status: Filter by booking status
        review_rating: Filter by review rating
        sort_by: Sort by field
        sort_order: Sort order
        db: Database session dependency
        current_user: Authenticated user with bookings:read permission

    Returns:
        Paginated response with bookings and metadata
    """
    filters = schemas.BookingFilterParams(
        search=search,
        payment_status=payment_status,
        booking_status=booking_status,
        review_rating=review_rating,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await booking_service.get_user_bookings(
        db, current_user.id, skip, limit, filters
    )


@router.get("/freeze-booking/{freeze_id}", response_model=schemas.FreezeBookingResponse)
async def get_freeze_booking(
    freeze_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["bookings-freeze:read"]
    ),
):
    """
    Get details of a specific frozen booking.

    Args:
        freeze_id: Unique identifier of the frozen booking
        db: Database session dependency
        current_user: Authenticated user with bookings-freeze:read permission

    Returns:
        Frozen booking details with estimate information
    """
    return await booking_service.get_freeze_booking(db, freeze_id, current_user.id)


@router.get(
    "/export",
    response_class=StreamingResponse,
)
async def export_my_bookings(
    search: Optional[str] = Query(
        None, description="Search in car info (color, model, car_no)"
    ),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    booking_status: Optional[str] = Query(None, description="Filter by booking status"),
    review_rating: Optional[int] = Query(
        None, ge=1, le=5, description="Filter by review rating (1-5)"
    ),
    sort_by: str = Query(
        "start_time", description="Sort by field: start_time, end_time, created_at"
    ),
    sort_order: str = Query("DESC", description="Sort order: ASC or DESC"),
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:read"]),
):
    """
    Export current user's bookings to CSV with filtering and sorting.

    Args:
        search: Search in car info
        payment_status: Filter by payment status
        booking_status: Filter by booking status
        review_rating: Filter by review rating
        sort_by: Sort by field
        sort_order: Sort order
        db: Database session dependency
        current_user: Authenticated user with bookings:read permission

    Returns:
        Streaming CSV file with booking data
    """
    filters = schemas.BookingFilterParams(
        search=search,
        payment_status=payment_status,
        booking_status=booking_status,
        review_rating=review_rating,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await booking_service.export_user_bookings(db, current_user.id, filters)


@router.get("/admin", response_model=schemas.PaginatedResponse)
async def get_all_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(
        None, description="Search in car info, user_id, username, tag"
    ),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    booking_status: Optional[str] = Query(None, description="Filter by booking status"),
    review_rating: Optional[int] = Query(
        None, ge=1, le=5, description="Filter by review rating (1-5)"
    ),
    sort_by: str = Query(
        "start_time", description="Sort by field: start_time, end_time, created_at"
    ),
    sort_order: str = Query("DESC", description="Sort order: ASC or DESC"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:read_all"]),
):
    """
    Admin endpoint to get all bookings with filtering and sorting.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search in car info, user_id, username, tag
        payment_status: Filter by payment status
        booking_status: Filter by booking status
        review_rating: Filter by review rating
        sort_by: Sort by field
        sort_order: Sort order
        db: Database session dependency

    Returns:
        Paginated response with all bookings and metadata
    """
    filters = schemas.BookingFilterParams(
        search=search,
        payment_status=payment_status,
        booking_status=booking_status,
        review_rating=review_rating,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await booking_service.get_all_bookings(db, skip, limit, filters)


@router.get(
    "/admin/export",
    response_class=StreamingResponse,
)
async def export_all_bookings(
    search: Optional[str] = Query(
        None, description="Search in car info, user_id, username, tag"
    ),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    booking_status: Optional[str] = Query(None, description="Filter by booking status"),
    review_rating: Optional[int] = Query(
        None, ge=1, le=5, description="Filter by review rating (1-5)"
    ),
    sort_by: str = Query(
        "start_time", description="Sort by field: start_time, end_time, created_at"
    ),
    sort_order: str = Query("DESC", description="Sort order: ASC or DESC"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:read_all"]),
):
    """
    Admin endpoint to export all bookings to CSV with filtering.

    Args:
        search: Search in car info, user_id, username, tag
        payment_status: Filter by payment status
        booking_status: Filter by booking status
        review_rating: Filter by review rating
        sort_by: Sort by field
        sort_order: Sort order
        db: Database session dependency

    Returns:
        Streaming CSV file with all booking data
    """
    filters = schemas.BookingFilterParams(
        search=search,
        payment_status=payment_status,
        booking_status=booking_status,
        review_rating=review_rating,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await booking_service.export_all_bookings(db, filters)


@router.post("/admin/pickup-location", response_model=schemas.LocationGeocodeResponse)
async def get_pickup_location_address(
    request: schemas.LocationGeocodeRequest,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:read_all"]),
):
    """
    Admin endpoint to get geocoded address for pickup location.

    Args:
        request: Request containing booking_id
        db: Database session dependency

    Returns:
        Geocoded address information for pickup location
    """
    return await booking_service.get_pickup_location_address(db, request.booking_id)


@router.post("/admin/delivery-location", response_model=schemas.LocationGeocodeResponse)
async def get_delivery_location_address(
    request: schemas.LocationGeocodeRequest,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:read_all"]),
):
    """
    Admin endpoint to get geocoded address for delivery location.

    Args:
        request: Request containing booking_id
        db: Database session dependency

    Returns:
        Geocoded address information for delivery location
    """
    return await booking_service.get_delivery_location_address(db, request.booking_id)


@router.put(
    "/freeze/{freeze_id}/update-locations", response_model=schemas.EstimateResponse
)
async def update_freeze_locations(
    freeze_id: int,
    update_in: schemas.FreezeUpdate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:create"]),
):
    """
    Update pickup and delivery locations for a frozen booking.

    Args:
        freeze_id: Unique identifier of the frozen booking
        update_in: Updated location data
        db: Database session dependency
        current_user: Authenticated user with bookings:create permission

    Returns:
        Updated estimate with new location information
    """
    return await booking_service.update_freeze_locations(
        db, freeze_id, update_in, current_user.id
    )


@router.delete("/freeze/{freeze_id}", response_model=schemas.Msg)
async def cancel_freeze(
    freeze_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:create"]),
):
    """
    Cancel a frozen booking before it becomes a confirmed booking.

    Args:
        freeze_id: Unique identifier of the frozen booking
        db: Database session dependency
        current_user: Authenticated user with bookings:create permission

    Returns:
        Success message confirming cancellation
    """
    return await booking_service.cancel_freeze(db, freeze_id, current_user.id)


@router.get("/{booking_id}", response_model=schemas.BookingDetailed)
async def get_booking(
    booking_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:read"]),
):
    """
    Get detailed information for a specific booking.

    Args:
        booking_id: Unique identifier of the booking
        db: Database session dependency
        current_user: Authenticated user with bookings:read permission

    Returns:
        Detailed booking information including car and payment details
    """
    return await booking_service.get_booking_details(db, booking_id, current_user.id)


@router.get(
    "/admin/{booking_id}/get-video-upload-url",
    response_model=schemas.VideoUploadSASResponse,
)
async def get_video_upload_sas_url(
    booking_id: int,
    video_type: str = Query(..., description="Type of video: 'delivery' or 'pickup'"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:update_all"]),
):
    """
    Admin endpoint to get SAS URL for video upload to Azure Blob Storage.

    Args:
        booking_id: Unique identifier of the booking
        video_type: Type of video (delivery or pickup)
        db: Database session dependency

    Returns:
        SAS URL for direct video upload to blob storage
    """
    return await booking_service.generate_video_upload_sas_url(
        db, booking_id, video_type, None
    )


@router.post("/admin/{booking_id}/process-delivery", response_model=schemas.Msg)
async def process_delivery(
    booking_id: int,
    delivery_data: schemas.ProcessDeliveryInput,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:update_all"]),
):
    """
    Admin endpoint to process car delivery with video and kilometers.

    Args:
        booking_id: Unique identifier of the booking
        delivery_data: Delivery data including video URL and start kilometers
        db: Database session dependency

    Returns:
        Success message with OTP generation confirmation
    """
    return await booking_service.process_delivery(db, booking_id, delivery_data)


@router.get("/{booking_id}/delivery-otp", response_model=schemas.OTPResponse)
async def get_delivery_otp(
    booking_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:read"]),
):
    """
    Customer endpoint to get delivery OTP for admin verification.

    Args:
        booking_id: Unique identifier of the booking
        db: Database session dependency
        current_user: Authenticated user with bookings:read permission

    Returns:
        OTP response with delivery verification code
    """
    return await booking_service.get_delivery_otp(db, booking_id, current_user.id)


@router.get("/{booking_id}/pickup-otp", response_model=schemas.OTPResponse)
async def get_pickup_otp(
    booking_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:read"]),
):
    """
    Customer endpoint to get pickup OTP for admin verification.

    Args:
        booking_id: Unique identifier of the booking
        db: Database session dependency
        current_user: Authenticated user with bookings:read permission

    Returns:
        OTP response with pickup verification code
    """
    return await booking_service.get_pickup_otp(db, booking_id, current_user.id)


@router.post(
    "/{booking_id}/request-return", response_model=schemas.ReturnRequestResponse
)
async def request_return(
    booking_id: int,
    return_request: schemas.ReturnRequest,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:update"]),
):
    """
    Customer endpoint to request car return with time and location.

    Args:
        booking_id: Unique identifier of the booking
        return_request: Return request with expected time and pickup location
        db: Database session dependency
        current_user: Authenticated user with bookings:update permission

    Returns:
        Confirmation response with return request details
    """
    return await booking_service.request_return(
        db, booking_id, return_request, current_user.id
    )


@router.post(
    "/admin/{booking_id}/verify-pickup", response_model=schemas.BookingAdminDetailed
)
async def verify_pickup_otp(
    booking_id: int,
    otp_data: schemas.OTPVerify,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:update_all"]),
):
    """
    Admin endpoint to verify pickup OTP provided by customer.

    Args:
        booking_id: Unique identifier of the booking
        otp_data: OTP verification data
        db: Database session dependency

    Returns:
        Updated booking details after successful verification
    """
    return await booking_service.verify_pickup_otp(db, booking_id, otp_data)


@router.post("/{booking_id}/cancel", response_model=schemas.Msg)
async def cancel_booking(
    booking_id: int,
    cancel_data: schemas.CancelBooking,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:update"]),
):
    """
    Customer endpoint to cancel a booking with reason.

    Args:
        booking_id: Unique identifier of the booking
        cancel_data: Cancellation data including reason
        db: Database session dependency
        current_user: Authenticated user with bookings:update permission

    Returns:
        Success message confirming cancellation
    """
    return await booking_service.cancel_booking(
        db, booking_id, current_user.id, cancel_data.reason
    )


@router.post("/{booking_id}/complete", response_model=schemas.BookingDetailed)
async def complete_booking_with_review(
    booking_id: int,
    review_in: schemas.ReviewCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["bookings:create"]),
):
    """
    Customer endpoint to complete booking and submit review.

    Args:
        booking_id: Unique identifier of the booking
        review_in: Review data including rating and comment
        db: Database session dependency
        current_user: Authenticated user with bookings:create permission

    Returns:
        Completed booking details with review
    """
    return await booking_service.complete_booking_with_review(
        db, booking_id, review_in, current_user.id
    )


@router.get("/admin/{booking_id}", response_model=schemas.BookingAdminDetailed)
async def get_booking_admin(
    booking_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:read_all"]),
):
    """
    Admin endpoint to get detailed booking information with admin fields.

    Args:
        booking_id: Unique identifier of the booking
        db: Database session dependency

    Returns:
        Detailed booking information with admin-specific fields
    """
    return await booking_service.get_booking_details(db, booking_id, "ADMIN")


@router.post(
    "/admin/{booking_id}/verify-delivery", response_model=schemas.BookingAdminDetailed
)
async def verify_delivery_otp(
    booking_id: int,
    otp_data: schemas.OTPVerify,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:update_all"]),
):
    """
    Admin endpoint to verify delivery OTP provided by customer.

    Args:
        booking_id: Unique identifier of the booking
        otp_data: OTP verification data
        db: Database session dependency

    Returns:
        Updated booking details after successful verification
    """
    return await booking_service.verify_delivery_otp(db, booking_id, otp_data)


@router.post(
    "/admin/{booking_id}/process-return", response_model=schemas.BookingAdminDetailed
)
async def process_return(
    booking_id: int,
    return_data: schemas.ProcessReturnInput,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:update_all"]),
):
    """
    Admin endpoint to process car return with video and end kilometers.

    Args:
        booking_id: Unique identifier of the booking
        return_data: Return data including video URL and end kilometers
        db: Database session dependency

    Returns:
        Updated booking details after processing return
    """
    return await booking_service.process_return(db, booking_id, return_data)


@router.post("/admin/{booking_id}/cancel", response_model=schemas.Msg)
async def admin_cancel_booking(
    booking_id: int,
    cancel_data: schemas.AdminCancelBooking,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:update_all"]),
):
    """
    Admin endpoint to cancel a booking with reason and notes.

    Args:
        booking_id: Unique identifier of the booking
        cancel_data: Admin cancellation data including reason and notes
        db: Database session dependency

    Returns:
        Success message confirming cancellation
    """
    return await booking_service.admin_cancel_booking(
        db, booking_id, cancel_data.reason, cancel_data.admin_notes, _.id
    )
