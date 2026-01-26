from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, aliased
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone


from app import models, schemas


class PaymentCRUD:
    """
    Class for managing payment records and related operations.
    """
    async def create_payment(
        self, db: AsyncSession, payment_in: schemas.PaymentCreate
    ) -> models.Payment:
        """
        Create a new payment record.

        Args:
            db: Database session
            payment_in: Payment creation data

        Returns:
            Created payment object
        """
        db_payment = models.Payment(**payment_in.model_dump())
        db.add(db_payment)
        await db.commit()
        await db.refresh(db_payment)
        return db_payment


    async def update_payment(
        self, db: AsyncSession, payment_id: int, update_data: Dict[str, Any]
    ) -> Optional[models.Payment]:
        """
        Update payment fields.

        Args:
            db: Database session
            payment_id: ID of payment to update
            update_data: Dictionary of fields to update

        Returns:
            Updated payment object or None if not found
        """
        payment = await db.get(models.Payment, payment_id)
        if payment:
            for key, value in update_data.items():
                setattr(payment, key, value)
            await db.commit()
            await db.refresh(payment)
        return payment


    async def get_payment_by_id(
        self, db: AsyncSession, payment_id: int
    ) -> Optional[models.Payment]:
        """
        Get payment by ID with relationships.

        Args:
            db: Database session
            payment_id: ID of payment to retrieve

        Returns:
            Payment object with relationships or None if not found
        """
        result = await db.execute(
            select(models.Payment)
            .options(
                selectinload(models.Payment.booking)
                .selectinload(models.Booking.car)
                .selectinload(models.Car.car_model),
                selectinload(models.Payment.booking)
                .selectinload(models.Booking.booker)
                .selectinload(models.User.customer_details),
                selectinload(models.Payment.status),
            )
            .where(models.Payment.id == payment_id)
        )
        return result.scalar_one_or_none()


    async def get_payment_data_by_id(
        self, db: AsyncSession, payment_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get payment data as dictionary with all Razorpay fields.

        Args:
            db: Database session
            payment_id: ID of payment to retrieve

        Returns:
            Payment data dictionary or None if not found
        """
        payment = await self.get_payment_by_id(db, payment_id)
        if not payment:
            return None

        return self._payment_to_dict(payment)


    async def get_payments_by_booking_id(
        self, db: AsyncSession, booking_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all payments for a booking.

        Args:
            db: Database session
            booking_id: ID of booking to get payments for

        Returns:
            List of payment data dictionaries
        """
        result = await db.execute(
            select(models.Payment)
            .options(
                selectinload(models.Payment.status),
                selectinload(models.Payment.booking)
                .selectinload(models.Booking.car)
                .selectinload(models.Car.car_model),
            )
            .where(models.Payment.booking_id == booking_id)
            .order_by(models.Payment.created_at.desc())
        )
        payments = result.scalars().all()
        return [self._payment_to_dict(payment) for payment in payments]


    async def get_user_payments_data(
        self,
        db: AsyncSession,
        user_id: str,
        skip: int,
        limit: int,
        filters: schemas.PaymentFilterParams,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated user payments with filters.

        Args:
            db: Database session
            user_id: ID of user to get payments for
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Payment filter parameters

        Returns:
            Tuple of payment data list and total count
        """
        query = (
            select(models.Payment)
            .join(models.Payment.booking)
            .options(
                selectinload(models.Payment.booking)
                .selectinload(models.Booking.car)
                .selectinload(models.Car.car_model),
                selectinload(models.Payment.status),
            )
            .where(models.Booking.booked_by == user_id)
        )

        query = self._apply_payment_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = self._apply_payment_sorting(query, filters.sort)
        result = await db.execute(query.offset(skip).limit(limit))
        payments = result.scalars().all()

        return [self._payment_to_dict(payment) for payment in payments], total


    async def get_all_payments_data(
        self, db: AsyncSession, skip: int, limit: int, filters: schemas.PaymentFilterParams
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated all payments with filters.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Payment filter parameters

        Returns:
            Tuple of payment data list and total count
        """
        query = (
            select(models.Payment)
            .join(models.Payment.booking)
            .options(
                selectinload(models.Payment.booking)
                .selectinload(models.Booking.car)
                .selectinload(models.Car.car_model),
                selectinload(models.Payment.booking)
                .selectinload(models.Booking.booker)
                .selectinload(models.User.customer_details),
                selectinload(models.Payment.status),
            )
        )

        query = self._apply_payment_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = self._apply_payment_sorting(query, filters.sort)

        result = await db.execute(query.offset(skip).limit(limit))
        payments = result.scalars().all()

        return [self._payment_to_dict(payment) for payment in payments], total


    async def update_payment_status(
        self, db: AsyncSession, payment_id: int, status_id: int
    ):
        """
        Update payment status.

        Args:
            db: Database session
            payment_id: ID of payment to update
            status_id: New status ID

        Returns:
            None
        """
        payment = await db.get(models.Payment, payment_id)
        if payment:
            payment.status_id = status_id
            await db.commit()



    def _payment_to_dict(self, payment: models.Payment) -> Dict[str, Any]:
        """
        Convert ORM payment to dictionary with all fields.

        Args:
            payment: Payment object to convert

        Returns:
            Dictionary representation of payment with nested relationships
        """
        customer_name = "N/A"
        if (
            payment.booking
            and payment.booking.booker
            and payment.booking.booker.customer_details
        ):
            customer_name = payment.booking.booker.customer_details.name

        car_model_str = "N/A"
        if payment.booking and payment.booking.car and payment.booking.car.car_model:
            car_model_str = f"{payment.booking.car.car_model.brand} {payment.booking.car.car_model.model}"

        return {
            "id": payment.id,
            "booking_id": payment.booking_id,
            "amount_inr": payment.amount_inr,
            "payment_method": payment.payment_method,
            "payment_type": payment.payment_type,
            "status": payment.status.name if payment.status else None,
            "transaction_id": payment.transaction_id,
            "razorpay_order_id": payment.razorpay_order_id,
            "razorpay_payment_id": payment.razorpay_payment_id,
            "razorpay_signature": payment.razorpay_signature,
            "remarks": payment.remarks,
            "created_at": payment.created_at,
            "booking": (
                {
                    "id": payment.booking.id if payment.booking else None,
                    "booked_by": payment.booking.booked_by if payment.booking else None,
                    "booking_status": (
                        payment.booking.booking_status.name
                        if payment.booking and payment.booking.booking_status
                        else None
                    ),
                    "payment_status": (
                        payment.booking.payment_status.name
                        if payment.booking and payment.booking.payment_status
                        else None
                    ),
                    "created_at": payment.booking.created_at if payment.booking else None,
                    "car": (
                        {
                            "id": (
                                payment.booking.car.id
                                if payment.booking and payment.booking.car
                                else None
                            ),
                            "car_no": (
                                payment.booking.car.car_no
                                if payment.booking and payment.booking.car
                                else None
                            ),
                            "car_model": (
                                {
                                    "brand": (
                                        payment.booking.car.car_model.brand
                                        if payment.booking
                                        and payment.booking.car
                                        and payment.booking.car.car_model
                                        else None
                                    ),
                                    "model": (
                                        payment.booking.car.car_model.model
                                        if payment.booking
                                        and payment.booking.car
                                        and payment.booking.car.car_model
                                        else None
                                    ),
                                }
                                if payment.booking and payment.booking.car
                                else None
                            ),
                            "created_at": (
                                payment.booking.car.created_at
                                if payment.booking and payment.booking.car
                                else None
                            ),
                        }
                        if payment.booking
                        else None
                    ),
                    "booker": (
                        {
                            "id": (
                                payment.booking.booker.id
                                if payment.booking and payment.booking.booker
                                else None
                            ),
                            "email": (
                                payment.booking.booker.email
                                if payment.booking and payment.booking.booker
                                else None
                            ),
                            "username": (
                                payment.booking.booker.username
                                if payment.booking and payment.booking.booker
                                else None
                            ),
                            "customer_name": customer_name,
                            "created_at": (
                                payment.booking.booker.created_at
                                if payment.booking and payment.booking.booker
                                else None
                            ),
                        }
                        if payment.booking
                        else None
                    ),
                }
                if payment.booking
                else None
            ),
        }


    def _apply_payment_filters(self, query, filters: schemas.PaymentFilterParams):
        """
        Apply filters to payment query.

        Args:
            query: SQLAlchemy query to filter
            filters: Payment filter parameters

        Returns:
            Filtered query
        """
        if filters.search:
            search_term = f"%{filters.search}%"
            query = (
                query.join(models.Payment.booking)
                .join(models.Booking.car)
                .where(
                    or_(
                        models.Car.car_no.ilike(search_term),
                        models.Payment.transaction_id.ilike(search_term),
                        models.Payment.razorpay_order_id.ilike(search_term),
                        models.Payment.razorpay_payment_id.ilike(search_term),
                    )
                )
            )

        if filters.status:
            p_status = aliased(models.Status)
            query = query.join(p_status, models.Payment.status_id == p_status.id).where(
                p_status.name == filters.status
            )

        if filters.payment_type:
            query = query.where(models.Payment.payment_type == filters.payment_type)

        if filters.start_date:
            dt = datetime.combine(filters.start_date, datetime.min.time()).replace(
                tzinfo=timezone.utc
            )
            query = query.where(models.Payment.created_at >= dt)

        if filters.end_date:
            dt = datetime.combine(filters.end_date, datetime.max.time()).replace(
                tzinfo=timezone.utc
            )
            query = query.where(models.Payment.created_at <= dt)

        return query


    def _apply_payment_sorting(self, query, sort: str):
        """
        Apply sorting to payment query.

        Args:
            query: SQLAlchemy query to sort
            sort: Sort option string

        Returns:
            Sorted query
        """
        if sort == "created_at_asc":
            return query.order_by(models.Payment.created_at.asc())
        if sort == "amount_asc":
            return query.order_by(models.Payment.amount_inr.asc())
        if sort == "amount_desc":
            return query.order_by(models.Payment.amount_inr.desc())
        return query.order_by(models.Payment.created_at.desc())


payment_crud = PaymentCRUD()