from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timezone
from decimal import Decimal
import logging
import io
import csv
from fastapi.responses import StreamingResponse


from app import models, schemas
from app.crud import payment_crud, booking_crud, rbac_crud
from app.utils import notification_utils
from app.utils.exception_utils import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from .booking_services import booking_service


logger = logging.getLogger(__name__)


class PaymentService:
    """
    Service class for handling payment operations.
    """
    def _validate_payment_ownership(self, payment_data: dict, user_id: str):
        """Validate payment ownership.
        
        Args:
            payment_data: Payment data dictionary
            user_id: User ID to validate against
        
        Returns:
            None
        """
        if payment_data["booking"]["booked_by"] != user_id:
            raise ForbiddenException("Can only access your own payments")


    def _validate_payment_status(self, payment_data: dict, expected_status: str):
        """Validate payment status.
        
        Args:
            payment_data: Payment data dictionary
            expected_status: Expected payment status
        
        Returns:
            None
        """
        if payment_data["status"] != expected_status:
            raise BadRequestException(f"Payment must be in {expected_status} status")


    def _validate_booking_status(self, booking_data: dict, expected_status: str):
        """Validate booking status.
        
        Args:
            booking_data: Booking data dictionary
            expected_status: Expected booking status
        
        Returns:
            None
        """
        if booking_data["booking_status"] != expected_status:
            raise BadRequestException(f"Booking must be in {expected_status} status")


    def _validate_booking_payment_status(
        self, booking_data: dict, expected_status: str
    ):
        """Validate booking payment status.
        
        Args:
            booking_data: Booking data dictionary
            expected_status: Expected payment status
        
        Returns:
            None
        """
        if booking_data["payment_status"] != expected_status:
            raise BadRequestException(
                f"Booking payment status must be {expected_status}"
            )

    async def export_all_payments(
        self, db: AsyncSession, filters: schemas.PaymentFilterParams
    ) -> StreamingResponse:
        """Export all payments to CSV.
        
        Args:
            db: Database session
            filters: Payment filter parameters
        
        Returns:
            StreamingResponse containing CSV file
        """
        payments_data, _ = await payment_crud.get_all_payments_data(
            db, 0, 10000, filters
        )

        csv_data = self._prepare_payments_csv_data(
            payments_data, include_customer_info=True
        )

        csv_file = io.StringIO()

        fieldnames = csv_data[0].keys() if csv_data else []
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

        response = StreamingResponse(
            iter([csv_file.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=all_payments_export.csv"
            },
        )

        return response


    async def export_user_payments(
        self, db: AsyncSession, user_id: str, filters: schemas.PaymentFilterParams
    ) -> StreamingResponse:
        """Export user payments to CSV.
        
        Args:
            db: Database session
            user_id: User ID
            filters: Payment filter parameters
        
        Returns:
            StreamingResponse containing CSV file
        """
        payments_data, _ = await payment_crud.get_user_payments_data(
            db, user_id, 0, 10000, filters
        )

        csv_data = self._prepare_payments_csv_data(
            payments_data, include_customer_info=False
        )

        csv_file = io.StringIO()

        fieldnames = csv_data[0].keys() if csv_data else []
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

        response = StreamingResponse(
            iter([csv_file.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=my_payments_export.csv"
            },
        )

        return response


    def _prepare_payments_csv_data(
        self, payments_data: List[dict], include_customer_info: bool = True
    ) -> List[dict]:
        """Prepare payments data for CSV export.
        
        Args:
            payments_data: List of payment data dictionaries
            include_customer_info: Whether to include customer information
        
        Returns:
            List of dictionaries formatted for CSV export
        """
        csv_rows = []

        all_fieldnames = set(
            [
                "Payment ID",
                "Transaction ID",
                "Amount (INR)",
                "Payment Method",
                "Payment Type",
                "Payment Status",
                "Remarks",
                "Created At",
                "Booking ID",
                "Car Number",
                "Car Model",
            ]
        )

        if include_customer_info:
            all_fieldnames.update(
                ["Customer ID", "Customer Email", "Customer Name", "Customer Username"]
            )

        all_fieldnames.update(["Razorpay Order ID", "Razorpay Payment ID"])

        fieldnames_list = sorted(all_fieldnames)

        for payment in payments_data:
            row = {
                "Payment ID": payment["id"],
                "Transaction ID": payment["transaction_id"],
                "Amount (INR)": float(payment["amount_inr"]),
                "Payment Method": (
                    payment["payment_method"].value
                    if payment["payment_method"]
                    else "N/A"
                ),
                "Payment Type": (
                    payment["payment_type"].value if payment["payment_type"] else "N/A"
                ),
                "Payment Status": payment["status"],
                "Remarks": payment["remarks"] or "N/A",
                "Created At": (
                    payment["created_at"].isoformat()
                    if payment["created_at"]
                    else "N/A"
                ),
                "Booking ID": payment["booking"]["id"] if payment["booking"] else "N/A",
                "Car Number": (
                    payment["booking"]["car"]["car_no"]
                    if payment["booking"] and payment["booking"]["car"]
                    else "N/A"
                ),
                "Car Model": (
                    f"{payment['booking']['car']['car_model']['brand']} {payment['booking']['car']['car_model']['model']}"
                    if payment["booking"]
                    and payment["booking"]["car"]
                    and payment["booking"]["car"]["car_model"]
                    else "N/A"
                ),
                "Razorpay Order ID": payment.get("razorpay_order_id") or "N/A",
                "Razorpay Payment ID": payment.get("razorpay_payment_id") or "N/A",
            }

            if (
                include_customer_info
                and payment["booking"]
                and payment["booking"]["booker"]
            ):
                row.update(
                    {
                        "Customer ID": payment["booking"]["booker"]["id"],
                        "Customer Email": payment["booking"]["booker"]["email"],
                        "Customer Name": payment["booking"]["booker"]["customer_name"]
                        or "N/A",
                        "Customer Username": payment["booking"]["booker"]["username"],
                    }
                )

            for field in fieldnames_list:
                if field not in row:
                    row[field] = "N/A"

            csv_rows.append(row)

        return csv_rows


    async def initiate_payment_from_freeze(
        self,
        db: AsyncSession,
        payment_in: schemas.PaymentInitiationRequest,
        user_id: str,
    ) -> schemas.BookingDetailed:
        """Initiate payment from freeze and create booking.
        
        Args:
            db: Database session
            payment_in: Payment initiation request data
            user_id: User ID
        
        Returns:
            Detailed booking information
        """
        booking = await booking_service.create_booking_from_freeze(
            db, payment_in.freeze_id, payment_in, user_id
        )

        total_amount = Decimal("0.0")
        if booking.payment_summary and booking.payment_summary.charges_breakdown:
            total_amount = Decimal(
                str(booking.payment_summary.charges_breakdown["total_payable"])
            )

        await self.create_payment(
            db,
            booking_id=booking.id,
            amount=total_amount,
            user_id=user_id,
            payment_method=payment_in.payment_method,
            payment_type=models.PaymentType.PAYMENT,
            status=models.PaymentStatusEnum.PAID,
            transaction_id=payment_in.transaction_id,
            razorpay_order_id=payment_in.razorpay_order_id,
            razorpay_payment_id=payment_in.razorpay_payment_id,
            razorpay_signature=payment_in.razorpay_signature,
            remarks=payment_in.remarks or "Initial booking payment",
        )

        return await booking_service.get_booking_details(db, booking.id, user_id)


    async def create_payment(
        self,
        db: AsyncSession,
        booking_id: int,
        amount: Decimal,
        user_id: str,
        payment_method: models.PaymentMethod,
        payment_type: models.PaymentType,
        status: models.PaymentStatusEnum,
        transaction_id: str,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        remarks: str = None,
    ) -> schemas.PaymentPublic:
        """Create a new payment record.
        
        Args:
            db: Database session
            booking_id: Booking ID
            amount: Payment amount
            user_id: User ID
            payment_method: Payment method
            payment_type: Payment type
            status: Payment status
            transaction_id: Transaction ID
            razorpay_order_id: Razorpay order ID
            razorpay_payment_id: Razorpay payment ID
            razorpay_signature: Razorpay signature
            remarks: Optional remarks
        
        Returns:
            Created payment public data
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if (
            payment_type == models.PaymentType.PAYMENT
            or payment_type == models.PaymentType.ADD_PAYMENT
        ) and booking_data["booked_by"] != user_id:
            raise ForbiddenException("Cannot create payment for another user's booking")

        status_obj = await rbac_crud.get_status_by_name(db, status)
        if not status_obj:
            raise NotFoundException(f"{status} status not found")

        current_timestamp = int(datetime.now(timezone.utc).timestamp())
        if not transaction_id:
            transaction_id = (
                f"DUMMY_TXN_{booking_id}_{current_timestamp}_{payment_type.value}"
            )
        if not razorpay_order_id:
            razorpay_order_id = (
                f"DUMMY_ORDER_{booking_id}_{current_timestamp}_{payment_type.value}"
            )
        if not razorpay_payment_id:
            razorpay_payment_id = (
                f"DUMMY_PAYMENT_{booking_id}_{current_timestamp}_{payment_type.value}"
            )
        if not razorpay_signature:
            razorpay_signature = (
                f"DUMMY_SIGNATURE_{booking_id}_{current_timestamp}_{payment_type.value}"
            )

        payment_data = schemas.PaymentCreate(
            booking_id=booking_id,
            amount_inr=amount,
            payment_method=payment_method,
            payment_type=payment_type,
            transaction_id=transaction_id,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            remarks=remarks,
            status_id=status_obj.id,
        )

        payment = await payment_crud.create_payment(db, payment_data)
        return schemas.PaymentPublic(
            **await payment_crud.get_payment_data_by_id(db, payment.id)
        )


    async def create_settlement_payment(
        self,
        db: AsyncSession,
        booking_id: int,
        settlement_type: str,
        amount: Decimal,
        remarks: str,
    ) -> Optional[schemas.PaymentPublic]:
        """Create a settlement payment for a booking.
        
        Args:
            db: Database session
            booking_id: Booking ID
            settlement_type: Type of settlement (INITIATED or REFUNDING)
            amount: Settlement amount
            remarks: Settlement remarks
        
        Returns:
            Created payment public data or None
        """
        if settlement_type == "SETTLED" and amount == Decimal("0.00"):
            return None

        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        user_id = booking_data["booked_by"]
        current_time = datetime.now(timezone.utc)

        if settlement_type == "INITIATED":
            return await self.create_payment(
                db=db,
                booking_id=booking_id,
                amount=amount,
                user_id=user_id,
                payment_method=models.PaymentMethod.UPI,
                payment_type=models.PaymentType.ADD_PAYMENT,
                status=models.PaymentStatusEnum.INITIATED,
                transaction_id=f"DUMMY_TXN_SETTLE_A_{booking_id}_{int(current_time.timestamp())}",
                razorpay_order_id=f"DUMMY_ORDER_SETTLE_A_{booking_id}_{int(current_time.timestamp())}",
                razorpay_payment_id=f"DUMMY_PAYMENT_SETTLE_A_{booking_id}_{int(current_time.timestamp())}",
                razorpay_signature=f"DUMMY_SIGNATURE_SETTLE_A_{booking_id}_{int(current_time.timestamp())}",
                remarks=remarks,
            )

        elif settlement_type == "REFUNDING":
            return await self.create_payment(
                db=db,
                booking_id=booking_id,
                amount=amount,
                user_id=user_id,
                payment_method=models.PaymentMethod.UPI,
                payment_type=models.PaymentType.REFUND,
                status=models.PaymentStatusEnum.REFUNDING,
                transaction_id=f"DUMMY_TXN_SETTLE_B_{booking_id}_{int(current_time.timestamp())}",
                razorpay_order_id=f"DUMMY_ORDER_SETTLE_B_{booking_id}_{int(current_time.timestamp())}",
                razorpay_payment_id=f"DUMMY_PAYMENT_SETTLE_B_{booking_id}_{int(current_time.timestamp())}",
                razorpay_signature=f"DUMMY_SIGNATURE_SETTLE_B_{booking_id}_{int(current_time.timestamp())}",
                remarks=remarks,
            )

        return None


    async def create_cancellation_refund(
        self,
        db: AsyncSession,
        booking_id: int,
        refund_amount: Decimal,
        is_customer_cancellation: bool = True,
        reason: str = None,
    ) -> Optional[schemas.PaymentPublic]:
        """Create a cancellation refund payment.
        
        Args:
            db: Database session
            booking_id: Booking ID
            refund_amount: Refund amount
            is_customer_cancellation: Whether it's a customer cancellation
            reason: Optional cancellation reason
        
        Returns:
            Created payment public data or None
        """
        if refund_amount == Decimal("0.00"):
            return None

        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        user_id = booking_data["booked_by"]
        current_time = datetime.now(timezone.utc)

        if is_customer_cancellation:
            remarks = (
                f"Customer cancellation refund: {reason}"
                if reason
                else "Customer cancellation refund"
            )
            payment_type = models.PaymentType.CANCELLATION_REFUND
        else:
            remarks = (
                f"Admin cancellation/rejection refund: {reason}"
                if reason
                else "Admin cancellation/rejection refund"
            )
            payment_type = models.PaymentType.REJECTION_REFUND

        return await self.create_payment(
            db=db,
            booking_id=booking_id,
            amount=refund_amount,
            user_id=user_id,
            payment_method=models.PaymentMethod.UPI,
            payment_type=payment_type,
            status=models.PaymentStatusEnum.REFUNDING,
            transaction_id=f"DUMMY_TXN_CANCEL_REFUND_{booking_id}_{int(current_time.timestamp())}",
            razorpay_order_id=f"DUMMY_ORDER_CANCEL_REFUND_{booking_id}_{int(current_time.timestamp())}",
            razorpay_payment_id=f"DUMMY_PAYMENT_CANCEL_REFUND_{booking_id}_{int(current_time.timestamp())}",
            razorpay_signature=f"DUMMY_SIGNATURE_CANCEL_REFUND_{booking_id}_{int(current_time.timestamp())}",
            remarks=remarks,
        )


    async def confirm_payment(
        self,
        db: AsyncSession,
        payment_id: int,
        user_id: str,
        confirm_in: schemas.PaymentConfirmRequest,
    ) -> schemas.Msg:
        """Confirm a payment and update booking status.
        
        Args:
            db: Database session
            payment_id: Payment ID
            user_id: User ID
            confirm_in: Payment confirmation request data
        
        Returns:
            Success message
        """
        payment_data = await payment_crud.get_payment_data_by_id(db, payment_id)
        if not payment_data:
            raise NotFoundException("Payment not found")

        self._validate_payment_ownership(payment_data, user_id)

        self._validate_payment_status(payment_data, models.PaymentStatusEnum.INITIATED)

        if payment_data["payment_type"] != models.PaymentType.PAYMENT:
            raise BadRequestException("Only PAYMENT type payments can be confirmed")

        booking_data = await booking_crud.get_booking_data_by_id(
            db, payment_data["booking_id"]
        )
        if not booking_data:
            raise NotFoundException("Booking not found")

        self._validate_booking_status(booking_data, models.StatusEnum.RETURNED)
        self._validate_booking_payment_status(
            booking_data, models.PaymentStatusEnum.INITIATED
        )

        charged_status = await rbac_crud.get_status_by_name(
            db, models.PaymentStatusEnum.CHARGED
        )
        if not charged_status:
            raise NotFoundException("CHARGED status not found")

        update_data = {"status_id": charged_status.id}

        if confirm_in.payment_method:
            update_data["payment_method"] = confirm_in.payment_method
        if confirm_in.transaction_id:
            update_data["transaction_id"] = confirm_in.transaction_id
        if confirm_in.razorpay_order_id:
            update_data["razorpay_order_id"] = confirm_in.razorpay_order_id
        if confirm_in.razorpay_payment_id:
            update_data["razorpay_payment_id"] = confirm_in.razorpay_payment_id
        if confirm_in.razorpay_signature:
            update_data["razorpay_signature"] = confirm_in.razorpay_signature
        if confirm_in.remarks:
            update_data["remarks"] = confirm_in.remarks

        await payment_crud.update_payment(db, payment_id, update_data)

        await booking_crud.update_payment_status(
            db, payment_data["booking_id"], charged_status.id
        )

        pickup_otp = booking_service._generate_otp()
        current_time = datetime.now(timezone.utc)

        await booking_crud.update_payment_summary(
            db,
            payment_data["booking_id"],
            {
                "return_verification": {
                    "pickup_otp_generated_at": current_time.isoformat()
                },
                "settlement": {
                    "settlement_status": "CHARGED",
                    "additional_payment_confirmed": True,
                    "additional_payment_confirmed_at": current_time.isoformat(),
                },
            },
        )

        await booking_crud.update_booking(
            db,
            payment_data["booking_id"],
            {"pickup_otp": pickup_otp, "pickup_otp_generated_at": current_time},
        )

        await notification_utils.send_system_notification(
            db,
            receiver_id=user_id,
            subject=f"Booking #{payment_data['booking_id']} Payment Confirmed",
            body="Additional payment confirmed successfully. Pickup OTP generated.",
            type=models.NotificationType.PAYMENT,
        )

        return schemas.Msg(
            message="Payment confirmed successfully. Pickup OTP has been generated."
        )


    async def confirm_refund(
        self,
        db: AsyncSession,
        payment_id: int,
        confirm_in: schemas.PaymentConfirmRequest,
    ) -> schemas.Msg:
        """Confirm a refund payment.
        
        Args:
            db: Database session
            payment_id: Payment ID
            confirm_in: Payment confirmation request data
        
        Returns:
            Success message
        """
        payment_data = await payment_crud.get_payment_data_by_id(db, payment_id)
        if not payment_data:
            raise NotFoundException("Payment not found")

        booking_id = payment_data["booking_id"]
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["payment_status"] != models.PaymentStatusEnum.REFUNDING:
            raise BadRequestException("Booking is not in refunding status")

        if payment_data["status"] != models.PaymentStatusEnum.REFUNDING:
            raise BadRequestException("Payment is not in refunding status")

        refunded_status = await rbac_crud.get_status_by_name(
            db, models.PaymentStatusEnum.REFUNDED
        )
        if not refunded_status:
            raise NotFoundException("REFUNDED status not found")

        update_data = {"status_id": refunded_status.id}

        if confirm_in.payment_method:
            update_data["payment_method"] = confirm_in.payment_method
        if confirm_in.transaction_id:
            update_data["transaction_id"] = confirm_in.transaction_id
        if confirm_in.razorpay_order_id:
            update_data["razorpay_order_id"] = confirm_in.razorpay_order_id

        if confirm_in.razorpay_payment_id:
            update_data["razorpay_payment_id"] = confirm_in.razorpay_payment_id

        if confirm_in.razorpay_signature:
            update_data["razorpay_signature"] = confirm_in.razorpay_signature
        if confirm_in.remarks:
            update_data["remarks"] = confirm_in.remarks

        await payment_crud.update_payment(db, payment_id, update_data)

        await booking_crud.update_payment_status(db, booking_id, refunded_status.id)

        await booking_crud.update_payment_summary(
            db,
            booking_id,
            {
                "settlement": {
                    "settlement_status": "REFUNDED",
                    "refund_processed": True,
                    "refund_processed_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        await notification_utils.send_system_notification(
            db,
            receiver_id=booking_data["booked_by"],
            subject=f"Booking #{booking_id} Refund Confirmed",
            body=f"Refund of ₹{payment_data['amount_inr']} has been processed successfully.",
            type=models.NotificationType.PAYMENT,
        )

        return schemas.Msg(
            message=f"Refund of ₹{payment_data['amount_inr']} confirmed successfully"
        )


    async def get_user_payments(
        self,
        db: AsyncSession,
        user_id: str,
        skip: int,
        limit: int,
        filters: schemas.PaymentFilterParams,
    ) -> schemas.PaginatedResponse:
        """Get paginated user payments.
        
        Args:
            db: Database session
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Payment filter parameters
        
        Returns:
            Paginated response with payment data
        """
        items, total = await payment_crud.get_user_payments_data(
            db, user_id, skip, limit, filters
        )
        return schemas.PaginatedResponse(
            total=total, items=items, skip=skip, limit=limit
        )


    async def get_payment_details(
        self, db: AsyncSession, payment_id: int, user_id_or_admin: str
    ) -> schemas.PaymentDetailed:
        """Get detailed payment information.
        
        Args:
            db: Database session
            payment_id: Payment ID
            user_id_or_admin: User ID or 'ADMIN' for admin access
        
        Returns:
            Detailed payment data
        """
        payment_data = await payment_crud.get_payment_data_by_id(db, payment_id)
        if not payment_data:
            raise NotFoundException("Payment not found")

        if (
            user_id_or_admin != "ADMIN"
            and payment_data["booking"]["booked_by"] != user_id_or_admin
        ):
            raise ForbiddenException("Access denied")

        return schemas.PaymentDetailed(**payment_data)


    async def get_all_payments(
        self,
        db: AsyncSession,
        skip: int,
        limit: int,
        filters: schemas.PaymentFilterParams,
    ) -> schemas.PaginatedResponse:
        """Get all payments with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Payment filter parameters
        
        Returns:
            Paginated response with payment data
        """
        items, total = await payment_crud.get_all_payments_data(
            db, skip, limit, filters
        )
        return schemas.PaginatedResponse(
            total=total, items=items, skip=skip, limit=limit
        )


    async def get_payments_by_booking_id(
        self, db: AsyncSession, booking_id: int, user_id: str
    ) -> List[schemas.PaymentPublic]:
        """Get all payments for a specific booking.
        
        Args:
            db: Database session
            booking_id: Booking ID
            user_id: User ID
        
        Returns:
            List of payment public data
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booked_by"] != user_id:
            raise ForbiddenException("Access denied")

        payments_data = await payment_crud.get_payments_by_booking_id(db, booking_id)
        return [schemas.PaymentPublic(**payment_data) for payment_data in payments_data]


    async def get_refunding_payments_for_admin(
        self,
        db: AsyncSession,
        skip: int,
        limit: int,
        filters: schemas.PaymentFilterParams,
    ) -> schemas.PaginatedResponse:
        """Get refunding payments for admin with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Payment filter parameters
        
        Returns:
            Paginated response with refunding payment data
        """
        if not filters.status:
            filters.status = models.PaymentStatusEnum.REFUNDING

        items, total = await payment_crud.get_all_payments_data(
            db, skip, limit, filters
        )

        refunding_payments = [
            item
            for item in items
            if item["status"] == models.PaymentStatusEnum.REFUNDING
        ]

        return schemas.PaginatedResponse(
            total=len(refunding_payments),
            items=refunding_payments,
            skip=skip,
            limit=limit,
        )


    async def get_initiated_payment_for_user(
        self, db: AsyncSession, booking_id: int, user_id: str
    ) -> schemas.PaymentPublic:
        """Get initiated payment for a user's booking.
        
        Args:
            db: Database session
            booking_id: Booking ID
            user_id: User ID
        
        Returns:
            Payment public data for the initiated payment
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booked_by"] != user_id:
            raise ForbiddenException("Access denied")

        if booking_data["payment_status"] != models.PaymentStatusEnum.INITIATED:
            raise BadRequestException(
                "Booking is not in initiated status for additional payment"
            )

        payments_data = await payment_crud.get_payments_by_booking_id(db, booking_id)

        initiated_payment = None
        for payment in payments_data:
            if (
                payment["status"] == models.PaymentStatusEnum.INITIATED
                and payment["payment_type"] == models.PaymentType.PAYMENT
            ):
                initiated_payment = payment
                break

        if not initiated_payment:
            raise NotFoundException(
                "No initiated additional payment found for this booking"
            )

        return schemas.PaymentPublic(**initiated_payment)


payment_service = PaymentService()
