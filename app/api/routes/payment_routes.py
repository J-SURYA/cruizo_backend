from fastapi import APIRouter, Depends, Security, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date


from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import payment_service
from app.services import booking_service


router = APIRouter()


@router.post("/customers/initiate-from-freeze", response_model=schemas.BookingDetailed)
async def initiate_payment_from_freeze(
    payment_in: schemas.PaymentInitiationRequest,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["bookings:create", "payments:create"]
    ),
):
    """
    Initiate payment from frozen booking.

    Args:
        payment_in: Payment initiation details
        db: Database session dependency
        current_user: Authenticated user with required permissions

    Returns:
        Detailed booking information with payment initiated
    """
    return await payment_service.initiate_payment_from_freeze(
        db, payment_in, current_user.id
    )


@router.get(
    "/customers/export",
    response_class=StreamingResponse,
)
async def export_my_payments(
    search: Optional[str] = None,
    status: Optional[str] = None,
    payment_type: Optional[schemas.PaymentType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Export current user's payments to Excel.

    Args:
        search: Search term for filtering payments
        status: Filter by payment status
        payment_type: Filter by payment type
        start_date: Filter by start date
        end_date: Filter by end date
        db: Database session dependency
        current_user: Authenticated user

    Returns:
        Streaming Excel file with user's payment data
    """
    filters = schemas.PaymentFilterParams(
        search=search,
        status=status,
        payment_type=payment_type,
        start_date=start_date,
        end_date=end_date,
        sort="created_at_desc",
    )
    return await payment_service.export_user_payments(db, current_user.id, filters)


@router.post("/customers/payment/{payment_id}/confirm", response_model=schemas.Msg)
async def confirm_payment(
    payment_id: int,
    confirm_in: schemas.PaymentConfirmRequest,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["payments:update"]),
):
    """
    Confirm payment by customer.

    Args:
        payment_id: ID of the payment to confirm
        confirm_in: Payment confirmation details
        db: Database session dependency
        current_user: Authenticated user

    Returns:
        Success message
    """
    return await payment_service.confirm_payment(
        db, payment_id, current_user.id, confirm_in
    )


@router.get("/customers", response_model=schemas.PaginatedResponse)
async def get_my_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    payment_type: Optional[schemas.PaymentType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sort: str = Query("created_at_desc"),
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Get current user's payments with pagination and filtering.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for filtering
        status: Filter by payment status
        payment_type: Filter by payment type
        start_date: Filter by start date
        end_date: Filter by end date
        sort: Sort order
        db: Database session dependency
        current_user: Authenticated user

    Returns:
        Paginated list of user's payments
    """
    filters = schemas.PaymentFilterParams(
        search=search,
        status=status,
        payment_type=payment_type,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
    )
    return await payment_service.get_user_payments(
        db, current_user.id, skip, limit, filters
    )


@router.get(
    "/customers/booking/{booking_id}/payments",
    response_model=List[schemas.PaymentPublic],
)
async def get_payments_by_booking_id(
    booking_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Get all payments for specific booking.

    Args:
        booking_id: ID of the booking
        db: Database session dependency
        current_user: Authenticated user

    Returns:
        List of payments associated with the booking
    """
    return await payment_service.get_payments_by_booking_id(
        db, booking_id, current_user.id
    )


@router.get("/customers/{payment_id}", response_model=schemas.PaymentDetailed)
async def get_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Get payment details by ID.

    Args:
        payment_id: ID of the payment
        db: Database session dependency
        current_user: Authenticated user

    Returns:
        Detailed payment information
    """
    return await payment_service.get_payment_details(db, payment_id, current_user.id)


@router.get(
    "/customers/booking/{booking_id}/initiated-payment",
    response_model=schemas.PaymentPublic,
)
async def get_initiated_payment_for_booking(
    booking_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Get initiated payment for specific booking.

    Args:
        booking_id: ID of the booking
        db: Database session dependency
        current_user: Authenticated user

    Returns:
        Initiated payment details for the booking
    """
    return await payment_service.get_initiated_payment_for_user(
        db, booking_id, current_user.id
    )


@router.get("/customers/booking/{booking_id}/payment-summary", response_model=dict)
async def get_booking_payment_summary(
    booking_id: int,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Get payment summary for specific booking.

    Args:
        booking_id: ID of the booking
        db: Database session dependency
        current_user: Authenticated user

    Returns:
        Payment summary including total amount, paid amount, and outstanding
    """
    return await booking_service.get_booking_payment_summary(
        db, booking_id, current_user.id
    )


@router.get(
    "/admin/export",
    response_class=StreamingResponse,
)
async def export_all_payments(
    search: Optional[str] = None,
    status: Optional[str] = None,
    payment_type: Optional[schemas.PaymentType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Export all payments to Excel for admin.

    Args:
        search: Search term for filtering
        status: Filter by payment status
        payment_type: Filter by payment type
        start_date: Filter by start date
        end_date: Filter by end date
        db: Database session dependency

    Returns:
        Streaming Excel file with all payment data
    """
    filters = schemas.PaymentFilterParams(
        search=search,
        status=status,
        payment_type=payment_type,
        start_date=start_date,
        end_date=end_date,
        sort="created_at_desc",
    )
    return await payment_service.export_all_payments(db, filters)


@router.get("/admin/refunding", response_model=schemas.PaginatedResponse)
async def get_refunding_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sort: str = Query("created_at_desc"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Get all refunding payments for admin.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for filtering
        start_date: Filter by start date
        end_date: Filter by end date
        sort: Sort order
        db: Database session dependency

    Returns:
        Paginated list of refunding payments
    """
    filters = schemas.PaymentFilterParams(
        search=search,
        status="REFUNDING",
        payment_type=None,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
    )
    return await payment_service.get_refunding_payments_for_admin(
        db, skip, limit, filters
    )


@router.get("/admin", response_model=schemas.PaginatedResponse)
async def get_all_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    payment_type: Optional[schemas.PaymentType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sort: str = Query("created_at_desc"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Get all payments for admin with pagination and filtering.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for filtering
        status: Filter by payment status
        payment_type: Filter by payment type
        start_date: Filter by start date
        end_date: Filter by end date
        sort: Sort order
        db: Database session dependency

    Returns:
        Paginated list of all payments
    """
    filters = schemas.PaymentFilterParams(
        search=search,
        status=status,
        payment_type=payment_type,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
    )
    return await payment_service.get_all_payments(db, skip, limit, filters)


@router.post("/admin/refund/{payment_id}/confirm", response_model=schemas.Msg)
async def confirm_refund(
    payment_id: int,
    confirm_in: schemas.PaymentConfirmRequest,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["payments:update"]),
):
    """
    Confirm refund for payment.

    Args:
        payment_id: ID of the payment to refund
        confirm_in: Refund confirmation details
        db: Database session dependency

    Returns:
        Success message
    """
    return await payment_service.confirm_refund(db, payment_id, confirm_in)


@router.get("/admin/{payment_id}", response_model=schemas.PaymentDetailed)
async def get_payment_admin(
    payment_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["payments:read"]),
):
    """
    Get payment details by ID for admin.

    Args:
        payment_id: ID of the payment
        db: Database session dependency

    Returns:
        Detailed payment information
    """
    return await payment_service.get_payment_details(db, payment_id, "ADMIN")


@router.get(
    "/admin/{booking_id}/payment-summary", response_model=schemas.PaymentSummary
)
async def get_booking_payment_summary_admin(
    booking_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:read_all"]),
):
    """
    Get payment summary for booking admin view.

    Args:
        booking_id: ID of the booking
        db: Database session dependency

    Returns:
        Payment summary with total, paid, and outstanding amounts
    """
    return await booking_service.get_booking_payment_summary(db, booking_id, "ADMIN")
