from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, delete, String
from sqlalchemy.orm import selectinload, aliased
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone


from app import models, schemas
from .rbac_crud import rbac_crud
from app.utils.exception_utils import NotFoundException


class BookingCRUD:
    """
    Class for managing bookings and booking freezes.
    """

    async def create_location(
        self, db: AsyncSession, location_in: schemas.LocationCreate
    ) -> models.Location:
        """
        Create a new location record.

        Args:
            db: Database session
            location_in: Location data to create

        Returns:
            Created location model
        """
        db_location = models.Location(**location_in.model_dump())
        db.add(db_location)
        await db.commit()
        await db.refresh(db_location)
        return db_location


    async def get_location_by_coords(
        self, db: AsyncSession, longitude: float, latitude: float
    ) -> Optional[models.Location]:
        """
        Get location by coordinates.

        Args:
            db: Database session
            longitude: Location longitude
            latitude: Location latitude

        Returns:
            Location model if found, None otherwise
        """
        result = await db.execute(
            select(models.Location).where(
                and_(
                    models.Location.longitude == longitude,
                    models.Location.latitude == latitude,
                )
            )
        )
        return result.scalar_one_or_none()


    async def get_location_by_id(
        self, db: AsyncSession, location_id: int
    ) -> Optional[models.Location]:
        """
        Get location by ID.

        Args:
            db: Database session
            location_id: Location ID

        Returns:
            Location model if found, None otherwise
        """
        return await db.get(models.Location, location_id)


    async def create_booking_freeze(
        self,
        db: AsyncSession,
        freeze_data: Dict[str, Any],
        delivery_location: schemas.LocationCreate,
        pickup_location: schemas.LocationCreate,
    ) -> models.BookingFreeze:
        """
        Create a new booking freeze.

        Args:
            db: Database session
            freeze_data: Freeze data dictionary
            delivery_location: Delivery location data
            pickup_location: Pickup location data

        Returns:
            Created booking freeze model
        """
        freeze_data.update(
            {
                "delivery_longitude": delivery_location.longitude,
                "delivery_latitude": delivery_location.latitude,
                "pickup_longitude": pickup_location.longitude,
                "pickup_latitude": pickup_location.latitude,
            }
        )

        db_freeze = models.BookingFreeze(**freeze_data)
        db.add(db_freeze)
        await db.commit()
        await db.refresh(db_freeze)
        return db_freeze


    async def get_booking_freeze_by_id(
        self, db: AsyncSession, freeze_id: int
    ) -> Optional[models.BookingFreeze]:
        """
        Get booking freeze by ID.

        Args:
            db: Database session
            freeze_id: Freeze ID

        Returns:
            Booking freeze model if found, None otherwise
        """
        return await db.get(models.BookingFreeze, freeze_id)


    async def get_active_freezes_for_car(
        self, db: AsyncSession, car_id: int, start_date: datetime, end_date: datetime
    ) -> List[models.BookingFreeze]:
        """
        Get active freezes for a car within a date range.

        Args:
            db: Database session
            car_id: Car ID
            start_date: Start date of range
            end_date: End date of range

        Returns:
            List of active booking freezes
        """
        result = await db.execute(
            select(models.BookingFreeze).where(
                models.BookingFreeze.car_id == car_id,
                models.BookingFreeze.is_active.is_(True),
                models.BookingFreeze.freeze_expires_at > datetime.now(timezone.utc),
                models.BookingFreeze.start_date < end_date,
                models.BookingFreeze.end_date > start_date,
            )
        )
        return result.scalars().all()


    async def get_customer_active_freezes(
        self, db: AsyncSession, user_id: str, start_date: datetime, end_date: datetime
    ) -> List[models.BookingFreeze]:
        """
        Get active freezes for a customer within a date range.

        Args:
            db: Database session
            user_id: User ID
            start_date: Start date of range
            end_date: End date of range

        Returns:
            List of customer's active booking freezes
        """
        result = await db.execute(
            select(models.BookingFreeze).where(
                models.BookingFreeze.user_id == user_id,
                models.BookingFreeze.is_active.is_(True),
                models.BookingFreeze.freeze_expires_at > datetime.now(timezone.utc),
                models.BookingFreeze.start_date < end_date,
                models.BookingFreeze.end_date > start_date,
            )
        )
        return result.scalars().all()


    async def update_booking_freeze(
        self, db: AsyncSession, freeze_id: int, update_data: Dict[str, Any]
    ) -> Optional[models.BookingFreeze]:
        """
        Update a booking freeze.

        Args:
            db: Database session
            freeze_id: Freeze ID
            update_data: Dictionary of fields to update

        Returns:
            Updated booking freeze if found, None otherwise
        """
        freeze = await db.get(models.BookingFreeze, freeze_id)
        if freeze:
            for key, value in update_data.items():
                setattr(freeze, key, value)
            await db.commit()
            await db.refresh(freeze)
        return freeze


    async def delete_booking_freeze(self, db: AsyncSession, freeze_id: int) -> bool:
        """
        Delete a booking freeze.

        Args:
            db: Database session
            freeze_id: Freeze ID

        Returns:
            True if deleted, False if not found
        """
        freeze = await db.get(models.BookingFreeze, freeze_id)
        if freeze:
            await db.delete(freeze)
            await db.commit()
            return True
        return False


    async def cleanup_expired_freezes(self, db: AsyncSession):
        """
        Clean up expired or inactive booking freezes.

        Args:
            db: Database session
        """
        now = datetime.now(timezone.utc)
        await db.execute(
            delete(models.BookingFreeze).where(
                or_(
                    models.BookingFreeze.freeze_expires_at <= now,
                    models.BookingFreeze.is_active.is_(False),
                )
            )
        )
        await db.commit()


    async def create_booking(
        self, db: AsyncSession, booking_data: Dict[str, Any]
    ) -> models.Booking:
        """
        Create a new booking.

        Args:
            db: Database session
            booking_data: Booking data dictionary

        Returns:
            Created booking model
        """
        db_booking = models.Booking(**booking_data)
        db.add(db_booking)
        await db.commit()
        await db.refresh(db_booking)
        return db_booking


    async def get_booking_by_id(
        self, db: AsyncSession, booking_id: int
    ) -> Optional[models.Booking]:
        """
        Get booking by ID with all related data preloaded.

        Args:
            db: Database session
            booking_id: Booking ID

        Returns:
            Booking model with relationships if found, None otherwise
        """
        result = await db.execute(
            select(models.Booking)
            .options(
                selectinload(models.Booking.delivery_location),
                selectinload(models.Booking.pickup_location),
                selectinload(models.Booking.car).selectinload(models.Car.car_model),
                selectinload(models.Booking.car).selectinload(models.Car.color),
                selectinload(models.Booking.booking_status),
                selectinload(models.Booking.payment_status),
                selectinload(models.Booking.payments).selectinload(models.Payment.status),
                selectinload(models.Booking.review),
                selectinload(models.Booking.booker)
                .selectinload(models.User.customer_details)
                .selectinload(models.CustomerDetails.address),
                selectinload(models.Booking.booker)
                .selectinload(models.User.customer_details)
                .selectinload(models.CustomerDetails.tag),
            )
            .where(models.Booking.id == booking_id)
        )
        return result.scalar_one_or_none()


    async def get_booking_data_by_id(
        self, db: AsyncSession, booking_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get booking data as dictionary by ID.

        Args:
            db: Database session
            booking_id: Booking ID

        Returns:
            Booking data dictionary if found, None otherwise
        """
        booking = await self.get_booking_by_id(db, booking_id)
        if not booking:
            return None

        return self._booking_to_dict(booking)


    def _booking_to_dict(self,booking: models.Booking) -> Dict[str, Any]:
        """
        Convert booking model to dictionary.

        Args:
            booking: Booking model

        Returns:
            Booking data dictionary
        """
        return {
            "id": booking.id,
            "car_id": booking.car_id,
            "start_date": booking.start_date,
            "end_date": booking.end_date,
            "remarks": booking.remarks,
            "created_at": booking.created_at,
            "booked_by": booking.booked_by,
            "booking_status": (
                booking.booking_status.name if booking.booking_status else None
            ),
            "payment_status": (
                booking.payment_status.name if booking.payment_status else None
            ),
            "payment_summary": booking.payment_summary or {},
            "delivery_video_url": booking.delivery_video_url,
            "delivery_otp": booking.delivery_otp,
            "delivery_otp_generated_at": booking.delivery_otp_generated_at,
            "delivery_otp_verified": booking.delivery_otp_verified,
            "delivery_otp_verified_at": booking.delivery_otp_verified_at,
            "start_kilometers": booking.start_kilometers,
            "pickup_video_url": booking.pickup_video_url,
            "pickup_otp": booking.pickup_otp,
            "pickup_otp_generated_at": booking.pickup_otp_generated_at,
            "pickup_otp_verified": booking.pickup_otp_verified,
            "pickup_otp_verified_at": booking.pickup_otp_verified_at,
            "end_kilometers": booking.end_kilometers,
            "car": (
                {
                    "id": booking.car.id,
                    "car_no": booking.car.car_no,
                    "color": booking.car.color.color_name if booking.car.color else None,
                    "image_urls": (
                        booking.car.image_urls if hasattr(booking.car, "image_urls") else []
                    ),
                    "car_model": (
                        {
                            "id": booking.car.car_model.id,
                            "brand": booking.car.car_model.brand,
                            "model": booking.car.car_model.model,
                            "dynamic_rental_price": booking.car.car_model.dynamic_rental_price,
                            "kilometer_limit_per_hr": booking.car.car_model.kilometer_limit_per_hr,
                        }
                        if booking.car.car_model
                        else None
                    ),
                }
                if booking.car
                else None
            ),
            "pickup_location": (
                {
                    "id": booking.pickup_location.id,
                    "longitude": booking.pickup_location.longitude,
                    "latitude": booking.pickup_location.latitude,
                    "address": booking.pickup_location.address,
                }
                if booking.pickup_location
                else None
            ),
            "delivery_location": (
                {
                    "id": booking.delivery_location.id,
                    "longitude": booking.delivery_location.longitude,
                    "latitude": booking.delivery_location.latitude,
                    "address": booking.delivery_location.address,
                }
                if booking.delivery_location
                else None
            ),
            "payments": (
                [
                    {
                        "id": payment.id,
                        "amount_inr": payment.amount_inr,
                        "payment_method": payment.payment_method,
                        "payment_type": payment.payment_type,
                        "status": payment.status.name if payment.status else None,
                        "transaction_id": payment.transaction_id,
                        "razorpay_order_id": payment.razorpay_order_id,
                        "razorpay_payment_id": payment.razorpay_payment_id,
                        "razorpay_signature": payment.razorpay_signature,
                        "created_at": payment.created_at,
                        "remarks": payment.remarks,
                    }
                    for payment in booking.payments
                ]
                if booking.payments
                else []
            ),
            "review": (
                {
                    "id": booking.review.id,
                    "rating": booking.review.rating,
                    "remarks": booking.review.remarks,
                    "created_at": booking.review.created_at,
                    "created_by": booking.review.created_by,
                }
                if booking.review
                else None
            ),
            "booker": self._format_booker_details(booking.booker) if booking.booker else None,
            "cancelled_at": booking.cancelled_at,
            "cancelled_by": booking.cancelled_by,
            "cancellation_reason": booking.cancellation_reason,
            "referral_benefit": booking.referral_benefit,
        }


    def _format_booker_details(self, booker) -> Dict[str, Any]:
        """
        Format booker details with full customer information.

        Args:
            booker: User model

        Returns:
            Formatted booker data dictionary
        """
        if not booker:
            return None

        # Basic user details
        booker_data = {
            "id": booker.id,
            "username": booker.username,
            "email": booker.email,
            "created_at": booker.created_at,
            "name": None,
            "phone": None,
            "dob": None,
            "gender": None,
            "profile_url": None,
            "address": None,
            "aadhaar_no": None,
            "license_no": None,
            "is_verified": None,
            "tag": None,
            "rookie_benefit_used": None,
            "referral_code": booker.referral_code,
            "total_referrals": booker.total_referrals,
        }

        # Add customer details if available
        if booker.customer_details:
            cd = booker.customer_details
            booker_data.update(
                {
                    "name": cd.name,
                    "phone": cd.phone,
                    "dob": cd.dob,
                    "gender": cd.gender,
                    "profile_url": cd.profile_url,
                    "aadhaar_no": (
                        f"XXXX-XXXX-{cd.aadhaar_no[-4:]}" if cd.aadhaar_no else None
                    ),  # Masked
                    "license_no": cd.license_no,
                    "is_verified": cd.is_verified,
                    "rookie_benefit_used": cd.rookie_benefit_used,
                }
            )

            # Add address if available
            if cd.address:
                booker_data["address"] = {
                    "id": cd.address.id,
                    "address_line": cd.address.address_line,
                    "area": cd.address.area,
                    "state": cd.address.state,
                    "country": cd.address.country,
                }

            # Add tag if available
            if cd.tag:
                booker_data["tag"] = cd.tag.name

        return booker_data


    async def update_booking(
        self, db: AsyncSession, booking_id: int, update_data: Dict[str, Any]
    ) -> Optional[models.Booking]:
        """
        Update a booking.

        Args:
            db: Database session
            booking_id: Booking ID
            update_data: Dictionary of fields to update

        Returns:
            Updated booking if found, None otherwise
        """
        booking = await db.get(models.Booking, booking_id)
        if booking:
            for key, value in update_data.items():
                setattr(booking, key, value)
            await db.commit()
            await db.refresh(booking)
        return booking


    async def update_booking_status(self, db: AsyncSession, booking_id: int, status_id: int):
        """
        Update booking status.

        Args:
            db: Database session
            booking_id: Booking ID
            status_id: New status ID
        """
        booking = await db.get(models.Booking, booking_id)
        if booking:
            booking.booking_status_id = status_id
            await db.commit()


    async def update_payment_status(self, db: AsyncSession, booking_id: int, status_id: int):
        """
        Update payment status.

        Args:
            db: Database session
            booking_id: Booking ID
            status_id: New status ID
        """
        booking = await db.get(models.Booking, booking_id)
        if booking:
            booking.payment_status_id = status_id
            await db.commit()


    async def update_booking_and_payment_status(
        self, db: AsyncSession, booking_id: int, booking_status_id: int, payment_status_id: int
    ):
        """
        Update both booking and payment status.

        Args:
            db: Database session
            booking_id: Booking ID
            booking_status_id: New booking status ID
            payment_status_id: New payment status ID
        """
        booking = await db.get(models.Booking, booking_id)
        if booking:
            booking.booking_status_id = booking_status_id
            booking.payment_status_id = payment_status_id
            await db.commit()


    async def update_payment_summary(
        self, db: AsyncSession, booking_id: int, summary_updates: Dict[str, Any]
    ):
        """
        Update payment summary with deep merge.

        Args:
            db: Database session
            booking_id: Booking ID
            summary_updates: Updates to merge into payment summary
        """
        booking = await db.get(models.Booking, booking_id)
        if booking:
            current_summary = booking.payment_summary or {}
            self._deep_merge(current_summary, summary_updates)
            booking.payment_summary = current_summary
            flag_modified(booking, "payment_summary")
            await db.commit()


    def _deep_merge(self, original: Dict, updates: Dict):
        """
        Deep merge updates into original dictionary.

        Args:
            original: Original dictionary to update
            updates: Updates to merge
        """
        for key, value in updates.items():
            if (
                key in original
                and isinstance(original[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_merge(original[key], value)
            else:
                original[key] = value


    async def check_car_availability(
        self,
        db: AsyncSession,
        car_id: int,
        start: datetime,
        end: datetime,
        exclude_booking_id: Optional[int] = None,
    ) -> bool:
        """
        Check if a car is available for the given time period.

        Args:
            db: Database session
            car_id: Car ID
            start: Start datetime
            end: End datetime
            exclude_booking_id: Booking ID to exclude from check

        Returns:
            True if available, False otherwise
        """
        blocking_statuses = ["BOOKED", "DELIVERED", "RETURNED"]

        query = (
            select(models.Booking)
            .join(models.Status, models.Booking.booking_status_id == models.Status.id)
            .where(
                models.Booking.car_id == car_id,
                models.Status.name.in_(blocking_statuses),
                models.Booking.start_date < end,
                models.Booking.end_date > start,
            )
        )

        if exclude_booking_id:
            query = query.where(models.Booking.id != exclude_booking_id)

        result = await db.execute(query)
        return result.first() is None


    async def get_customer_overlapping_bookings(
        self,
        db: AsyncSession,
        user_id: str,
        start: datetime,
        end: datetime,
        blocking_statuses: List[str],
    ) -> List[models.Booking]:
        """
        Get overlapping bookings for a customer.

        Args:
            db: Database session
            user_id: User ID
            start: Start datetime
            end: End datetime
            blocking_statuses: List of status names to consider

        Returns:
            List of overlapping bookings
        """
        query = (
            select(models.Booking)
            .join(models.Status, models.Booking.booking_status_id == models.Status.id)
            .where(
                models.Booking.booked_by == user_id,
                models.Status.name.in_(blocking_statuses),
                models.Booking.start_date < end,
                models.Booking.end_date > start,
            )
        )

        result = await db.execute(query)
        return result.scalars().all()


    async def get_next_available_time(self, db: AsyncSession, car_id: int) -> Optional[datetime]:
        """
        Get the next available time for a car.

        Args:
            db: Database session
            car_id: Car ID

        Returns:
            Next available datetime if found, None otherwise
        """
        current_time = datetime.now(timezone.utc)

        result = await db.execute(
            select(models.Booking.end_date)
            .join(models.Status, models.Booking.booking_status_id == models.Status.id)
            .where(
                models.Booking.car_id == car_id,
                models.Status.name.in_(["BOOKED", "DELIVERED", "RETURNED"]),
                models.Booking.end_date > current_time,
            )
            .order_by(models.Booking.end_date.desc())
            .limit(1)
        )

        last_booking = result.scalar_one_or_none()

        return last_booking


    async def get_user_bookings_data(
        self,
        db: AsyncSession,
        user_id: str,
        skip: int,
        limit: int,
        filters: schemas.BookingFilterParams,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get user bookings data with filtering and pagination.

        Args:
            db: Database session
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Filter parameters

        Returns:
            Tuple of (list of booking dictionaries, total count)
        """
        query = (
            select(models.Booking)
            .options(
                selectinload(models.Booking.booking_status),
                selectinload(models.Booking.payment_status),
                selectinload(models.Booking.car).selectinload(models.Car.car_model),
                selectinload(models.Booking.car).selectinload(models.Car.color),
            )
            .where(models.Booking.booked_by == user_id)
        )

        query = self._apply_user_booking_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = self._apply_sorting(query, filters)

        result = await db.execute(query.offset(skip).limit(limit))
        bookings = result.scalars().all()

        return [self._booking_to_dict(booking) for booking in bookings], total

    async def get_all_bookings_data(
        self, db: AsyncSession, skip: int, limit: int, filters: schemas.BookingFilterParams
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get all bookings data with filtering and pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Filter parameters

        Returns:
            Tuple of (list of booking dictionaries, total count)
        """
        query = select(models.Booking).options(
            selectinload(models.Booking.booking_status),
            selectinload(models.Booking.payment_status),
            selectinload(models.Booking.car).selectinload(models.Car.car_model),
            selectinload(models.Booking.car).selectinload(models.Car.color),
            selectinload(models.Booking.booker)
            .selectinload(models.User.customer_details)
            .selectinload(models.CustomerDetails.address),
            selectinload(models.Booking.booker)
            .selectinload(models.User.customer_details)
            .selectinload(models.CustomerDetails.tag),
        )

        query = self._apply_admin_booking_filters(query, filters)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = self._apply_sorting(query, filters)

        result = await db.execute(query.offset(skip).limit(limit))
        bookings = result.scalars().all()

        return [self._booking_to_dict(booking) for booking in bookings], total


    def _apply_user_booking_filters(self, query, filters: schemas.BookingFilterParams):
        """
        Apply filters for user bookings.

        Args:
            query: SQLAlchemy query
            filters: Filter parameters

        Returns:
            Modified query
        """
        if filters.search:
            # Need to ensure car, car_model, and color are joined
            query = (
                query.join(models.Booking.car)
                .join(models.CarModel, models.Car.car_model_id == models.CarModel.id)
                .join(models.Color, models.Car.color_id == models.Color.id)
                .where(
                    or_(
                        models.Car.car_no.ilike(f"%{filters.search}%"),
                        models.CarModel.model.ilike(f"%{filters.search}%"),
                        models.CarModel.brand.ilike(f"%{filters.search}%"),
                        models.Color.color_name.ilike(f"%{filters.search}%"),
                    )
                )
            )

        if filters.payment_status:
            ps_alias = aliased(models.Status)
            query = query.join(
                ps_alias, models.Booking.payment_status_id == ps_alias.id
            ).where(func.cast(ps_alias.name, String) == filters.payment_status)

        if filters.booking_status:
            bs_alias = aliased(models.Status)
            query = query.join(
                bs_alias, models.Booking.booking_status_id == bs_alias.id
            ).where(func.cast(bs_alias.name, String) == filters.booking_status)

        if filters.review_rating:
            query = query.join(
                models.Review, models.Booking.id == models.Review.booking_id
            ).where(models.Review.rating == filters.review_rating)

        return query


    def _apply_admin_booking_filters(self, query, filters: schemas.BookingFilterParams):
        """
        Apply filters for admin bookings.

        Args:
            query: SQLAlchemy query
            filters: Filter parameters

        Returns:
            Modified query
        """
        if filters.search:
            # Need to ensure all necessary tables are joined
            query = (
                query.join(models.Booking.car)
                .join(models.CarModel, models.Car.car_model_id == models.CarModel.id)
                .join(models.Color, models.Car.color_id == models.Color.id)
                .join(models.User, models.Booking.booked_by == models.User.id)
                .outerjoin(
                    models.CustomerDetails,
                    models.User.id == models.CustomerDetails.customer_id,
                )
                .outerjoin(models.Tag, models.CustomerDetails.tag_id == models.Tag.id)
                .where(
                    or_(
                        models.Car.car_no.ilike(f"%{filters.search}%"),
                        models.CarModel.model.ilike(f"%{filters.search}%"),
                        models.CarModel.brand.ilike(f"%{filters.search}%"),
                        models.Color.color_name.ilike(f"%{filters.search}%"),
                        models.User.id.ilike(f"%{filters.search}%"),
                        models.User.username.ilike(f"%{filters.search}%"),
                        models.Tag.name.ilike(f"%{filters.search}%"),
                    )
                )
            )

        if filters.payment_status:
            ps_alias = aliased(models.Status)
            query = query.join(
                ps_alias, models.Booking.payment_status_id == ps_alias.id
            ).where(func.cast(ps_alias.name, String) == filters.payment_status)

        if filters.booking_status:
            bs_alias = aliased(models.Status)
            query = query.join(
                bs_alias, models.Booking.booking_status_id == bs_alias.id
            ).where(func.cast(bs_alias.name, String) == filters.booking_status)

        if filters.review_rating:
            query = query.join(
                models.Review, models.Booking.id == models.Review.booking_id
            ).where(models.Review.rating == filters.review_rating)

        return query


    def _apply_sorting(self, query, filters: schemas.BookingFilterParams):
        """
        Apply sorting to query.

        Args:
            query: SQLAlchemy query
            filters: Filter parameters

        Returns:
            Modified query with sorting
        """
        sort_by = filters.sort_by
        sort_order = filters.sort_order.upper()

        if sort_by == "start_time":
            if sort_order == "ASC":
                return query.order_by(models.Booking.start_date.asc())
            else:
                return query.order_by(models.Booking.start_date.desc())
        elif sort_by == "end_time":
            if sort_order == "ASC":
                return query.order_by(models.Booking.end_date.asc())
            else:
                return query.order_by(models.Booking.end_date.desc())
        elif sort_by == "created_at":
            if sort_order == "ASC":
                return query.order_by(models.Booking.created_at.asc())
            else:
                return query.order_by(models.Booking.created_at.desc())

        return query.order_by(models.Booking.start_date.desc())


    async def create_review(self, db: AsyncSession, review_data: Dict[str, Any]) -> models.Review:
        """
        Create a new review.

        Args:
            db: Database session
            review_data: Review data dictionary

        Returns:
            Created review model
        """
        db_review = models.Review(**review_data)
        db.add(db_review)
        await db.commit()
        await db.refresh(db_review)
        return db_review


    async def get_review_by_booking_id(
        self, db: AsyncSession, booking_id: int
    ) -> Optional[models.Review]:
        """
        Get review by booking ID.

        Args:
            db: Database session
            booking_id: Booking ID

        Returns:
            Review model if found, None otherwise
        """
        result = await db.execute(
            select(models.Review).where(models.Review.booking_id == booking_id)
        )
        return result.scalar_one_or_none()


    async def get_additional_payment(
        self, db: AsyncSession, booking_id: int
    ) -> Optional[models.Payment]:
        """
        Get additional payment for a booking.

        Args:
            db: Database session
            booking_id: Booking ID

        Returns:
            Payment model if found, None otherwise
        """
        result = await db.execute(
            select(models.Payment)
            .join(models.Status, models.Payment.status_id == models.Status.id)
            .where(
                models.Payment.booking_id == booking_id,
                models.Payment.payment_type == models.PaymentType.ADD_PAYMENT,
                models.Status.name == "CHARGED",
            )
            .order_by(models.Payment.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


    async def create_booking_from_freeze(
        self,
        db: AsyncSession,
        freeze: models.BookingFreeze,
        remarks: str = None,
        payment_summary: Dict[str, Any] = None,
        referral_benefit: bool = False,
    ) -> models.Booking:
        """
        Create a booking from a booking freeze.

        Args:
            db: Database session
            freeze: Booking freeze model
            remarks: Booking remarks
            payment_summary: Payment summary dictionary
            referral_benefit: Whether referral benefit applies

        Returns:
            Created booking model
        """
        delivery_location = schemas.LocationCreate(
            longitude=freeze.delivery_longitude, latitude=freeze.delivery_latitude
        )

        pickup_location = schemas.LocationCreate(
            longitude=freeze.pickup_longitude, latitude=freeze.pickup_latitude
        )

        delivery_loc = await self.get_location_by_coords(
            db, delivery_location.longitude, delivery_location.latitude
        )
        if not delivery_loc:
            delivery_loc = await self.create_location(db, delivery_location)

        pickup_loc = await self.get_location_by_coords(
            db, pickup_location.longitude, pickup_location.latitude
        )
        if not pickup_loc:
            pickup_loc = await self.create_location(db, pickup_location)

        booked_status = await rbac_crud.get_status_by_name(db, "BOOKED")
        paid_status = await rbac_crud.get_status_by_name(db, "PAID")

        if not booked_status or not paid_status:
            raise NotFoundException("Required statuses not found")

        booking_data = {
            "car_id": freeze.car_id,
            "start_date": freeze.start_date,
            "end_date": freeze.end_date,
            "delivery_id": delivery_loc.id,
            "pickup_id": pickup_loc.id,
            "booked_by": freeze.user_id,
            "remarks": remarks,
            "referral_benefit": referral_benefit,
            "booking_status_id": booked_status.id,
            "payment_status_id": paid_status.id,
            "payment_summary": payment_summary or {},
        }

        db_booking = await self.create_booking(db, booking_data)

        await self.update_booking_freeze(db, freeze.id, {"is_active": False})

        return db_booking


booking_crud = BookingCRUD()