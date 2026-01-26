from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import logging
import io
import csv
import random
import string
from fastapi.responses import StreamingResponse
from azure.storage.blob import generate_blob_sas, BlobSasPermissions


from app import models, schemas
from app.crud import booking_crud, inventory_crud, rbac_crud, user_crud
from app.utils.exception_utils import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from .inventory_services import inventory_service
from app.core.config import settings
from app.utils import notification_utils
from app.utils.geocoding_utils import reverse_geocode
from app.core.dependencies import get_container_client


logger = logging.getLogger(__name__)


class BookingService:
    """
    Service class for handling booking operations and business logic.
    """
    async def _get_valid_offer_discount(
        self, db: AsyncSession
    ) -> tuple[Optional[str], Decimal]:
        """
        Fetch the best valid offer discount from active homepage promotions.
        
        Args:
            db: Database session
        
        Returns:
            tuple: (offer_title, discount_percentage) or (None, Decimal("0"))
        """
        try:
            from sqlalchemy import select
            from datetime import date

            homepage_result = await db.execute(
                select(models.HomePage)
                .where(models.HomePage.is_active.is_(True))
                .limit(1)
            )

            active_homepage = homepage_result.scalar_one_or_none()

            if not active_homepage:
                return (None, Decimal("0"))

            offer_result = await db.execute(
                select(models.HomePagePromotion)
                .where(
                    models.HomePagePromotion.homepage_id == active_homepage.id,
                    models.HomePagePromotion.type == models.PromotionTypeEnum.OFFER,
                    models.HomePagePromotion.timeline >= date.today(),
                )
                .order_by(models.HomePagePromotion.discount.desc())
                .limit(1)
            )

            offer = offer_result.scalar_one_or_none()

            if offer:
                discount_str = offer.discount.replace("%", "").strip()
                discount_percentage = Decimal(discount_str)
                return (offer.title, discount_percentage)

            return (None, Decimal("0"))

        except Exception as e:
            logger.error(f"Error fetching offer discount: {e}")
            return (None, Decimal("0"))


    async def _check_and_apply_referral_benefit(
        self, db: AsyncSession, user: models.User
    ) -> tuple[bool, int]:
        """
        Check if user is eligible for referral benefit and deduct 3 from count.

        Args:
            db: Database session
            user: User model object

        Returns:
            tuple: (is_eligible, remaining_count)
        """
        if user.referral_count >= 3:
            new_count = user.referral_count - 3
            await db.execute(
                models.User.__table__.update()
                .where(models.User.id == user.id)
                .values(referral_count=new_count)
            )
            await db.commit()
            return (True, new_count)

        return (False, user.referral_count)


    async def _refund_referral_benefit(self, db: AsyncSession, user_id: str) -> None:
        """
        Refund 3 referral points back to user on booking cancellation.

        Args:
            db: Database session
            user_id: User ID
        """
        await db.execute(
            models.User.__table__.update()
            .where(models.User.id == user_id)
            .values(referral_count=models.User.referral_count + 3)
        )
        await db.commit()


    async def _refund_rookie_benefit(self, db: AsyncSession, user_id: str) -> None:
        """
        Reset rookie benefit usage on booking cancellation.

        Args:
            db: Database session
            user_id: User ID
        """
        await db.execute(
            models.CustomerDetails.__table__.update()
            .where(models.CustomerDetails.customer_id == user_id)
            .values(rookie_benefit_used=False)
        )
        await db.commit()


    async def _apply_rookie_benefit(self, db: AsyncSession, user_id: str) -> None:
        """
        Mark rookie benefit as used for the user.

        Args:
            db: Database session
            user_id: User ID
        """
        await db.execute(
            models.CustomerDetails.__table__.update()
            .where(models.CustomerDetails.customer_id == user_id)
            .values(rookie_benefit_used=True)
        )
        await db.commit()


    async def _create_payment_summary(
        self,
        db: AsyncSession,
        car: models.Car,
        start_date: datetime,
        end_date: datetime,
        hub_to_delivery: float,
        hub_to_pickup: float,
        user_id: Optional[str] = None,
    ) -> schemas.PaymentSummary:
        """
        Creates a standardized payment summary for bookings with discount logic.
        
        Args:
            db: Database session
            car: Car model object
            start_date: Booking start datetime
            end_date: Booking end datetime
            hub_to_delivery: Distance from hub to delivery location in km
            hub_to_pickup: Distance from hub to pickup location in km
            user_id: User ID for ROOKIE discount and referral benefit check
        
        Returns:
            PaymentSummary object with all calculations including discounts
        """
        total_distance = hub_to_delivery + hub_to_pickup

        delivery_charges = self._calculate_delivery_charges(total_distance)

        duration_hours = Decimal(str((end_date - start_date).total_seconds() / 3600))
        rental_base_amount = duration_hours * car.car_model.dynamic_rental_price
        security_deposit = Decimal("10.0") * car.car_model.dynamic_rental_price

        user = await user_crud.get_user_with_details(db, user_id) if user_id else None

        is_rookie_benefit = False
        if (
            user
            and user.customer_details
            and user.customer_details.rookie_benefit_used is False
        ):
            is_rookie_benefit = True

        delivery_discount = Decimal("0")

        rookie_delivery_discount = Decimal("0")
        if is_rookie_benefit:
            rookie_delivery_discount = delivery_charges
            delivery_discount = delivery_charges

        offer_title, offer_discount_percentage = await self._get_valid_offer_discount(
            db
        )
        offer_discount_amount = Decimal("0")
        if offer_discount_percentage > 0:
            offer_discount_amount = (
                rental_base_amount * offer_discount_percentage
            ) / Decimal("100")

        apply_referral_benefit = user and user.referral_count >= 3

        referral_benefit_amount = Decimal("0")
        if apply_referral_benefit:
            referral_benefit_amount = (
                delivery_charges if not is_rookie_benefit else Decimal("0")
            )
            if not is_rookie_benefit and referral_benefit_amount > 0:
                delivery_discount = referral_benefit_amount

        payment_summary = schemas.PaymentSummary()

        payment_summary.booking_details = {
            "duration_hours": float(duration_hours),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "car_model": f"{car.car_model.brand} {car.car_model.model}",
            "color": car.color.color_name if car.color else "N/A",
            "car_no": car.car_no,
        }

        payment_summary.distance_calculation = {
            "hub_to_delivery_km": float(hub_to_delivery),
            "hub_to_pickup_km": float(hub_to_pickup),
            "total_distance_km": float(total_distance),
            "delivery_charge_tier": "≤30 km" if total_distance <= 30 else "31-60 km",
        }

        subtotal = (
            rental_base_amount
            + delivery_charges
            + Decimal("500.00")
            + security_deposit
            + Decimal("100.00")
        )

        total_payable = subtotal - offer_discount_amount - delivery_discount

        charges_breakdown = {
            "base_rental": float(rental_base_amount),
            "delivery_charges": float(delivery_charges),
            "maintenance_charges": 500.00,
            "security_deposit": float(security_deposit),
            "platform_fee": 100.00,
            "subtotal": float(subtotal),
            "total_payable": float(total_payable),
        }

        if is_rookie_benefit and rookie_delivery_discount > 0:
            charges_breakdown["rookie_discount_applied"] = float(
                rookie_delivery_discount
            )
            charges_breakdown["rookie_discount_description"] = (
                "100% delivery charges waived for first booking"
            )

        if offer_discount_amount > 0:
            charges_breakdown["offer_discount_applied"] = float(offer_discount_amount)
            charges_breakdown["offer_discount_percentage"] = float(
                offer_discount_percentage
            )
            if offer_title:
                charges_breakdown["offer_title"] = offer_title

        if referral_benefit_amount > 0:
            charges_breakdown["referral_benefit_applied"] = float(
                referral_benefit_amount
            )
            charges_breakdown["referral_benefit_description"] = (
                "Delivery charges waived via referral benefit"
            )

        payment_summary.charges_breakdown = charges_breakdown

        free_kilometers = duration_hours * car.car_model.kilometer_limit_per_hr
        payment_summary.kilometer_allowance = {
            "free_kilometers": int(free_kilometers),
            "limit_per_hour": car.car_model.kilometer_limit_per_hr,
            "extra_kilometers": 0,
            "extra_km_charges": 0.0,
        }

        return payment_summary


    def _calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Args:
            lat1: Latitude of first location
            lon1: Longitude of first location
            lat2: Latitude of second location
            lon2: Longitude of second location
        
        Returns:
            Distance in kilometers
        """
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
            math.radians(lat1)
        ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c


    def _calculate_delivery_charges(self, total_distance: float) -> Decimal:
        """
        Calculate delivery charges based on total distance.
        
        Args:
            total_distance: Total distance in kilometers
        
        Returns:
            Delivery charges amount
        """
        if total_distance <= 30:
            return Decimal("1000.00")
        elif total_distance <= 60:
            return Decimal("2000.00")
        else:
            raise BadRequestException("Total distance exceeds 60km limit")


    def _validate_booking_times(self, start_date: datetime, end_date: datetime):
        """
        Validate booking start and end times against business rules.
        
        Args:
            start_date: Booking start datetime
            end_date: Booking end datetime
        
        Returns:
            None
        """
        current_time = datetime.now(timezone.utc)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        min_advance_time = current_time + timedelta(hours=2) - timedelta(minutes=5)
        if start_date < min_advance_time:
            raise BadRequestException("Start time must be at least 2 hours from now")
        if (end_date - start_date) < timedelta(hours=8):
            raise BadRequestException("Booking duration must be at least 8 hours")
        if (start_date - current_time).days > 15:
            raise BadRequestException("Start date cannot be more than 15 days from now")
        if start_date.minute not in [0, 30] or end_date.minute not in [0, 30]:
            raise BadRequestException(
                "Booking times must be in :00 or :30 minute intervals"
            )


    async def _validate_customer_eligibility(self, db: AsyncSession, user_id: str):
        """
        Validate customer eligibility for making bookings.
        
        Args:
            db: Database session
            user_id: User ID to validate
        
        Returns:
            None
        """
        user = await rbac_crud.get_user_by_id(db, user_id)
        if not user:
            raise ForbiddenException("User verification failed.")
        if user.status.name != "ACTIVE":
            raise ForbiddenException(
                f"Your account is {user.status.name.lower()}. Only active accounts can make bookings."
            )
        if not user.customer_details:
            raise ForbiddenException("Complete your profile to make bookings.")
        if not user.customer_details.is_verified:
            raise ForbiddenException(
                "Your account is not verified. Please complete your profile with license and ID documents."
            )
        address = user.customer_details.address
        if not address or not all(
            [address.address_line, address.area, address.state, address.country]
        ):
            raise ForbiddenException(
                "Complete address is required to make bookings. Please fill all address fields."
            )


    def _calculate_exponential_km_charges(self, extra_kilometers: int) -> Decimal:
        """
        Calculate exponential charges for extra kilometers driven.
        
        Args:
            extra_kilometers: Number of extra kilometers beyond free limit
        
        Returns:
            Calculated charge amount
        """
        if extra_kilometers <= 0:
            return Decimal("0.00")
        base_rate = Decimal("10.0")
        exponential_factor = Decimal("1.5")
        if extra_kilometers <= 50:
            charge = Decimal(str(extra_kilometers)) * base_rate
        elif extra_kilometers <= 100:
            tier1_charge = Decimal("50") * base_rate
            tier2_extra = extra_kilometers - 50
            charge = tier1_charge + (Decimal(str(tier2_extra)) ** exponential_factor)
        else:
            tier1_charge = Decimal("50") * base_rate
            tier2_charge = Decimal("50") ** exponential_factor
            tier3_extra = extra_kilometers - 100
            charge = (
                tier1_charge
                + tier2_charge
                + (Decimal(str(tier3_extra)) ** (exponential_factor + Decimal("0.5")))
            )
        return charge.quantize(Decimal("0.01"))


    def _calculate_late_charges(
        self, expected_end_time: datetime, actual_return_time: datetime
    ) -> tuple[Decimal, int, str]:
        """
        Calculate late return charges with 30-minute grace period.
        
        Args:
            expected_end_time: Expected booking end time
            actual_return_time: Actual return timestamp
        
        Returns:
            tuple: (late_charge_amount, late_hours, calculation_details)
        """
        if actual_return_time.tzinfo is None:
            actual_return_time = actual_return_time.replace(tzinfo=timezone.utc)
        if expected_end_time.tzinfo is None:
            expected_end_time = expected_end_time.replace(tzinfo=timezone.utc)
        delay_minutes = (actual_return_time - expected_end_time).total_seconds() / 60
        if delay_minutes <= 30:
            return Decimal("0.00"), 0, "Within grace period (30 minutes)"
        chargeable_minutes = delay_minutes - 30
        chargeable_hours = int(chargeable_minutes / 60)
        remaining_minutes = chargeable_minutes % 60
        if remaining_minutes > 0:
            chargeable_hours += 1
        base_rate = Decimal("100.0")
        exponential_factor = Decimal("1.3")
        if chargeable_hours == 0:
            return Decimal("0.00"), 0, "Within grace period"
        elif chargeable_hours <= 3:
            charge = Decimal(str(chargeable_hours)) * base_rate
            details = f"{chargeable_hours} hour(s) × ₹{base_rate} = ₹{charge}"
        elif chargeable_hours <= 6:
            tier1_charge = Decimal("3") * base_rate
            tier2_hours = chargeable_hours - 3
            tier2_charge = (Decimal(str(tier2_hours)) ** exponential_factor) * base_rate
            charge = tier1_charge + tier2_charge
            details = f"First 3 hrs: ₹{tier1_charge}, Next {tier2_hours} hr(s): ₹{tier2_charge.quantize(Decimal('0.01'))}"
        else:
            tier1_charge = Decimal("3") * base_rate
            tier2_charge = (Decimal("3") ** exponential_factor) * base_rate
            tier3_hours = chargeable_hours - 6
            tier3_charge = (
                Decimal(str(tier3_hours)) ** (exponential_factor + Decimal("0.5"))
            ) * base_rate
            charge = tier1_charge + tier2_charge + tier3_charge
            details = f"First 3 hrs: ₹{tier1_charge}, Next 3 hrs: ₹{tier2_charge.quantize(Decimal('0.01'))}, Next {tier3_hours} hr(s): ₹{tier3_charge.quantize(Decimal('0.01'))}"
        return charge.quantize(Decimal("0.01")), chargeable_hours, details


    def _generate_otp(self, length: int = 6) -> str:
        """
        Generate a random numeric OTP.
        
        Args:
            length: Length of OTP to generate
        
        Returns:
            Generated OTP string
        """
        return "".join(random.choices(string.digits, k=length))


    async def _verify_blob_exists(self, blob_url: str) -> bool:
        """
        Verifies that a blob exists in Azure Blob Storage.
        
        Args:
            blob_url: Full URL of the blob (may include query parameters/SAS tokens)
        
        Returns:
            bool: True if blob exists, False otherwise
        """
        try:
            from urllib.parse import urlparse

            parsed_url = urlparse(blob_url)
            path_parts = parsed_url.path.strip("/").split("/", 1)
            if len(path_parts) < 2:
                logger.warning(f"Invalid blob URL format: {blob_url}")
                return False
            
            container_name = path_parts[0]
            blob_name = path_parts[1]
            container_client = await get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)

            exists = await blob_client.exists()
            return exists
        
        except Exception as e:
            logger.error(f"Error verifying blob existence: {e}")
            return False


    async def generate_video_upload_sas_url(
        self,
        db: AsyncSession,
        booking_id: int,
        video_type: str,
        user_id: Optional[str] = None,
    ) -> schemas.VideoUploadSASResponse:
        """
        Generates a short-lived SAS URL for uploading a video to Azure Blob Storage.
        
        Args:
            db: Database session
            booking_id: Booking ID
            video_type: Type of video ('delivery' or 'pickup')
            user_id: User ID (optional, not used in new flow)
        
        Returns:
            VideoUploadSASResponse: SAS URL and related information
        """
        if video_type not in ["delivery", "pickup"]:
            raise BadRequestException("video_type must be 'delivery' or 'pickup'")
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")
        if video_type == "delivery":
            if booking_data["delivery_video_url"]:
                raise BadRequestException("Delivery video already uploaded")
            if booking_data["booking_status"] != "BOOKED":
                raise BadRequestException(
                    "Booking must be in BOOKED status to upload delivery video"
                )
        else:
            if booking_data["pickup_video_url"]:
                raise BadRequestException("Pickup video already uploaded")
            if booking_data["booking_status"] != "RETURNING":
                raise BadRequestException(
                    "Booking must be in RETURNING status to upload pickup video"
                )
        
        try:
            container_client = await get_container_client(settings.BOOKING_CONTAINER_NAME)
            blob_name = f"booking_{booking_id}_{video_type}.mp4"
            from datetime import timezone as tz
            expiry_time = datetime.now(tz.utc) + timedelta(minutes=10)
            conn_dict = {}
            for part in settings.AZURE_STORAGE_CONNECTION_STRING.split(";"):
                if "=" in part:
                    key, value = part.split("=", 1)
                    conn_dict[key.strip()] = value.strip()
            account_name = conn_dict.get("AccountName")
            account_key = conn_dict.get("AccountKey")

            if not account_name or not account_key:
                raise BadRequestException(
                    "Invalid Azure Storage connection string configuration"
                )
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=settings.BOOKING_CONTAINER_NAME,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(write=True, create=True),
                expiry=expiry_time,
            )
            blob_client = container_client.get_blob_client(blob_name)
            blob_url = blob_client.url
            sas_url = f"{blob_url}?{sas_token}"

            return schemas.VideoUploadSASResponse(
                sas_url=sas_url,
                blob_url=blob_url,
                blob_name=blob_name,
                expires_at=expiry_time,
                container_name=settings.BOOKING_CONTAINER_NAME,
            )
        
        except Exception as e:
            logger.error(f"Error generating SAS URL: {e}")
            raise BadRequestException("Failed to generate SAS URL")


    def _apply_4_hour_gap(
        self, start: datetime, end: datetime
    ) -> tuple[datetime, datetime]:
        """
        Apply 4-hour gap buffer to booking time range.
        
        Args:
            start: Start datetime
            end: End datetime
        
        Returns:
            tuple: (adjusted_start, adjusted_end)
        """
        return start - timedelta(hours=4), end + timedelta(hours=4)


    async def _check_customer_booking_overlap(
        self, db: AsyncSession, user_id: str, start: datetime, end: datetime
    ):
        """
        Check if customer has overlapping bookings or freezes.
        
        Args:
            db: Database session
            user_id: User ID
            start: Start datetime
            end: End datetime
        
        Returns:
            None
        """
        start_with_gap, end_with_gap = self._apply_4_hour_gap(start, end)
        blocking_statuses = ["BOOKED", "DELIVERED", "RETURNED"]

        overlapping_bookings = await booking_crud.get_customer_overlapping_bookings(
            db, user_id, start_with_gap, end_with_gap, blocking_statuses
        )

        active_freezes = await booking_crud.get_customer_active_freezes(
            db, user_id, start_with_gap, end_with_gap
        )

        if overlapping_bookings or active_freezes:
            raise BadRequestException(
                "You already have a booking or freeze that overlaps with this time period. "
                "Please choose a different time slot with at least 4 hours gap between bookings."
            )


    async def get_freeze_booking(
        self, db: AsyncSession, freeze_id: int, user_id: str
    ) -> schemas.FreezeBookingResponse:
        """
        Retrieve freeze booking details for confirmation.
        
        Args:
            db: Database session
            freeze_id: Freeze ID
            user_id: User ID
        
        Returns:
            FreezeBookingResponse with car details and payment summary
        """
        freeze = await booking_crud.get_booking_freeze_by_id(db, freeze_id)
        if not freeze:
            raise NotFoundException("Freeze not found")

        if freeze.user_id != user_id:
            raise ForbiddenException("Cannot access another user's freeze")

        if not freeze.is_active:
            raise ForbiddenException("Freeze is not active")

        if freeze.freeze_expires_at < datetime.now(timezone.utc):
            raise ForbiddenException("Freeze has expired")

        car = await inventory_crud.get_car_by_id(db, freeze.car_id)
        if not car:
            raise NotFoundException("Car not found")

        if car.status.name != "ACTIVE":
            raise BadRequestException("Car is not available for booking")

        carinfo = await inventory_service.get_car(db, freeze.car_id)

        hub_to_delivery = self._calculate_distance(
            settings.HUB_LATITUDE,
            settings.HUB_LONGITUDE,
            freeze.delivery_latitude,
            freeze.delivery_longitude,
        )

        hub_to_pickup = self._calculate_distance(
            settings.HUB_LATITUDE,
            settings.HUB_LONGITUDE,
            freeze.pickup_latitude,
            freeze.pickup_longitude,
        )

        total_distance = hub_to_delivery + hub_to_pickup

        if total_distance > 60:
            raise BadRequestException(
                f"Total distance ({total_distance:.1f} km) exceeds 60km limit"
            )

        payment_summary = await self._create_payment_summary(
            db,
            car,
            freeze.start_date,
            freeze.end_date,
            hub_to_delivery,
            hub_to_pickup,
            user_id,
        )

        return schemas.FreezeBookingResponse(
            freeze_id=freeze.id,
            car_details=carinfo,
            start_time=freeze.start_date,
            end_time=freeze.end_date,
            delivery_location=schemas.LocationBase(
                longitude=freeze.delivery_longitude,
                latitude=freeze.delivery_latitude,
            ),
            pickup_location=schemas.LocationBase(
                longitude=freeze.pickup_longitude,
                latitude=freeze.pickup_latitude,
            ),
            freeze_expires_at=freeze.freeze_expires_at,
            payment_summary=payment_summary,
        )


    async def freeze_booking(
        self, db: AsyncSession, freeze_in: schemas.FreezeCreate, user_id: str
    ) -> schemas.EstimateResponse:
        """
        Create a temporary booking freeze for a car.
        
        Args:
            db: Database session
            freeze_in: Freeze creation data
            user_id: User ID
        
        Returns:
            EstimateResponse with freeze details and payment summary
        """
        await self._validate_customer_eligibility(db, user_id)

        self._validate_booking_times(freeze_in.start_date, freeze_in.end_date)

        await self._check_customer_booking_overlap(
            db, user_id, freeze_in.start_date, freeze_in.end_date
        )

        car = await inventory_crud.get_car_by_id(db, freeze_in.car_id)
        if not car:
            raise NotFoundException("Car not found")

        if car.status.name != "ACTIVE":
            raise BadRequestException("Car is not available for booking")

        start_with_gap, end_with_gap = self._apply_4_hour_gap(
            freeze_in.start_date, freeze_in.end_date
        )

        overlapping_freezes = await booking_crud.get_customer_active_freezes(
            db, user_id, freeze_in.start_date, freeze_in.end_date
        )
        if overlapping_freezes:
            raise BadRequestException(
                "You already have an active freeze that overlaps with this time period."
            )

        active_freezes = await booking_crud.get_active_freezes_for_car(
            db, freeze_in.car_id, start_with_gap, end_with_gap
        )
        if active_freezes:
            raise BadRequestException(
                "This time slot is currently being booked by another user"
            )

        is_available = await booking_crud.check_car_availability(
            db, freeze_in.car_id, start_with_gap, end_with_gap
        )
        if not is_available:
            next_available = await booking_crud.get_next_available_time(
                db, freeze_in.car_id
            )
            next_available_str = (
                next_available.strftime("%Y-%m-%d %H:%M") if next_available else "N/A"
            )
            raise BadRequestException(
                f"Car is not available for the selected dates. "
                f"Next available from: {next_available_str}"
            )

        hub_to_delivery = self._calculate_distance(
            settings.HUB_LATITUDE,
            settings.HUB_LONGITUDE,
            freeze_in.delivery_location.latitude,
            freeze_in.delivery_location.longitude,
        )

        hub_to_pickup = self._calculate_distance(
            settings.HUB_LATITUDE,
            settings.HUB_LONGITUDE,
            freeze_in.pickup_location.latitude,
            freeze_in.pickup_location.longitude,
        )

        total_distance = hub_to_delivery + hub_to_pickup

        if total_distance > 60:
            raise BadRequestException(
                f"Total distance ({total_distance:.1f} km) exceeds 60km limit"
            )

        user = await user_crud.get_user_with_details(db, user_id)
        if not user:
            raise NotFoundException("User not found")

        payment_summary = await self._create_payment_summary(
            db,
            car,
            freeze_in.start_date,
            freeze_in.end_date,
            hub_to_delivery,
            hub_to_pickup,
            user_id,
        )

        freeze_data = {
            "car_id": freeze_in.car_id,
            "user_id": user_id,
            "start_date": freeze_in.start_date,
            "end_date": freeze_in.end_date,
            "freeze_expires_at": datetime.now(timezone.utc) + timedelta(minutes=7),
            "is_active": True,
        }

        freeze = await booking_crud.create_booking_freeze(
            db, freeze_data, freeze_in.delivery_location, freeze_in.pickup_location
        )

        return schemas.EstimateResponse(
            freeze_id=freeze.id,
            freeze_expires_at=freeze.freeze_expires_at,
            payment_summary=payment_summary,
            car_details={
                "id": car.id,
                "car_no": car.car_no,
                "brand": car.car_model.brand,
                "model": car.car_model.model,
                "color": car.color.color_name if car.color else "N/A",
                "image_urls": car.image_urls,
            },
        )


    async def create_booking_from_freeze(
        self,
        db: AsyncSession,
        freeze_id: int,
        payment_in: schemas.PaymentInitiationRequest,
        user_id: str,
    ) -> schemas.BookingDetailed:
        """
        Create a confirmed booking from a valid freeze.
        
        Args:
            db: Database session
            freeze_id: Freeze ID
            payment_in: Payment initiation data
            user_id: User ID
        
        Returns:
            BookingDetailed with complete booking information
        """
        freeze = await booking_crud.get_booking_freeze_by_id(db, freeze_id)
        if not freeze:
            raise NotFoundException("Freeze not found")

        if freeze.user_id != user_id:
            raise ForbiddenException("Cannot create booking from another user's freeze")

        if not freeze.is_active or freeze.freeze_expires_at < datetime.now(
            timezone.utc
        ):
            raise BadRequestException("Freeze has expired")

        car = await inventory_crud.get_car_by_id(db, freeze.car_id)
        if not car:
            raise NotFoundException("Car not found")

        start_with_gap, end_with_gap = self._apply_4_hour_gap(
            freeze.start_date, freeze.end_date
        )

        is_available = await booking_crud.check_car_availability(
            db, freeze.car_id, start_with_gap, end_with_gap
        )
        if not is_available:
            raise BadRequestException(
                "Car is no longer available for the selected dates"
            )

        hub_to_delivery = self._calculate_distance(
            settings.HUB_LATITUDE,
            settings.HUB_LONGITUDE,
            freeze.delivery_latitude,
            freeze.delivery_longitude,
        )

        hub_to_pickup = self._calculate_distance(
            settings.HUB_LATITUDE,
            settings.HUB_LONGITUDE,
            freeze.pickup_latitude,
            freeze.pickup_longitude,
        )

        payment_summary = await self._create_payment_summary(
            db,
            car,
            freeze.start_date,
            freeze.end_date,
            hub_to_delivery,
            hub_to_pickup,
            user_id,
        )

        user = await user_crud.get_user_with_details(db, user_id)

        referral_benefit = False

        if user:
            if (
                user.customer_details.tag.name == models.Tags.ROOKIE
                and user.customer_details.rookie_benefit_used is False
            ):
                await self._apply_rookie_benefit(db, user_id)
            elif user.referral_count >= 3:
                referral_benefit, new_referral_count = (
                    await self._check_and_apply_referral_benefit(db, user)
                )

        booking = await booking_crud.create_booking_from_freeze(
            db=db,
            freeze=freeze,
            remarks=payment_in.remarks,
            payment_summary=payment_summary.model_dump(),
            referral_benefit=referral_benefit,
        )

        await notification_utils.send_system_notification(
            db,
            receiver_id=user_id,
            subject=f"Booking #{booking.id} Created",
            body="Your booking has been created successfully.",
            type=models.NotificationType.BOOKING,
        )

        booking_data = await booking_crud.get_booking_data_by_id(db, booking.id)
        return schemas.BookingDetailed(**booking_data)


    async def update_freeze_locations(
        self,
        db: AsyncSession,
        freeze_id: int,
        update_in: schemas.FreezeUpdate,
        user_id: str,
    ) -> schemas.EstimateResponse:
        """
        Update delivery and pickup locations for an active freeze.
        
        Args:
            db: Database session
            freeze_id: Freeze ID
            update_in: Location update data
            user_id: User ID
        
        Returns:
            EstimateResponse with updated payment summary
        """
        freeze = await booking_crud.get_booking_freeze_by_id(db, freeze_id)
        if not freeze:
            raise NotFoundException("Freeze not found")

        if freeze.user_id != user_id:
            raise ForbiddenException("Cannot update another user's freeze")

        if not freeze.is_active or freeze.freeze_expires_at < datetime.now(
            timezone.utc
        ):
            raise BadRequestException("Freeze has expired")

        car = await inventory_crud.get_car_by_id(db, freeze.car_id)
        if not car:
            raise NotFoundException("Car not found")

        if not update_in.delivery_location or not update_in.pickup_location:
            raise BadRequestException(
                "Both delivery and pickup locations must be provided"
            )

        hub_to_delivery = self._calculate_distance(
            settings.HUB_LATITUDE,
            settings.HUB_LONGITUDE,
            update_in.delivery_location.latitude,
            update_in.delivery_location.longitude,
        )

        hub_to_pickup = self._calculate_distance(
            settings.HUB_LATITUDE,
            settings.HUB_LONGITUDE,
            update_in.pickup_location.latitude,
            update_in.pickup_location.longitude,
        )

        total_distance = hub_to_delivery + hub_to_pickup

        if total_distance > 60:
            raise BadRequestException(
                f"Total distance ({total_distance:.1f} km) exceeds 60km limit"
            )

        update_data = {
            "delivery_longitude": update_in.delivery_location.longitude,
            "delivery_latitude": update_in.delivery_location.latitude,
            "pickup_longitude": update_in.pickup_location.longitude,
            "pickup_latitude": update_in.pickup_location.latitude,
        }

        updated_freeze = await booking_crud.update_booking_freeze(
            db, freeze_id, update_data
        )
        if not updated_freeze:
            raise NotFoundException("Failed to update freeze locations")

        payment_summary = await self._create_payment_summary(
            db,
            car,
            freeze.start_date,
            freeze.end_date,
            hub_to_delivery,
            hub_to_pickup,
            user_id,
        )

        return schemas.EstimateResponse(
            freeze_id=freeze.id,
            freeze_expires_at=freeze.freeze_expires_at,
            payment_summary=payment_summary,
            car_details={
                "id": car.id,
                "car_no": car.car_no,
                "brand": car.car_model.brand,
                "model": car.car_model.model,
                "color": car.color.color_name if car.color else "N/A",
                "image_urls": car.image_urls,
            },
        )


    async def cancel_freeze(
        self, db: AsyncSession, freeze_id: int, user_id: str
    ) -> schemas.Msg:
        """
        Cancel an active freeze.
        
        Args:
            db: Database session
            freeze_id: Freeze ID
            user_id: User ID
        
        Returns:
            Msg with cancellation confirmation
        """
        freeze = await booking_crud.get_booking_freeze_by_id(db, freeze_id)
        if not freeze:
            raise NotFoundException("Freeze not found")

        if freeze.user_id != user_id:
            raise ForbiddenException("Cannot cancel another user's freeze")

        await booking_crud.delete_booking_freeze(db, freeze_id)

        return schemas.Msg(message="Freeze cancelled successfully")


    async def process_delivery(
        self,
        db: AsyncSession,
        booking_id: int,
        delivery_input: schemas.ProcessDeliveryInput,
    ) -> schemas.Msg:
        """
        Admin processes delivery by uploading video, recording start kilometers, and generating OTP for customer.
        
        Args:
            db: Database session
            booking_id: Booking ID
            delivery_input: Delivery processing data
        
        Returns:
            Msg with confirmation
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booking_status"] != "BOOKED":
            raise BadRequestException(
                "Booking must be in BOOKED status to process delivery"
            )

        if booking_data["delivery_video_url"]:
            raise BadRequestException("Delivery already processed")
        
        blob_exists = await self._verify_blob_exists(delivery_input.delivery_video_url)
        if not blob_exists:
            raise BadRequestException(
                "Video blob not found in storage. Please ensure the video was uploaded successfully."
            )

        delivery_otp = self._generate_otp()
        current_time = datetime.now(timezone.utc)

        await booking_crud.update_booking(
            db,
            booking_id,
            {
                "delivery_video_url": delivery_input.delivery_video_url,
                "start_kilometers": delivery_input.start_kilometers,
                "delivery_otp": delivery_otp,
                "delivery_otp_generated_at": current_time,
            },
        )

        await booking_crud.update_payment_summary(
            db,
            booking_id,
            {
                "delivery_verification": {
                    "admin_video_url": delivery_input.delivery_video_url,
                    "start_kilometers": delivery_input.start_kilometers,
                    "delivery_otp_generated_at": current_time.isoformat(),
                    "video_uploaded_at": current_time.isoformat(),
                }
            },
        )
        await notification_utils.send_system_notification(
            db,
            receiver_id=booking_data["booked_by"],
            subject=f"Delivery OTP for Booking #{booking_id}",
            body=f"Your delivery OTP is: {delivery_otp}. Share this with the admin for verification.",
            type=models.NotificationType.BOOKING,
        )

        return schemas.Msg(
            message="Delivery processed successfully. OTP has been sent to customer."
        )


    async def request_return(
        self,
        db: AsyncSession,
        booking_id: int,
        return_request: schemas.ReturnRequest,
        user_id: str,
    ) -> schemas.ReturnRequestResponse:
        """
        Customer initiates return request before reaching pickup location.
        
        Args:
            db: Database session
            booking_id: Booking ID
            return_request: Return request data
            user_id: User ID
        
        Returns:
            ReturnRequestResponse with confirmation
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booked_by"] != user_id:
            raise ForbiddenException("Cannot request return for another user's booking")

        if booking_data["booking_status"] != "DELIVERED":
            raise BadRequestException(
                "Booking must be in DELIVERED status to request return"
            )

        # Validate expected return time is not in the past
        current_time = datetime.now(timezone.utc)
        expected_return = return_request.expected_return_time
        if expected_return.tzinfo is None:
            expected_return = expected_return.replace(tzinfo=timezone.utc)

        if expected_return < current_time:
            raise BadRequestException("Expected return time cannot be in the past")

        start_date = booking_data["start_date"]
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)

        if expected_return <= start_date:
            raise BadRequestException(
                "Expected return time must be strictly after the booking start time"
            )

        if expected_return.minute not in [0, 30] or expected_return.second != 0:
            raise BadRequestException(
                "Return time must be in 30-minute intervals (e.g., 2:00, 2:30)"
            )
        returning_status = await rbac_crud.get_status_by_name(db, "RETURNING")
        if not returning_status:
            raise NotFoundException("RETURNING status not found in database")
        await booking_crud.update_booking(
            db, booking_id, {"return_requested_at": current_time}
        )
        await booking_crud.update_booking_status(db, booking_id, returning_status.id)
        pickup_location = booking_data.get("pickup_location", {})
        await booking_crud.update_payment_summary(
            db,
            booking_id,
            {
                "return_request": {
                    "requested_at": current_time.isoformat(),
                    "expected_return_time": expected_return.isoformat(),
                    "remarks": return_request.remarks,
                }
            },
        )
        admin_role = await rbac_crud.get_role_by_name(db, "ADMIN")
        if admin_role:
            admin_users = await rbac_crud.get_users_by_role_id(db, admin_role.id)
            for admin in admin_users:
                await notification_utils.send_system_notification(
                    db,
                    receiver_id=admin.id,
                    subject=f"Return Request: Booking #{booking_id}",
                    body=f"Customer has requested return at {expected_return.strftime('%Y-%m-%d %H:%M')}. Check pickup location in booking details.",
                    type=models.NotificationType.BOOKING,
                )
        await notification_utils.send_system_notification(
            db,
            receiver_id=user_id,
            subject=f"Return Request Received: Booking #{booking_id}",
            body=f"Your return request has been received. Admin will meet you at the pickup location at {expected_return.strftime('%Y-%m-%d %H:%M')}.",
            type=models.NotificationType.BOOKING,
        )

        return schemas.ReturnRequestResponse(
            message="Return request submitted successfully. Admin will meet you at the pickup location.",
            booking_id=booking_id,
            status="RETURNING",
            expected_return_time=expected_return,
        )


    async def get_delivery_otp(
        self, db: AsyncSession, booking_id: int, user_id: str
    ) -> schemas.OTPResponse:
        """
        Customer retrieves their delivery OTP to share with admin.
        
        Args:
            db: Database session
            booking_id: Booking ID
            user_id: User ID
        
        Returns:
            OTPResponse with OTP details
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booked_by"] != user_id:
            raise ForbiddenException("Cannot access OTP for another user's booking")

        if not booking_data["delivery_video_url"]:
            raise BadRequestException("Admin has not uploaded delivery video yet")

        if not booking_data["delivery_otp"]:
            raise BadRequestException("Delivery OTP not generated yet")

        return schemas.OTPResponse(
            otp=booking_data["delivery_otp"],
            generated_at=booking_data["delivery_otp_generated_at"],
            message="Share this OTP with admin for delivery verification",
        )


    async def verify_delivery_otp(
        self, db: AsyncSession, booking_id: int, otp_data: schemas.OTPVerify
    ) -> schemas.BookingAdminDetailed:
        """
        Admin verifies delivery OTP provided by customer.
        
        Args:
            db: Database session
            booking_id: Booking ID
            otp_data: OTP verification data
        
        Returns:
            BookingAdminDetailed with updated booking information
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booking_status"] != "BOOKED":
            raise BadRequestException("Booking must be in BOOKED status for delivery")

        if not booking_data["delivery_video_url"]:
            raise BadRequestException("Delivery must be processed first")

        if booking_data["start_kilometers"] is None:
            raise BadRequestException("Start kilometers not recorded")

        if not booking_data["delivery_otp"]:
            raise BadRequestException("Delivery OTP not generated yet")

        if booking_data["delivery_otp"] != otp_data.otp:
            raise BadRequestException("Invalid delivery OTP provided by customer")

        if booking_data["delivery_otp_verified"]:
            raise BadRequestException("Delivery OTP already verified")

        delivered_status = await rbac_crud.get_status_by_name(db, "DELIVERED")
        if not delivered_status:
            raise NotFoundException("Delivered status not found")

        current_time = datetime.now(timezone.utc)
        await booking_crud.update_booking(
            db,
            booking_id,
            {"delivery_otp_verified": True, "delivery_otp_verified_at": current_time},
        )

        await booking_crud.update_booking_status(db, booking_id, delivered_status.id)

        await booking_crud.update_payment_summary(
            db,
            booking_id,
            {
                "delivery_verification": {
                    "delivery_otp_verified": True,
                    "delivery_otp_verified_at": current_time.isoformat(),
                    "delivered_at": current_time.isoformat(),
                    "admin_verified": True,
                }
            },
        )

        await notification_utils.send_system_notification(
            db,
            receiver_id=booking_data["booked_by"],
            subject=f"Booking #{booking_id} Delivered",
            body="Your car has been delivered successfully.",
            type=models.NotificationType.BOOKING,
        )

        updated_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        return schemas.BookingAdminDetailed(**updated_data)


    async def process_return(
        self, db: AsyncSession, booking_id: int, return_in: schemas.ProcessReturnInput
    ) -> schemas.BookingAdminDetailed:
        """
        Admin processes return by uploading pickup video and recording final details.
        
        Args:
            db: Database session
            booking_id: Booking ID
            return_in: Return processing data
        
        Returns:
            BookingAdminDetailed with updated booking information
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booking_status"] != "RETURNING":
            raise BadRequestException(
                "Booking must be in RETURNING status for return processing. Customer must request return first."
            )

        if booking_data["pickup_video_url"]:
            raise BadRequestException("Pickup video already uploaded")
        
        blob_exists = await self._verify_blob_exists(return_in.pickup_video_url)
        if not blob_exists:
            raise BadRequestException(
                "Pickup video blob not found in storage. Please ensure the video was uploaded successfully."
            )

        start_km = booking_data.get("start_kilometers")
        if start_km is None:
            raise BadRequestException("Start kilometers not recorded")

        actual_kilometers = return_in.end_kilometers - start_km
        free_kilometers = (
            booking_data["payment_summary"]
            .get("kilometer_allowance", {})
            .get("free_kilometers", 0)
        )
        extra_kilometers = max(0, actual_kilometers - free_kilometers)
        extra_km_charges = self._calculate_exponential_km_charges(extra_kilometers)
        expected_end_time = booking_data["end_date"]
        actual_return_time = return_in.returned_at
        start_date = booking_data["start_date"]
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)

        if actual_return_time.tzinfo is None:
            actual_return_time = actual_return_time.replace(tzinfo=timezone.utc)

        if actual_return_time <= start_date:
            raise BadRequestException(
                "Actual return time must be strictly after the booking start time"
            )

        if actual_return_time.minute not in [0, 30] or actual_return_time.second != 0:
            raise BadRequestException(
                "Return time must be in 30-minute intervals (e.g., 2:00, 2:30)"
            )

        late_charges, late_hours, late_charge_details = self._calculate_late_charges(
            expected_end_time, actual_return_time
        )
        total_extra_charges = (
            sum(Decimal(str(charge.amount)) for charge in return_in.extra_charges)
            + extra_km_charges
            + late_charges
        )

        security_deposit = Decimal(
            str(
                booking_data["payment_summary"]
                .get("charges_breakdown", {})
                .get("security_deposit", 0)
            )
        )

        base_amount = Decimal(
            str(
                booking_data["payment_summary"]
                .get("charges_breakdown", {})
                .get("base_rental", 0)
            )
        )

        base_rental_payable = base_amount
        settlement_amount = security_deposit - total_extra_charges
        current_time = datetime.now(timezone.utc)
        if settlement_amount == Decimal("0.00"):
            scenario = "SETTLED"
            payment_record_amount = Decimal("0.00")
            settlement_status = "SETTLED"
            new_payment_status = "SETTLED"
            pickup_otp = self._generate_otp()

        elif settlement_amount > Decimal("0.00"):
            scenario = "REFUNDING"
            payment_record_amount = settlement_amount
            settlement_status = "REFUNDING"
            new_payment_status = "REFUNDING"
            pickup_otp = self._generate_otp()

        else:
            scenario = "INITIATED"
            payment_record_amount = abs(settlement_amount)
            settlement_status = "INITIATED"
            new_payment_status = "INITIATED"
            pickup_otp = None

        returned_status = await rbac_crud.get_status_by_name(db, "RETURNED")
        payment_status_obj = await rbac_crud.get_status_by_name(db, new_payment_status)

        if not returned_status or not payment_status_obj:
            raise NotFoundException("Required statuses not found")

        update_data = {
            "pickup_video_url": return_in.pickup_video_url,
            "end_kilometers": return_in.end_kilometers,
        }

        if pickup_otp:
            update_data.update(
                {"pickup_otp": pickup_otp, "pickup_otp_generated_at": current_time}
            )

            # Notify customer with pickup OTP
            await notification_utils.send_system_notification(
                db,
                receiver_id=booking_data["booked_by"],
                subject=f"Pickup OTP for Booking #{booking_id}",
                body=f"Your pickup OTP is: {pickup_otp}. Share this with the admin for verification.",
                type=models.NotificationType.BOOKING,
            )

        await booking_crud.update_booking(db, booking_id, update_data)

        extra_charges_breakdown = [
            {
                "type": "extra_kilometers",
                "amount": float(extra_km_charges),
                "specification": f"{extra_kilometers} km beyond free limit",
                "calculation_details": "Exponential calculation",
            }
        ]
        if late_charges > 0:
            extra_charges_breakdown.append(
                {
                    "type": "late_return_charges",
                    "amount": float(late_charges),
                    "specification": f"{late_hours} hour(s) late (30 min grace period applied)",
                    "calculation_details": late_charge_details,
                }
            )
        extra_charges_breakdown += [
            {
                "type": charge.type,
                "amount": float(charge.amount),
                "specification": charge.specification,
                "calculation_details": charge.calculation_details,
            }
            for charge in return_in.extra_charges
        ]

        summary_updates = {
            "return_verification": {
                "admin_video_url": return_in.pickup_video_url,
                "end_kilometers": return_in.end_kilometers,
                "returned_at": actual_return_time.isoformat(),
                "expected_return_time": expected_end_time.isoformat(),
                "actual_return_time": actual_return_time.isoformat(),
                "late_hours": late_hours,
            },
            "extra_charges_calculation": {
                "extra_kilometers": extra_kilometers,
                "extra_km_charges": float(extra_km_charges),
                "late_return_charges": float(late_charges),
                "damage_charges": float(
                    sum(
                        Decimal(str(charge.amount))
                        for charge in return_in.extra_charges
                        if charge.type.lower() in ["damage_charges", "damage"]
                    )
                ),
                "other_charges": float(
                    sum(
                        Decimal(str(charge.amount))
                        for charge in return_in.extra_charges
                        if charge.type.lower() not in ["damage_charges", "damage"]
                    )
                ),
                "charges_breakdown": extra_charges_breakdown,
                "total_extra_charges": float(total_extra_charges),
                "calculated_at": current_time.isoformat(),
            },
            "settlement": {
                "scenario": scenario,
                "additional_amount_due": (
                    float(payment_record_amount) if scenario == "INITIATED" else 0.0
                ),
                "refund_amount": (
                    float(payment_record_amount) if scenario == "REFUNDING" else 0.0
                ),
                "base_rental_payable": float(base_rental_payable),
                "security_deposit": float(security_deposit),
                "total_extra_charges": float(total_extra_charges),
                "settlement_status": settlement_status,
                "settlement_remarks": return_in.settlement_remarks,
            },
        }

        if pickup_otp:
            summary_updates["return_verification"][
                "pickup_otp_generated_at"
            ] = current_time.isoformat()
        await booking_crud.update_payment_summary(db, booking_id, summary_updates)

        await booking_crud.update_booking_and_payment_status(
            db, booking_id, returned_status.id, payment_status_obj.id
        )

        if scenario != "SETTLED" or payment_record_amount != Decimal("0.00"):
            from .payment_services import payment_service

            if scenario == "INITIATED":
                remarks = f"Additional settlement charges: Extra km (₹{extra_km_charges:.2f}) + other charges"
                await payment_service.create_settlement_payment(
                    db=db,
                    booking_id=booking_id,
                    settlement_type="INITIATED",
                    amount=payment_record_amount,
                    remarks=remarks,
                )
            elif scenario == "REFUNDING":
                remarks = f"Refund due: Security deposit ({security_deposit}) - Extra charges ({total_extra_charges})"
                await payment_service.create_settlement_payment(
                    db=db,
                    booking_id=booking_id,
                    settlement_type="REFUNDING",
                    amount=payment_record_amount,
                    remarks=remarks,
                )

        updated_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        return schemas.BookingAdminDetailed(**updated_data)


    async def get_pickup_otp(
        self, db: AsyncSession, booking_id: int, user_id: str
    ) -> schemas.OTPResponse:
        """
        Customer retrieves their pickup OTP to share with admin.
        
        Args:
            db: Database session
            booking_id: Booking ID
            user_id: User ID
        
        Returns:
            OTPResponse with OTP details
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booked_by"] != user_id:
            raise ForbiddenException("Cannot access OTP for another user's booking")

        if booking_data["booking_status"] != "RETURNED":
            raise BadRequestException("Booking must be in RETURNED status")

        if not booking_data["pickup_video_url"]:
            raise BadRequestException("Admin has not uploaded pickup video yet")

        payment_status = booking_data["payment_status"]

        if payment_status in ["REFUNDED", "REFUNDING", "SETTLED"]:
            if not booking_data["pickup_otp"]:
                raise BadRequestException("Pickup OTP not generated yet")

            return schemas.OTPResponse(
                otp=booking_data["pickup_otp"],
                generated_at=booking_data["pickup_otp_generated_at"],
                message="Share this OTP with admin for pickup verification",
            )

        elif payment_status == "INITIATED" or payment_status == "CHARGED":
            additional_payment = await booking_crud.get_additional_payment(
                db, booking_id
            )

            if not additional_payment or additional_payment.status.name != "CHARGED":
                raise BadRequestException(
                    "Additional payment not confirmed yet. You must confirm payment first."
                )

            if not booking_data["pickup_otp"]:
                raise BadRequestException("Pickup OTP not generated yet")

            return schemas.OTPResponse(
                otp=booking_data["pickup_otp"],
                generated_at=booking_data["pickup_otp_generated_at"],
                message="Share this OTP with admin for pickup verification",
            )

        else:
            raise BadRequestException(
                "Pickup OTP not available for current payment status"
            )


    async def verify_pickup_otp(
        self, db: AsyncSession, booking_id: int, otp_data: schemas.OTPVerify
    ) -> schemas.BookingAdminDetailed:
        """
        Admin verifies pickup OTP provided by customer.
        
        Args:
            db: Database session
            booking_id: Booking ID
            otp_data: OTP verification data
        
        Returns:
            BookingAdminDetailed with updated booking information
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booking_status"] != "RETURNED":
            raise BadRequestException("Booking must be in RETURNED status")

        if not booking_data["pickup_video_url"]:
            raise BadRequestException("Pickup video must be uploaded first")

        if not booking_data["pickup_otp"]:
            raise BadRequestException("Pickup OTP not generated yet")

        if booking_data["pickup_otp"] != otp_data.otp:
            raise BadRequestException("Invalid pickup OTP provided by customer")

        if booking_data["pickup_otp_verified"]:
            raise BadRequestException("Pickup OTP already verified")

        completed_status = await rbac_crud.get_status_by_name(db, "COMPLETED")
        if not completed_status:
            raise NotFoundException("Completed status not found")

        current_time = datetime.now(timezone.utc)
        await booking_crud.update_booking(
            db,
            booking_id,
            {"pickup_otp_verified": True, "pickup_otp_verified_at": current_time},
        )

        await booking_crud.update_booking_status(db, booking_id, completed_status.id)

        await booking_crud.update_payment_summary(
            db,
            booking_id,
            {
                "return_verification": {
                    "pickup_otp_verified": True,
                    "pickup_otp_verified_at": current_time.isoformat(),
                },
                "settlement": {"settled_at": current_time.isoformat()},
            },
        )

        await notification_utils.send_system_notification(
            db,
            receiver_id=booking_data["booked_by"],
            subject=f"Booking #{booking_id} Completed",
            body="Pickup verified successfully. Booking completed.",
            type=models.NotificationType.BOOKING,
        )

        updated_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        return schemas.BookingAdminDetailed(**updated_data)


    async def cancel_booking(
        self, db: AsyncSession, booking_id: int, user_id: str, reason: str
    ) -> schemas.Msg:
        """
        Customer cancels their own booking.
        
        Args:
            db: Database session
            booking_id: Booking ID
            user_id: User ID
            reason: Cancellation reason
        
        Returns:
            Msg with cancellation confirmation and refund details
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booked_by"] != user_id:
            raise ForbiddenException("Cannot cancel another user's booking")

        if booking_data["booking_status"] != "BOOKED":
            raise BadRequestException("Your are not allowed to cancel this booking")

        if booking_data["referral_benefit"]:
            await self._refund_referral_benefit(db, user_id)

        if booking_data["payment_summary"]["charges_breakdown"].get(
            "rookie_discount_applied"
        ):
            await self._refund_rookie_benefit(db, booking_data["booked_by"])

        current_time = datetime.now(timezone.utc)
        start_time = booking_data["start_date"]

        hours_to_start = (start_time - current_time).total_seconds() / 3600

        base_amount = Decimal(
            str(
                booking_data["payment_summary"]
                .get("charges_breakdown", {})
                .get("base_rental", 0)
            )
        )

        security_deposit = Decimal(
            str(
                booking_data["payment_summary"]
                .get("charges_breakdown", {})
                .get("security_deposit", 0)
            )
        )

        security_refund_amount = security_deposit
        payment_status_name = "REFUNDING"
        base_refund_amount = Decimal("0.0")
        total_refund_amount = security_deposit
        base_refund_percentage = 0
        payment_remarks = f"Customer cancellation: No base rental refund + full security deposit refund"

        if hours_to_start > 2:
            base_refund_amount = base_amount * Decimal("0.5")
            total_refund_amount += base_refund_amount
            base_refund_percentage = 50

            payment_remarks = f"Customer cancellation: 50% base rental refund + full security deposit refund"

        if total_refund_amount > Decimal("0.00"):
            from .payment_services import payment_service

            await payment_service.create_cancellation_refund(
                db=db,
                booking_id=booking_id,
                refund_amount=total_refund_amount,
                is_customer_cancellation=True,
                reason=reason,
            )

        cancelled_status = await rbac_crud.get_status_by_name(db, "CANCELLED")
        payment_status = await rbac_crud.get_status_by_name(db, payment_status_name)

        if not cancelled_status or not payment_status:
            raise NotFoundException("Required statuses not found")

        await booking_crud.update_payment_summary(
            db,
            booking_id,
            {
                "cancellation_details": {
                    "cancelled": True,
                    "cancelled_at": current_time.isoformat(),
                    "cancelled_by": user_id,
                    "cancellation_reason": reason,
                    "refund_eligible": hours_to_start > 2,
                    "base_rental_refund_percentage": base_refund_percentage,
                    "base_rental_refund_amount": float(base_refund_amount),
                    "security_deposit_refund_amount": float(security_deposit),
                    "total_refund_amount": float(total_refund_amount),
                    "cancellation_charges": float(base_amount - base_refund_amount),
                },
                "settlement": {
                    "refund_amount": float(total_refund_amount),
                    "settlement_status": "CANCELLATION_REFUND",
                },
            },
        )

        await booking_crud.update_booking_status(db, booking_id, cancelled_status.id)
        await booking_crud.update_booking_and_payment_status(
            db, booking_id, cancelled_status.id, payment_status.id
        )

        await booking_crud.update_booking(
            db,
            booking_id,
            {
                "cancelled_at": current_time,
                "cancelled_by": user_id,
                "cancellation_reason": reason,
            },
        )

        message = f"Booking cancelled. "
        if base_refund_amount > 0:
            message += f"Base rental eligible for {base_refund_percentage}% refund: ₹{base_refund_amount:.2f}. "
        message += f"Security deposit fully refundable: ₹{security_refund_amount:.2f}"

        await notification_utils.send_system_notification(
            db,
            receiver_id=user_id,
            subject=f"Booking #{booking_id} Cancelled",
            body=message,
            type=models.NotificationType.BOOKING,
        )

        return schemas.Msg(message=message)


    async def admin_cancel_booking(
        self,
        db: AsyncSession,
        booking_id: int,
        reason: str,
        admin_notes: str,
        user_id: str,
    ) -> schemas.Msg:
        """
        Admin cancels/rejects a booking.
        
        Args:
            db: Database session
            booking_id: Booking ID
            reason: Cancellation reason
            admin_notes: Additional admin notes
            user_id: Admin user ID
        
        Returns:
            Msg with cancellation confirmation and refund details
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booking_status"] != "BOOKED":
            raise BadRequestException("Booking is not eligible for rejection")

        if booking_data["referral_benefit"]:
            await self._refund_referral_benefit(db, booking_data["booked_by"])

        if booking_data["payment_summary"]["charges_breakdown"].get(
            "rookie_discount_applied"
        ):
            await self._refund_rookie_benefit(db, booking_data["booked_by"])

        current_time = datetime.now(timezone.utc)

        base_amount = Decimal(
            str(
                booking_data["payment_summary"]
                .get("charges_breakdown", {})
                .get("base_rental", 0)
            )
        )

        security_deposit = Decimal(
            str(
                booking_data["payment_summary"]
                .get("charges_breakdown", {})
                .get("security_deposit", 0)
            )
        )

        security_refund_amount = security_deposit
        total_refund_amount = security_refund_amount

        from .payment_services import payment_service

        if security_refund_amount > 0:
            await payment_service.create_cancellation_refund(
                db=db,
                booking_id=booking_id,
                refund_amount=security_refund_amount,
                is_customer_cancellation=False,
                reason=f"Admin rejection: Security deposit refund",
            )

        rejected_status = await rbac_crud.get_status_by_name(db, "REJECTED")
        refunding_status = await rbac_crud.get_status_by_name(db, "REFUNDING")

        if not rejected_status or not refunding_status:
            raise NotFoundException("Required statuses not found")

        await booking_crud.update_payment_summary(
            db,
            booking_id,
            {
                "cancellation_details": {
                    "cancelled": True,
                    "cancelled_at": current_time.isoformat(),
                    "cancelled_by": user_id,
                    "cancellation_reason": reason,
                    "admin_notes": admin_notes,
                    "refund_eligible": True,
                    "base_rental_refund_percentage": 0,
                    "base_rental_refund_amount": 0.00,
                    "security_deposit_refund_amount": float(security_refund_amount),
                    "total_refund_amount": float(total_refund_amount),
                    "cancellation_charges": float(base_amount),
                },
                "settlement": {
                    "refund_amount": float(total_refund_amount),
                    "settlement_status": "REJECTION_REFUND",
                },
            },
        )

        await booking_crud.update_booking_and_payment_status(
            db, booking_id, rejected_status.id, refunding_status.id
        )

        await booking_crud.update_booking(
            db,
            booking_id,
            {
                "cancelled_at": current_time,
                "cancelled_by": user_id,
                "cancellation_reason": reason,
            },
        )

        message = f"Booking rejected by admin. Security deposit fully refundable: ₹{security_refund_amount:.2f}. Base rental not refundable. Reason: {reason}"

        await notification_utils.send_system_notification(
            db,
            receiver_id=booking_data["booked_by"],
            subject=f"Booking #{booking_id} Rejected by Admin",
            body=message,
            type=models.NotificationType.BOOKING,
        )

        return schemas.Msg(message=message)


    async def complete_booking_with_review(
        self,
        db: AsyncSession,
        booking_id: int,
        review_in: schemas.ReviewCreate,
        user_id: str,
    ) -> schemas.BookingDetailed:
        """
        Customer completes booking by submitting a review.
        
        Args:
            db: Database session
            booking_id: Booking ID
            review_in: Review data
            user_id: User ID
        
        Returns:
            BookingDetailed with review included
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if booking_data["booked_by"] != user_id:
            raise ForbiddenException("Can only complete your own booking")

        if booking_data["booking_status"] != "COMPLETED":
            raise BadRequestException("Booking must be COMPLETED to submit review")

        existing_review = await booking_crud.get_review_by_booking_id(db, booking_id)
        if existing_review:
            raise BadRequestException("Review already submitted")

        review_data = {
            "booking_id": booking_id,
            "car_id": booking_data["car_id"],
            "rating": review_in.rating,
            "remarks": review_in.remarks,
            "created_by": user_id,
        }

        await booking_crud.create_review(db, review_data)

        user = await user_crud.get_user_with_details(db, user_id)
        if user and user.customer_details and user.customer_details.tag:
            is_rookie = user.customer_details.tag.name == models.Tags.ROOKIE

            if is_rookie:
                if user.referred_by:
                    await db.execute(
                        models.User.__table__.update()
                        .where(models.User.id == user.referred_by)
                        .values(referral_count=models.User.referral_count + 1)
                    )

                traveler_tag = await db.execute(
                    models.Tag.__table__.select().where(
                        models.Tag.name == models.Tags.TRAVELER
                    )
                )
                traveler_tag_obj = traveler_tag.scalar_one_or_none()

                if traveler_tag_obj:
                    await db.execute(
                        models.CustomerDetails.__table__.update()
                        .where(models.CustomerDetails.customer_id == user_id)
                        .values(tag_id=traveler_tag_obj)
                    )

                await db.commit()

        updated_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        return schemas.BookingDetailed(**updated_data)


    async def get_user_bookings(
        self,
        db: AsyncSession,
        user_id: str,
        skip: int,
        limit: int,
        filters: schemas.BookingFilterParams,
    ) -> schemas.PaginatedResponse:
        """
        Retrieve paginated list of bookings for a user.
        
        Args:
            db: Database session
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Filter parameters
        
        Returns:
            PaginatedResponse with booking list
        """
        items, total = await booking_crud.get_user_bookings_data(
            db, user_id, skip, limit, filters
        )
        return schemas.PaginatedResponse(
            total=total, items=items, skip=skip, limit=limit
        )


    async def get_all_bookings(
        self,
        db: AsyncSession,
        skip: int,
        limit: int,
        filters: schemas.BookingFilterParams,
    ) -> schemas.PaginatedResponse:
        """
        Retrieve paginated list of all bookings (admin).
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Filter parameters
        
        Returns:
            PaginatedResponse with booking list
        """
        items, total = await booking_crud.get_all_bookings_data(
            db, skip, limit, filters
        )
        return schemas.PaginatedResponse(
            total=total, items=items, skip=skip, limit=limit
        )


    async def get_booking_details(
        self, db: AsyncSession, booking_id: int, user_id_or_admin: str
    ) -> schemas.BookingDetailed | schemas.BookingAdminDetailed:
        """
        Retrieve detailed booking information.
        
        Args:
            db: Database session
            booking_id: Booking ID
            user_id_or_admin: User ID or "ADMIN" string
        
        Returns:
            BookingDetailed or BookingAdminDetailed based on user role
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if (
            user_id_or_admin != "ADMIN"
            and booking_data["booked_by"] != user_id_or_admin
        ):
            raise ForbiddenException("Access denied to this booking")

        if user_id_or_admin == "ADMIN":
            return schemas.BookingAdminDetailed(**booking_data)
        return schemas.BookingDetailed(**booking_data)


    async def get_booking_payment_summary(
        self, db: AsyncSession, booking_id: int, user_id_or_admin: str
    ) -> schemas.PaymentSummary:
        """
        Retrieve payment summary for a booking.
        
        Args:
            db: Database session
            booking_id: Booking ID
            user_id_or_admin: User ID or "ADMIN" string
        
        Returns:
            PaymentSummary with all payment details
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        if (
            user_id_or_admin != "ADMIN"
            and booking_data["booked_by"] != user_id_or_admin
        ):
            raise ForbiddenException("Access denied")

        return booking_data.get("payment_summary", {})


    async def get_pickup_location_address(
        self, db: AsyncSession, booking_id: int
    ) -> schemas.LocationGeocodeResponse:
        """
        Get reverse geocoded address for pickup location.
        
        Args:
            db: Database session
            booking_id: Booking ID
        
        Returns:
            LocationGeocodeResponse with address details
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        pickup_location = booking_data.get("pickup_location")
        if not pickup_location:
            raise NotFoundException("Pickup location not found")

        latitude = pickup_location.get("latitude")
        longitude = pickup_location.get("longitude")

        if latitude is None or longitude is None:
            raise BadRequestException("Invalid pickup location coordinates")

        address = await reverse_geocode(latitude, longitude)

        return schemas.LocationGeocodeResponse(
            booking_id=booking_id,
            latitude=latitude,
            longitude=longitude,
            address=address,
            location_type="pickup",
        )


    async def get_delivery_location_address(
        self, db: AsyncSession, booking_id: int
    ) -> schemas.LocationGeocodeResponse:
        """
        Get reverse geocoded address for delivery location.
        
        Args:
            db: Database session
            booking_id: Booking ID
        
        Returns:
            LocationGeocodeResponse with address details
        """
        booking_data = await booking_crud.get_booking_data_by_id(db, booking_id)
        if not booking_data:
            raise NotFoundException("Booking not found")

        delivery_location = booking_data.get("delivery_location")
        if not delivery_location:
            raise NotFoundException("Delivery location not found")

        latitude = delivery_location.get("latitude")
        longitude = delivery_location.get("longitude")

        if latitude is None or longitude is None:
            raise BadRequestException("Invalid delivery location coordinates")

        address = await reverse_geocode(latitude, longitude)

        return schemas.LocationGeocodeResponse(
            booking_id=booking_id,
            latitude=latitude,
            longitude=longitude,
            address=address,
            location_type="delivery",
        )


    async def export_user_bookings(
        self, db: AsyncSession, user_id: str, filters: schemas.BookingFilterParams
    ) -> StreamingResponse:
        """
        Export user bookings to CSV file.
        
        Args:
            db: Database session
            user_id: User ID
            filters: Filter parameters
        
        Returns:
            StreamingResponse with CSV file
        """
        items, _ = await booking_crud.get_user_bookings_data(
            db, user_id, 0, 10000, filters
        )

        csv_data = self._prepare_bookings_csv_data(items)

        csv_file = io.StringIO()
        writer = csv.DictWriter(
            csv_file, fieldnames=csv_data[0].keys() if csv_data else []
        )
        writer.writeheader()
        writer.writerows(csv_data)

        response = StreamingResponse(
            iter([csv_file.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=my_bookings_export.csv"
            },
        )

        return response


    async def export_all_bookings(
        self, db: AsyncSession, filters: schemas.BookingFilterParams
    ) -> StreamingResponse:
        """
        Export all bookings to CSV file (admin).
        
        Args:
            db: Database session
            filters: Filter parameters
        
        Returns:
            StreamingResponse with CSV file
        """
        items, _ = await booking_crud.get_all_bookings_data(db, 0, 10000, filters)

        csv_data = self._prepare_bookings_csv_data(items, include_customer_info=True)

        csv_file = io.StringIO()
        writer = csv.DictWriter(
            csv_file, fieldnames=csv_data[0].keys() if csv_data else []
        )
        writer.writeheader()
        writer.writerows(csv_data)

        response = StreamingResponse(
            iter([csv_file.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=all_bookings_export.csv"
            },
        )

        return response


    def _prepare_bookings_csv_data(
        self, bookings_data: List[dict], include_customer_info: bool = False
    ) -> List[dict]:
        """
        Prepare booking data for CSV export.
        
        Args:
            bookings_data: List of booking dictionaries
            include_customer_info: Whether to include customer information
        
        Returns:
            List of dictionaries formatted for CSV export
        """
        csv_rows = []

        for booking in bookings_data:
            row = {
                "Booking ID": booking["id"],
                "Car Number": booking["car"]["car_no"] if booking["car"] else "N/A",
                "Car Model": (
                    f"{booking['car']['car_model']['brand']} {booking['car']['car_model']['model']}"
                    if booking["car"] and booking["car"]["car_model"]
                    else "N/A"
                ),
                "Start Date": (
                    booking["start_date"].isoformat()
                    if booking["start_date"]
                    else "N/A"
                ),
                "End Date": (
                    booking["end_date"].isoformat() if booking["end_date"] else "N/A"
                ),
                "Booking Status": booking["booking_status"],
                "Payment Status": booking["payment_status"] or "N/A",
                "Created At": (
                    booking["created_at"].isoformat()
                    if booking["created_at"]
                    else "N/A"
                ),
                "Total Amount": (
                    booking["payment_summary"]["charges_breakdown"]["total_payable"]
                    if booking["payment_summary"]
                    and booking["payment_summary"]["charges_breakdown"]
                    else "N/A"
                ),
            }

            if include_customer_info and booking.get("booker"):
                row.update(
                    {
                        "Customer ID": booking["booker"]["id"],
                        "Customer Email": booking["booker"]["email"],
                        "Customer Username": booking["booker"]["username"],
                    }
                )

            csv_rows.append(row)

        return csv_rows


booking_service = BookingService()
