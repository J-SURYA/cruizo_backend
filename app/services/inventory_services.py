from fastapi import UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, or_
from sqlalchemy.orm import selectinload
from azure.storage.blob import ContentSettings
from typing import List, Dict, Optional, Tuple
from pydantic import ValidationError
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import logging
import re


from app import models, schemas
from app.crud import inventory_crud, rbac_crud, booking_crud
from app.schemas import CarUpdate
from app.models.enums import StatusEnum
from app.utils.exception_utils import (
    NotFoundException,
    DuplicateEntryException,
    BadRequestException,
)
from app.core.config import settings
from app.core.dependencies import get_container_client


logger = logging.getLogger(__name__)


IMPORT_EXPORT_COLUMNS = [
    "Car Number",
    "Brand",
    "Model",
    "Color",
    "Mileage",
    "Rental Per Hour",
    "Manufacture Year",
    "Transmission Type",
    "Category",
    "Fuel Type",
    "Capacity",
    "Status",
    "Features (comma-separated)",
    "Last Serviced Date",
    "Service Frequency Months",
    "Insured Till",
    "Pollution Expiry",
]
MAX_FILE_SIZE_MB = 5
ALLOWED_MIMETYPES = [
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]


class InventoryService:
    """
    Service class for managing inventory operations including cars, models, and related resources.
    """
    async def _validate_trip_details(
        self, trip_details: Optional[schemas.TripDetailsInput]
    ) -> bool:
        """
        Validate trip details for availability checks.
        
        Args:
            trip_details: Trip details input with start and end dates
        
        Returns:
            Boolean indicating validation success
        """
        if not trip_details:
            return True

        current_time = datetime.now(timezone.utc)

        if trip_details.start_date.tzinfo is None:
            trip_details.start_date = trip_details.start_date.replace(
                tzinfo=timezone.utc
            )
        if trip_details.end_date.tzinfo is None:
            trip_details.end_date = trip_details.end_date.replace(tzinfo=timezone.utc)

        if trip_details.start_date <= current_time:
            raise BadRequestException("Start time must be in the future")

        min_advance_time = current_time + timedelta(hours=2) - timedelta(minutes=5)
        if trip_details.start_date < min_advance_time:
            raise BadRequestException("Start time must be at least 2 hours from now")

        if (trip_details.end_date - trip_details.start_date) < timedelta(hours=8):
            raise BadRequestException("Booking duration must be at least 8 hours")

        max_advance_time = current_time + timedelta(days=15)
        if trip_details.start_date > max_advance_time:
            raise BadRequestException("Start date cannot be more than 15 days from now")

        if trip_details.end_date <= trip_details.start_date:
            raise BadRequestException("End date must be after start date")

        if trip_details.start_date.minute not in [
            0,
            30,
        ] or trip_details.end_date.minute not in [0, 30]:
            raise BadRequestException(
                "Booking times must be in :00 or :30 minute intervals"
            )

        return True


    async def _validate_delivery_pickup_locations(
        self,
        delivery_lat: float,
        delivery_lon: float,
        pickup_lat: float,
        pickup_lon: float,
    ) -> Tuple[float, float, float]:
        """
        Validate delivery and pickup locations and calculate distances.
        
        Args:
            delivery_lat: Delivery location latitude
            delivery_lon: Delivery location longitude
            pickup_lat: Pickup location latitude
            pickup_lon: Pickup location longitude
        
        Returns:
            Tuple of hub to delivery, hub to pickup, and total distances in kilometers
        """
        if not (-90 <= delivery_lat <= 90) or not (-180 <= delivery_lon <= 180):
            raise BadRequestException("Invalid delivery location coordinates")
        if not (-90 <= pickup_lat <= 90) or not (-180 <= pickup_lon <= 180):
            raise BadRequestException("Invalid pickup location coordinates")

        def calculate_distance(
            lat1: float, lon1: float, lat2: float, lon2: float
        ) -> float:
            R = 6371

            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)

            a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
                math.radians(lat1)
            ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)

            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        hub_to_delivery = calculate_distance(
            settings.HUB_LATITUDE, settings.HUB_LONGITUDE, delivery_lat, delivery_lon
        )
        hub_to_pickup = calculate_distance(
            settings.HUB_LATITUDE, settings.HUB_LONGITUDE, pickup_lat, pickup_lon
        )
        total_distance = hub_to_delivery + hub_to_pickup

        if total_distance > 60:
            raise BadRequestException(
                f"Total distance ({total_distance:.1f}km) exceeds 60km limit"
            )

        return hub_to_delivery, hub_to_pickup, total_distance


    async def _get_available_slots_for_car(
        self, db: AsyncSession, car_id: int
    ) -> List[Dict[str, datetime]]:
        """
        Get available time slots for a car in next 15 days.
        
        Args:
            db: Database session
            car_id: Car ID to check availability for
        
        Returns:
            List of dictionaries containing start and end datetime for each available slot
        """
        current_time = datetime.now(timezone.utc)
        max_date = current_time + timedelta(days=15)

        bookings_query = await db.execute(
            select(models.Booking)
            .join(models.Status, models.Booking.booking_status_id == models.Status.id)
            .where(
                models.Booking.car_id == car_id,
                models.Booking.start_date < max_date,
                models.Booking.end_date > current_time,
                models.Status.name.in_(["BOOKED", "DELIVERED", "RETURNED"]),
            )
            .order_by(models.Booking.start_date.asc())
        )
        bookings = bookings_query.scalars().all()

        freezes_query = await db.execute(
            select(models.BookingFreeze)
            .where(
                models.BookingFreeze.car_id == car_id,
                models.BookingFreeze.is_active.is_(True),
                models.BookingFreeze.freeze_expires_at > current_time,
                models.BookingFreeze.start_date < max_date,
                models.BookingFreeze.end_date > current_time,
            )
            .order_by(models.BookingFreeze.start_date.asc())
        )
        freezes = freezes_query.scalars().all()

        occupied_periods = []

        for booking in bookings:
            occupied_periods.append(
                {
                    "start": booking.start_date,
                    "end": booking.end_date + timedelta(hours=4),
                }
            )

        for freeze in freezes:
            occupied_periods.append(
                {
                    "start": freeze.start_date,
                    "end": freeze.end_date + timedelta(hours=4),
                }
            )

        occupied_periods.sort(key=lambda x: x["start"])

        available_slots = []

        current_slot_start = current_time

        for period in occupied_periods:
            if period["end"] <= current_slot_start:
                continue

            if current_slot_start < period["start"]:
                slot_end = min(period["start"], max_date)

                if (slot_end - current_slot_start) >= timedelta(hours=8):
                    effective_end = min(slot_end, max_date)
                    if (effective_end - current_slot_start) >= timedelta(hours=8):
                        available_slots.append(
                            {"start": current_slot_start, "end": effective_end}
                        )

            current_slot_start = max(current_slot_start, period["end"])

            if current_slot_start >= max_date:
                break

        if current_slot_start < max_date:
            if (max_date - current_slot_start) >= timedelta(hours=8):
                available_slots.append({"start": current_slot_start, "end": max_date})

        return available_slots


    async def _validate_color(self, db: AsyncSession, color_id: int):
        """
        Validate color exists.
        
        Args:
            db: Database session
            color_id: Color ID to validate
        
        Returns:
            None
        """
        if not await inventory_crud.get_by_id(db, models.Color, color_id):
            raise BadRequestException(f"Color with id {color_id} not found")


    async def _validate_category(self, db: AsyncSession, category_id: int):
        """
        Validate category exists.
        
        Args:
            db: Database session
            category_id: Category ID to validate
        
        Returns:
            None
        """
        if not await inventory_crud.get_by_id(db, models.Category, category_id):
            raise BadRequestException(f"Category with id {category_id} not found")


    async def _validate_fuel(self, db: AsyncSession, fuel_id: int):
        """
        Validate fuel exists.
        
        Args:
            db: Database session
            fuel_id: Fuel ID to validate
        
        Returns:
            None
        """
        if not await inventory_crud.get_by_id(db, models.Fuel, fuel_id):
            raise BadRequestException(f"Fuel with id {fuel_id} not found")


    async def _validate_capacity(self, db: AsyncSession, capacity_id: int):
        """
        Validate capacity exists.
        
        Args:
            db: Database session
            capacity_id: Capacity ID to validate
        
        Returns:
            None
        """
        if not await inventory_crud.get_by_id(db, models.Capacity, capacity_id):
            raise BadRequestException(f"Capacity with id {capacity_id} not found")


    async def _validate_car_model_fks(
        self, db: AsyncSession, category_id: int, fuel_id: int, capacity_id: int
    ):
        """
        Validate all foreign keys for car model.
        
        Args:
            db: Database session
            category_id: Category ID to validate
            fuel_id: Fuel ID to validate
            capacity_id: Capacity ID to validate
        
        Returns:
            None
        """
        await self._validate_category(db, category_id)
        await self._validate_fuel(db, fuel_id)
        await self._validate_capacity(db, capacity_id)


    def _sanitize_car_identifier(self, car_no: str) -> str:
        """
        Sanitizes car number for safe use in blob names.
        
        Args:
            car_no: Car number string to sanitize
        
        Returns:
            Sanitized car number string
        """
        sanitized = re.sub(r"[^a-zA-Z0-9-_]", "-", car_no.strip())
        return sanitized.lower()


    async def _validate_image_format_and_size(self, file: UploadFile) -> None:
        """
        Validates image file format (JPG or PNG only) and size (max 2MB).
        
        Args:
            file: Upload file to validate
        
        Returns:
            None
        """
        content_type = (file.content_type or "").lower()
        filename = (file.filename or "").lower()
        valid_content_types = ["image/jpeg", "image/jpg", "image/png"]
        valid_extensions = [".jpg", ".jpeg", ".png"]
        is_valid_type = content_type in valid_content_types
        is_valid_extension = any(filename.endswith(ext) for ext in valid_extensions)
        if not (is_valid_type or is_valid_extension):
            raise BadRequestException("Only JPG and PNG images are accepted")

        file_bytes = await file.read()
        file_size = len(file_bytes)
        MAX_FILE_SIZE = 2 * 1024 * 1024
        if file_size > MAX_FILE_SIZE:
            raise BadRequestException("Image file size must be less than 2 MB")

        await file.seek(0)


    async def _upload_car_image(
        self, car_id: int, file: UploadFile, image_index: int
    ) -> str:
        """
        Uploads a car image to Azure Blob Storage and returns the URL.
        
        Args:
            car_id: Car ID for blob naming
            file: Upload file to store
            image_index: Index for the image (1-5)
        
        Returns:
            URL of the uploaded blob
        """
        try:
            container_client = await get_container_client(settings.INVENTORY_CONTAINER_NAME)
            file_bytes = await file.read()
            content_type = (file.content_type or "").lower()
            filename = (file.filename or "").lower()
            is_png = content_type == "image/png" or filename.endswith(".png")
            is_jpg = content_type in ["image/jpeg", "image/jpg"] or filename.endswith(
                (".jpg", ".jpeg")
            )
            sanitized_car_id = str(car_id)
            if is_png:
                blob_name = f"car_{sanitized_car_id}_image_{image_index}.png"
                content_settings = ContentSettings(content_type="image/png")
            elif is_jpg:
                blob_name = f"car_{sanitized_car_id}_image_{image_index}.jpg"
                content_settings = ContentSettings(content_type="image/jpeg")
            else:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Only JPG and PNG images are accepted",
                )
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.upload_blob(
                file_bytes, overwrite=True, content_settings=content_settings
            )
            return blob_client.url

        except Exception as e:
            logger.error(f"Error uploading car image: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload car image",
            )


    async def _delete_car_images(self, image_urls: List[str]) -> None:
        """
        Deletes car images from Azure Blob Storage.
        
        Args:
            image_urls: List of image URLs to delete
        
        Returns:
            None
        """
        if not image_urls:
            return
        
        try:
            container_client = await get_container_client(settings.INVENTORY_CONTAINER_NAME)
            for url in image_urls:
                try:
                    blob_name = url.split("/inventory/")[-1]
                    blob_client = container_client.get_blob_client(blob_name)
                    await blob_client.delete_blob()
                except Exception as e:
                    logger.warning(f"Failed to delete blob {url}: {e}")
        
        except Exception as e:
            logger.error(f"Error deleting car images: {e}")
            raise


    async def get_color(self, db: AsyncSession, color_id: int) -> models.Color:
        """
        Get color by ID.
        
        Args:
            db: Database session
            color_id: Color ID to retrieve
        
        Returns:
            Color model instance
        """
        db_obj = await inventory_crud.get_by_id(db, models.Color, color_id)
        if not db_obj:
            raise NotFoundException("Color not found")
        return db_obj


    async def create_color(
        self, db: AsyncSession, color_in: schemas.ColorCreate
    ) -> models.Color:
        """
        Create new color.
        
        Args:
            db: Database session
            color_in: Color creation data
        
        Returns:
            Created color model instance
        """
        if await inventory_crud.get_color_by_name(db, color_in.color_name):
            raise DuplicateEntryException("Color with this name already exists")
        return await inventory_crud.create_color(db, color_in)


    async def get_all_colors(self, db: AsyncSession) -> List[models.Color]:
        """
        Get all colors.
        
        Args:
            db: Database session
        
        Returns:
            List of all color model instances
        """
        return await inventory_crud.get_all(db, models.Color)


    async def update_color(
        self, db: AsyncSession, color_id: int, color_in: schemas.ColorUpdate
    ) -> models.Color:
        """
        Update existing color.
        
        Args:
            db: Database session
            color_id: Color ID to update
            color_in: Color update data
        
        Returns:
            Updated color model instance
        """
        db_color = await inventory_crud.get_by_id(db, models.Color, color_id)
        if not db_color:
            raise NotFoundException("Color not found")

        existing = await inventory_crud.get_color_by_name(db, color_in.color_name)
        if existing and existing.id != color_id:
            raise DuplicateEntryException("Another color with this name exists")

        return await inventory_crud.update_color(db, db_color, color_in)


    async def delete_color(self, db: AsyncSession, color_id: int) -> None:
        """
        Delete color.
        
        Args:
            db: Database session
            color_id: Color ID to delete
        
        Returns:
            None
        """
        db_color = await inventory_crud.get_by_id(db, models.Color, color_id)
        if not db_color:
            raise NotFoundException("Color not found")

        result = await db.execute(
            select(models.Car).where(models.Car.color_id == color_id).limit(1)
        )
        if result.scalar_one_or_none():
            raise BadRequestException("Cannot delete color that is assigned to cars")

        await inventory_crud.delete(db, db_color)


    async def get_car_model(
        self, db: AsyncSession, car_model_id: int
    ) -> schemas.CarModelWithCars:
        """
        Get car model by ID with all cars and their reviews.
        
        Args:
            db: Database session
            car_model_id: Car model ID to retrieve
        
        Returns:
            Car model with cars schema
        """
        db_obj = await inventory_crud.get_car_model_by_id(db, car_model_id)
        if not db_obj:
            raise NotFoundException("Car model not found")

        cars_with_reviews = []
        for car in db_obj.cars:
            car_complete = schemas.CarComplete(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                last_serviced_date=car.last_serviced_date,
                service_frequency_months=car.service_frequency_months,
                insured_till=car.insured_till,
                pollution_expiry=car.pollution_expiry,
                created_at=car.created_at,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                brand=db_obj.brand,
                model=db_obj.model,
                category=schemas.CategoryPublic(
                    id=db_obj.category.id, category_name=db_obj.category.category_name
                ),
                fuel=schemas.FuelPublic(
                    id=db_obj.fuel.id, fuel_name=db_obj.fuel.fuel_name
                ),
                capacity=schemas.CapacityPublic(
                    id=db_obj.capacity.id, capacity_value=db_obj.capacity.capacity_value
                ),
                transmission_type=db_obj.transmission_type,
                mileage=db_obj.mileage,
                rental_per_hr=db_obj.rental_per_hr,
                dynamic_rental_price=db_obj.dynamic_rental_price,
                kilometer_limit_per_hr=db_obj.kilometer_limit_per_hr,
                features=[
                    schemas.FeaturePublic(
                        id=feature.id, feature_name=feature.feature_name
                    )
                    for feature in db_obj.features
                ],
                reviews=[
                    schemas.ReviewPublic(
                        id=review.id,
                        rating=review.rating,
                        remarks=review.remarks,
                        created_by=review.creator.id if review.creator else "Unknown",
                        created_at=review.created_at,
                    )
                    for review in car.reviews
                ],
            )
            cars_with_reviews.append(car_complete)

        return schemas.CarModelWithCars(
            id=db_obj.id,
            brand=db_obj.brand,
            model=db_obj.model,
            transmission_type=db_obj.transmission_type,
            mileage=db_obj.mileage,
            rental_per_hr=db_obj.rental_per_hr,
            dynamic_rental_price=db_obj.dynamic_rental_price,
            kilometer_limit_per_hr=db_obj.kilometer_limit_per_hr,
            created_at=db_obj.created_at,
            category=schemas.CategoryPublic(
                id=db_obj.category.id, category_name=db_obj.category.category_name
            ),
            fuel=schemas.FuelPublic(id=db_obj.fuel.id, fuel_name=db_obj.fuel.fuel_name),
            capacity=schemas.CapacityPublic(
                id=db_obj.capacity.id, capacity_value=db_obj.capacity.capacity_value
            ),
            features=[
                schemas.FeaturePublic(id=feature.id, feature_name=feature.feature_name)
                for feature in db_obj.features
            ],
            cars=cars_with_reviews,
        )


    async def create_car_model(
        self,
        db: AsyncSession,
        car_model_in: schemas.CarModelCreate,
        creator: models.User,
    ) -> models.CarModel:
        """
        Create new car model.
        
        Args:
            db: Database session
            car_model_in: Car model creation data
            creator: User creating the car model
        
        Returns:
            Created car model instance
        """
        if await inventory_crud.get_car_model_by_brand_model(
            db, car_model_in.brand, car_model_in.model
        ):
            raise DuplicateEntryException(
                "Car model with this brand and model already exists"
            )

        await self._validate_car_model_fks(
            db, car_model_in.category_id, car_model_in.fuel_id, car_model_in.capacity_id
        )

        return await inventory_crud.create_car_model(db, car_model_in)


    async def get_all_car_models(
        self, db: AsyncSession
    ) -> List[schemas.CarModelWithCars]:
        """
        Get all car models with their cars and reviews.
        
        Args:
            db: Database session
        
        Returns:
            List of car models with cars schema
        """
        car_models = await inventory_crud.get_all_car_models(db)

        result = []
        for car_model in car_models:
            # Format each car model with its cars
            cars_with_reviews = []
            for car in car_model.cars:
                car_complete = schemas.CarComplete(
                    id=car.id,
                    car_no=car.car_no,
                    manufacture_year=car.manufacture_year,
                    image_urls=car.image_urls,
                    last_serviced_date=car.last_serviced_date,
                    service_frequency_months=car.service_frequency_months,
                    insured_till=car.insured_till,
                    pollution_expiry=car.pollution_expiry,
                    created_at=car.created_at,
                    color=schemas.ColorPublic(
                        id=car.color.id, color_name=car.color.color_name
                    ),
                    status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                    brand=car_model.brand,
                    model=car_model.model,
                    category=schemas.CategoryPublic(
                        id=car_model.category.id,
                        category_name=car_model.category.category_name,
                    ),
                    fuel=schemas.FuelPublic(
                        id=car_model.fuel.id, fuel_name=car_model.fuel.fuel_name
                    ),
                    capacity=schemas.CapacityPublic(
                        id=car_model.capacity.id,
                        capacity_value=car_model.capacity.capacity_value,
                    ),
                    transmission_type=car_model.transmission_type,
                    mileage=car_model.mileage,
                    rental_per_hr=car_model.rental_per_hr,
                    dynamic_rental_price=car_model.dynamic_rental_price,
                    kilometer_limit_per_hr=car_model.kilometer_limit_per_hr,
                    features=[
                        schemas.FeaturePublic(
                            id=feature.id, feature_name=feature.feature_name
                        )
                        for feature in car_model.features
                    ],
                    reviews=[
                        schemas.ReviewPublic(
                            id=review.id,
                            rating=review.rating,
                            remarks=review.remarks,
                            created_by=(
                                review.creator.id if review.creator else "Unknown"
                            ),
                            created_at=review.created_at,
                        )
                        for review in car.reviews
                    ],
                )
                cars_with_reviews.append(car_complete)

            car_model_with_cars = schemas.CarModelWithCars(
                id=car_model.id,
                brand=car_model.brand,
                model=car_model.model,
                transmission_type=car_model.transmission_type,
                mileage=car_model.mileage,
                rental_per_hr=car_model.rental_per_hr,
                dynamic_rental_price=car_model.dynamic_rental_price,
                kilometer_limit_per_hr=car_model.kilometer_limit_per_hr,
                created_at=car_model.created_at,
                category=schemas.CategoryPublic(
                    id=car_model.category.id,
                    category_name=car_model.category.category_name,
                ),
                fuel=schemas.FuelPublic(
                    id=car_model.fuel.id, fuel_name=car_model.fuel.fuel_name
                ),
                capacity=schemas.CapacityPublic(
                    id=car_model.capacity.id,
                    capacity_value=car_model.capacity.capacity_value,
                ),
                features=[
                    schemas.FeaturePublic(
                        id=feature.id, feature_name=feature.feature_name
                    )
                    for feature in car_model.features
                ],
                cars=cars_with_reviews,
            )
            result.append(car_model_with_cars)

        return result


    async def update_car_model(
        self, db: AsyncSession, car_model_id: int, car_model_in: schemas.CarModelUpdate
    ) -> models.CarModel:
        """
        Update existing car model.
        
        Args:
            db: Database session
            car_model_id: Car model ID to update
            car_model_in: Car model update data
        
        Returns:
            Updated car model instance
        """
        db_car_model = await inventory_crud.get_car_model_by_id(db, car_model_id)
        if not db_car_model:
            raise NotFoundException("Car model not found")

        if car_model_in.category_id:
            await self._validate_category(db, car_model_in.category_id)
        if car_model_in.fuel_id:
            await self._validate_fuel(db, car_model_in.fuel_id)
        if car_model_in.capacity_id:
            await self._validate_capacity(db, car_model_in.capacity_id)

        return await inventory_crud.update_car_model(db, db_car_model, car_model_in)


    async def delete_car_model(self, db: AsyncSession, car_model_id: int) -> None:
        """
        Delete car model.
        
        Args:
            db: Database session
            car_model_id: Car model ID to delete
        
        Returns:
            None
        """
        db_car_model = await inventory_crud.get_car_model_by_id(db, car_model_id)
        if not db_car_model:
            raise NotFoundException("Car model not found")

        result = await db.execute(
            select(models.Car).where(models.Car.car_model_id == car_model_id).limit(1)
        )
        if result.scalar_one_or_none():
            raise BadRequestException("Cannot delete car model that has cars assigned")

        await inventory_crud.delete(db, db_car_model)


    async def get_category(self, db: AsyncSession, category_id: int) -> models.Category:
        """
        Get category by ID.
        
        Args:
            db: Database session
            category_id: Category ID to retrieve
        
        Returns:
            Category model instance
        """
        db_obj = await inventory_crud.get_by_id(db, models.Category, category_id)
        if not db_obj:
            raise NotFoundException("Category not found")
        return db_obj


    async def create_category(
        self, db: AsyncSession, category_in: schemas.CategoryCreate
    ) -> models.Category:
        """
        Create new category.
        
        Args:
            db: Database session
            category_in: Category creation data
        
        Returns:
            Created category model instance
        """
        if await inventory_crud.get_category_by_name(db, category_in.category_name):
            raise DuplicateEntryException("Category with this name already exists")
        return await inventory_crud.create_category(db, category_in)


    async def get_all_categories(self, db: AsyncSession) -> List[models.Category]:
        """
        Get all categories.
        
        Args:
            db: Database session
        
        Returns:
            List of all category model instances
        """
        return await inventory_crud.get_all(db, models.Category)


    async def update_category(
        self, db: AsyncSession, category_id: int, category_in: schemas.CategoryUpdate
    ) -> models.Category:
        """
        Update existing category.
        
        Args:
            db: Database session
            category_id: Category ID to update
            category_in: Category update data
        
        Returns:
            Updated category model instance
        """
        db_category = await inventory_crud.get_by_id(db, models.Category, category_id)
        if not db_category:
            raise NotFoundException("Category not found")

        existing = await inventory_crud.get_category_by_name(
            db, category_in.category_name
        )
        if existing and existing.id != category_id:
            raise DuplicateEntryException("Another category with this name exists")

        return await inventory_crud.update_category(db, db_category, category_in)


    async def delete_category(self, db: AsyncSession, category_id: int) -> None:
        """
        Delete category.
        
        Args:
            db: Database session
            category_id: Category ID to delete
        
        Returns:
            None
        """
        db_category = await inventory_crud.get_by_id(db, models.Category, category_id)
        if not db_category:
            raise NotFoundException("Category not found")

        result = await db.execute(
            select(models.CarModel)
            .where(models.CarModel.category_id == category_id)
            .limit(1)
        )
        if result.scalar_one_or_none():
            raise BadRequestException(
                "Cannot delete category that is assigned to car models"
            )

        await inventory_crud.delete(db, db_category)


    async def get_fuel(self, db: AsyncSession, fuel_id: int) -> models.Fuel:
        """
        Get fuel by ID.
        
        Args:
            db: Database session
            fuel_id: Fuel ID to retrieve
        
        Returns:
            Fuel model instance
        """
        db_obj = await inventory_crud.get_by_id(db, models.Fuel, fuel_id)
        if not db_obj:
            raise NotFoundException("Fuel type not found")
        return db_obj


    async def create_fuel(
        self, db: AsyncSession, fuel_in: schemas.FuelCreate
    ) -> models.Fuel:
        """
        Create new fuel type.
        
        Args:
            db: Database session
            fuel_in: Fuel creation data
        
        Returns:
            Created fuel model instance
        """
        if await inventory_crud.get_fuel_by_name(db, fuel_in.fuel_name):
            raise DuplicateEntryException("Fuel type with this name already exists")
        return await inventory_crud.create_fuel(db, fuel_in)


    async def get_all_fuels(self, db: AsyncSession) -> List[models.Fuel]:
        """
        Get all fuel types.
        
        Args:
            db: Database session
        
        Returns:
            List of all fuel model instances
        """
        return await inventory_crud.get_all(db, models.Fuel)


    async def update_fuel(
        self, db: AsyncSession, fuel_id: int, fuel_in: schemas.FuelUpdate
    ) -> models.Fuel:
        """
        Update existing fuel type.
        
        Args:
            db: Database session
            fuel_id: Fuel ID to update
            fuel_in: Fuel update data
        
        Returns:
            Updated fuel model instance
        """
        db_fuel = await inventory_crud.get_by_id(db, models.Fuel, fuel_id)
        if not db_fuel:
            raise NotFoundException("Fuel type not found")

        existing = await inventory_crud.get_fuel_by_name(db, fuel_in.fuel_name)
        if existing and existing.id != fuel_id:
            raise DuplicateEntryException("Another fuel type with this name exists")

        return await inventory_crud.update_fuel(db, db_fuel, fuel_in)


    async def delete_fuel(self, db: AsyncSession, fuel_id: int) -> None:
        """
        Delete fuel type.
        
        Args:
            db: Database session
            fuel_id: Fuel ID to delete
        
        Returns:
            None
        """
        db_fuel = await inventory_crud.get_by_id(db, models.Fuel, fuel_id)
        if not db_fuel:
            raise NotFoundException("Fuel type not found")

        result = await db.execute(
            select(models.CarModel).where(models.CarModel.fuel_id == fuel_id).limit(1)
        )
        if result.scalar_one_or_none():
            raise BadRequestException(
                "Cannot delete fuel type that is assigned to car models"
            )

        await inventory_crud.delete(db, db_fuel)


    async def get_capacity(self, db: AsyncSession, capacity_id: int) -> models.Capacity:
        """
        Get capacity by ID.
        
        Args:
            db: Database session
            capacity_id: Capacity ID to retrieve
        
        Returns:
            Capacity model instance
        """
        db_obj = await inventory_crud.get_by_id(db, models.Capacity, capacity_id)
        if not db_obj:
            raise NotFoundException("Capacity not found")
        return db_obj


    async def create_capacity(
        self, db: AsyncSession, capacity_in: schemas.CapacityCreate
    ) -> models.Capacity:
        """
        Create new capacity.
        
        Args:
            db: Database session
            capacity_in: Capacity creation data
        
        Returns:
            Created capacity model instance
        """
        if await inventory_crud.get_capacity_by_value(db, capacity_in.capacity_value):
            raise DuplicateEntryException("Capacity with this value already exists")
        return await inventory_crud.create_capacity(db, capacity_in)


    async def get_all_capacities(self, db: AsyncSession) -> List[models.Capacity]:
        """
        Get all capacities.
        
        Args:
            db: Database session
        
        Returns:
            List of all capacity model instances
        """
        return await inventory_crud.get_all(db, models.Capacity)


    async def update_capacity(
        self, db: AsyncSession, capacity_id: int, capacity_in: schemas.CapacityUpdate
    ) -> models.Capacity:
        """
        Update existing capacity.
        
        Args:
            db: Database session
            capacity_id: Capacity ID to update
            capacity_in: Capacity update data
        
        Returns:
            Updated capacity model instance
        """
        db_capacity = await inventory_crud.get_by_id(db, models.Capacity, capacity_id)
        if not db_capacity:
            raise NotFoundException("Capacity not found")

        existing = await inventory_crud.get_capacity_by_value(
            db, capacity_in.capacity_value
        )
        if existing and existing.id != capacity_id:
            raise DuplicateEntryException("Another capacity with this value exists")

        return await inventory_crud.update_capacity(db, db_capacity, capacity_in)


    async def delete_capacity(self, db: AsyncSession, capacity_id: int) -> None:
        """
        Delete capacity.
        
        Args:
            db: Database session
            capacity_id: Capacity ID to delete
        
        Returns:
            None
        """
        db_capacity = await inventory_crud.get_by_id(db, models.Capacity, capacity_id)
        if not db_capacity:
            raise NotFoundException("Capacity not found")

        result = await db.execute(
            select(models.CarModel)
            .where(models.CarModel.capacity_id == capacity_id)
            .limit(1)
        )
        if result.scalar_one_or_none():
            raise BadRequestException(
                "Cannot delete capacity that is assigned to car models"
            )

        await inventory_crud.delete(db, db_capacity)


    async def get_feature(self, db: AsyncSession, feature_id: int) -> models.Feature:
        """
        Get feature by ID.
        
        Args:
            db: Database session
            feature_id: Feature ID to retrieve
        
        Returns:
            Feature model instance
        """
        db_obj = await inventory_crud.get_by_id(db, models.Feature, feature_id)
        if not db_obj:
            raise NotFoundException("Feature not found")
        return db_obj


    async def create_feature(
        self, db: AsyncSession, feature_in: schemas.FeatureCreate
    ) -> models.Feature:
        """
        Create new feature.
        
        Args:
            db: Database session
            feature_in: Feature creation data
        
        Returns:
            Created feature model instance
        """
        if await inventory_crud.get_feature_by_name(db, feature_in.feature_name):
            raise DuplicateEntryException("Feature with this name already exists")
        return await inventory_crud.create_feature(db, feature_in)


    async def get_all_features(self, db: AsyncSession) -> List[models.Feature]:
        """
        Get all features.
        
        Args:
            db: Database session
        
        Returns:
            List of all feature model instances
        """
        return await inventory_crud.get_all(db, models.Feature)


    async def update_feature(
        self, db: AsyncSession, feature_id: int, feature_in: schemas.FeatureUpdate
    ) -> models.Feature:
        """
        Update existing feature.
        
        Args:
            db: Database session
            feature_id: Feature ID to update
            feature_in: Feature update data
        
        Returns:
            Updated feature model instance
        """
        db_feature = await inventory_crud.get_by_id(db, models.Feature, feature_id)
        if not db_feature:
            raise NotFoundException("Feature not found")

        existing = await inventory_crud.get_feature_by_name(db, feature_in.feature_name)
        if existing and existing.id != feature_id:
            raise DuplicateEntryException("Another feature with this name exists")

        return await inventory_crud.update_feature(db, db_feature, feature_in)


    async def delete_feature(self, db: AsyncSession, feature_id: int) -> None:
        """
        Delete feature.
        
        Args:
            db: Database session
            feature_id: Feature ID to delete
        
        Returns:
            None
        """
        db_feature = await inventory_crud.get_by_id(db, models.Feature, feature_id)
        if not db_feature:
            raise NotFoundException("Feature not found")
        await inventory_crud.delete(db, db_feature)


    def _find_available_image_slots(
        self, current_image_urls: List[str], car_id: int, count: int
    ) -> List[int]:
        """
        Find available image slot indices (1-5) for a car.
        
        Args:
            current_image_urls: List of current image URLs
            car_id: Car ID used in blob naming pattern
            count: Number of slots needed
        
        Returns:
            List of available indices (e.g. [1, 3, 5] if 2 and 4 are used)
        """
        sanitized_car_id = str(car_id)
        used_indices = set()

        for url in current_image_urls:
            try:
                blob_name = url.split("/")[-1]
                if f"car_{sanitized_car_id}_image_" in blob_name:
                    parts = blob_name.split("_image_")
                    if len(parts) == 2:
                        index_str = parts[1].split(".")[0]
                        used_indices.add(int(index_str))
            except (ValueError, IndexError):
                continue

        available_slots = []
        for i in range(1, 6):
            if i not in used_indices:
                available_slots.append(i)
                if len(available_slots) == count:
                    break

        return available_slots


    async def create_car(
        self,
        db: AsyncSession,
        car_in: schemas.CarCreate,
        creator: models.User,
        images: Optional[List[UploadFile]] = None,
    ) -> models.Car:
        """
        Create individual car with optional image uploads.
        
        Args:
            db: Database session
            car_in: Car creation data
            creator: User creating the car
            images: Optional list of image files to upload
        
        Returns:
            Created car model instance
        """
        valid_images = None
        if images:
            filtered = [
                img
                for img in images
                if img and hasattr(img, "filename") and img.filename
            ]
            valid_images = filtered if filtered else None

        if await inventory_crud.get_car_by_car_no(db, car_in.car_no):
            raise DuplicateEntryException("Car with this number already exists")

        car_model = await inventory_crud.get_car_model_by_id(db, car_in.car_model_id)
        if not car_model:
            raise BadRequestException(
                f"Car model with id {car_in.car_model_id} not found"
            )

        color = await inventory_crud.get_by_id(db, models.Color, car_in.color_id)
        if not color:
            raise BadRequestException(f"Color with id {car_in.color_id} not found")

        result = await db.execute(
            select(models.Car).where(
                models.Car.car_model_id == car_in.car_model_id,
                models.Car.color_id == car_in.color_id,
            )
        )
        if result.scalar_one_or_none():
            raise BadRequestException(
                f"A car with color '{color.color_name}' already exists for this model"
            )

        if not await rbac_crud.get_status_by_id(db, car_in.status_id):
            raise BadRequestException(f"Status with id {car_in.status_id} not found")

        if valid_images:
            if len(valid_images) > 5:
                raise BadRequestException("Maximum 5 images allowed")

            for idx, image_file in enumerate(valid_images):
                await self._validate_image_format_and_size(image_file)

        car_data = car_in.model_dump()
        car_data["image_urls"] = []

        db_car = models.Car(**car_data, created_by=creator.id)
        created_db_car = await inventory_crud.create_car(db, db_car)

        if valid_images:
            image_urls = []
            try:
                for idx, image_file in enumerate(valid_images):
                    url = await self._upload_car_image(
                        created_db_car.id, image_file, idx + 1
                    )
                    image_urls.append(url)

                created_db_car.image_urls = image_urls
                await db.commit()
                await db.refresh(created_db_car)

            except Exception as e:
                if image_urls:
                    await self._delete_car_images(image_urls)
                raise BadRequestException(
                    f"Image upload failed: {str(e)}. Car created with ID {created_db_car.id} but without images."
                )
        else:
            await db.commit()
            await db.refresh(created_db_car)

        return created_db_car


    async def get_car(self, db: AsyncSession, car_id: int) -> schemas.CarComplete:
        """
        Get car by ID with all nested data.
        
        Args:
            db: Database session
            car_id: Car ID to retrieve
        
        Returns:
            Car complete schema with all details
        """
        db_car = await inventory_crud.get_car_with_all_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        return schemas.CarComplete(
            id=db_car.id,
            car_no=db_car.car_no,
            manufacture_year=db_car.manufacture_year,
            image_urls=db_car.image_urls,
            last_serviced_date=db_car.last_serviced_date,
            service_frequency_months=db_car.service_frequency_months,
            insured_till=db_car.insured_till,
            pollution_expiry=db_car.pollution_expiry,
            created_at=db_car.created_at,
            color=schemas.ColorPublic(
                id=db_car.color.id, color_name=db_car.color.color_name
            ),
            status=schemas.StatusPublic(id=db_car.status.id, name=db_car.status.name),
            brand=db_car.car_model.brand,
            model=db_car.car_model.model,
            category=schemas.CategoryPublic(
                id=db_car.car_model.category.id,
                category_name=db_car.car_model.category.category_name,
            ),
            fuel=schemas.FuelPublic(
                id=db_car.car_model.fuel.id, fuel_name=db_car.car_model.fuel.fuel_name
            ),
            capacity=schemas.CapacityPublic(
                id=db_car.car_model.capacity.id,
                capacity_value=db_car.car_model.capacity.capacity_value,
            ),
            transmission_type=db_car.car_model.transmission_type,
            mileage=db_car.car_model.mileage,
            rental_per_hr=db_car.car_model.rental_per_hr,
            dynamic_rental_price=db_car.car_model.dynamic_rental_price,
            kilometer_limit_per_hr=db_car.car_model.kilometer_limit_per_hr,
            features=[
                schemas.FeaturePublic(id=feature.id, feature_name=feature.feature_name)
                for feature in db_car.car_model.features
            ],
            reviews=[
                schemas.ReviewPublic(
                    id=review.id,
                    rating=review.rating,
                    remarks=review.remarks,
                    created_by=review.creator.id if review.creator else "Unknown",
                    created_at=review.created_at,
                )
                for review in db_car.reviews
            ],
        )


    async def list_cars(
        self, db: AsyncSession, params: schemas.CarFilterParams, skip: int, limit: int
    ) -> schemas.PaginatedCarSimpleResponse:
        """
        List cars with pagination.
        
        Args:
            db: Database session
            params: Car filter parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
        
        Returns:
            Paginated car simple response
        """
        items, total = await inventory_crud.get_all_cars_paginated(
            db, params, skip, limit
        )

        formatted_items = []
        for car in items:
            formatted_car = schemas.CarSimple(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
            )
            formatted_items.append(formatted_car)

        return schemas.PaginatedCarSimpleResponse(total=total, items=formatted_items)


    async def get_car_with_features(
        self, db: AsyncSession, car_id: int
    ) -> schemas.CarWithFeatures:
        """
        Get car with features by ID.
        
        Args:
            db: Database session
            car_id: Car ID to retrieve
        
        Returns:
            Car with features schema
        """
        db_car = await inventory_crud.get_car_with_features_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        return schemas.CarWithFeatures(
            id=db_car.id,
            car_no=db_car.car_no,
            manufacture_year=db_car.manufacture_year,
            image_urls=db_car.image_urls,
            color=schemas.ColorPublic(
                id=db_car.color.id, color_name=db_car.color.color_name
            ),
            status=schemas.StatusPublic(id=db_car.status.id, name=db_car.status.name),
            brand=db_car.car_model.brand,
            model=db_car.car_model.model,
            category=schemas.CategoryPublic(
                id=db_car.car_model.category.id,
                category_name=db_car.car_model.category.category_name,
            ),
            fuel=schemas.FuelPublic(
                id=db_car.car_model.fuel.id, fuel_name=db_car.car_model.fuel.fuel_name
            ),
            capacity=schemas.CapacityPublic(
                id=db_car.car_model.capacity.id,
                capacity_value=db_car.car_model.capacity.capacity_value,
            ),
            transmission_type=db_car.car_model.transmission_type,
            mileage=db_car.car_model.mileage,
            rental_per_hr=db_car.car_model.rental_per_hr,
            dynamic_rental_price=db_car.car_model.dynamic_rental_price,
            kilometer_limit_per_hr=db_car.car_model.kilometer_limit_per_hr,
            features=[
                schemas.FeaturePublic(id=feature.id, feature_name=feature.feature_name)
                for feature in db_car.car_model.features
            ],
        )


    async def list_cars_with_features(
        self, db: AsyncSession, params: schemas.CarFilterParams, skip: int, limit: int
    ) -> schemas.PaginatedCarWithFeaturesResponse:
        """
        List cars with features.
        
        Args:
            db: Database session
            params: Car filter parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
        
        Returns:
            Paginated car with features response
        """
        items, total = await inventory_crud.get_all_cars_with_features_paginated(
            db, params, skip, limit
        )

        formatted_items = []
        for car in items:
            formatted_car = schemas.CarWithFeatures(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                brand=car.car_model.brand,
                model=car.car_model.model,
                category=schemas.CategoryPublic(
                    id=car.car_model.category.id,
                    category_name=car.car_model.category.category_name,
                ),
                fuel=schemas.FuelPublic(
                    id=car.car_model.fuel.id, fuel_name=car.car_model.fuel.fuel_name
                ),
                capacity=schemas.CapacityPublic(
                    id=car.car_model.capacity.id,
                    capacity_value=car.car_model.capacity.capacity_value,
                ),
                transmission_type=car.car_model.transmission_type,
                mileage=car.car_model.mileage,
                rental_per_hr=car.car_model.rental_per_hr,
                dynamic_rental_price=car.car_model.dynamic_rental_price,
                kilometer_limit_per_hr=car.car_model.kilometer_limit_per_hr,
                features=[
                    schemas.FeaturePublic(
                        id=feature.id, feature_name=feature.feature_name
                    )
                    for feature in car.car_model.features
                ],
            )
            formatted_items.append(formatted_car)

        return schemas.PaginatedCarWithFeaturesResponse(
            total=total, items=formatted_items
        )


    async def get_car_with_reviews(
        self, db: AsyncSession, car_id: int
    ) -> schemas.CarWithReviews:
        """
        Get car with reviews by ID.
        
        Args:
            db: Database session
            car_id: Car ID to retrieve
        
        Returns:
            Car with reviews schema
        """
        db_car = await inventory_crud.get_car_with_reviews_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        return schemas.CarWithReviews(
            id=db_car.id,
            car_no=db_car.car_no,
            manufacture_year=db_car.manufacture_year,
            image_urls=db_car.image_urls,
            color=schemas.ColorPublic(
                id=db_car.color.id, color_name=db_car.color.color_name
            ),
            status=schemas.StatusPublic(id=db_car.status.id, name=db_car.status.name),
            brand=db_car.car_model.brand,
            model=db_car.car_model.model,
            category=schemas.CategoryPublic(
                id=db_car.car_model.category.id,
                category_name=db_car.car_model.category.category_name,
            ),
            fuel=schemas.FuelPublic(
                id=db_car.car_model.fuel.id, fuel_name=db_car.car_model.fuel.fuel_name
            ),
            capacity=schemas.CapacityPublic(
                id=db_car.car_model.capacity.id,
                capacity_value=db_car.car_model.capacity.capacity_value,
            ),
            transmission_type=db_car.car_model.transmission_type,
            mileage=db_car.car_model.mileage,
            rental_per_hr=db_car.car_model.rental_per_hr,
            dynamic_rental_price=db_car.car_model.dynamic_rental_price,
            kilometer_limit_per_hr=db_car.car_model.kilometer_limit_per_hr,
            reviews=[
                schemas.ReviewPublic(
                    id=review.id,
                    rating=review.rating,
                    remarks=review.remarks,
                    created_by=review.creator.id if review.creator else "Unknown",
                    created_at=review.created_at,
                )
                for review in db_car.reviews
            ],
        )


    async def list_cars_with_reviews(
        self, db: AsyncSession, params: schemas.CarFilterParams, skip: int, limit: int
    ) -> schemas.PaginatedCarWithReviewsResponse:
        """
        List cars with reviews.
        
        Args:
            db: Database session
            params: Car filter parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
        
        Returns:
            Paginated car with reviews response
        """
        items, total = await inventory_crud.get_all_cars_with_reviews_paginated(
            db, params, skip, limit
        )

        formatted_items = []
        for car in items:
            formatted_car = schemas.CarWithReviews(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                brand=car.car_model.brand,
                model=car.car_model.model,
                category=schemas.CategoryPublic(
                    id=car.car_model.category.id,
                    category_name=car.car_model.category.category_name,
                ),
                fuel=schemas.FuelPublic(
                    id=car.car_model.fuel.id, fuel_name=car.car_model.fuel.fuel_name
                ),
                capacity=schemas.CapacityPublic(
                    id=car.car_model.capacity.id,
                    capacity_value=car.car_model.capacity.capacity_value,
                ),
                transmission_type=car.car_model.transmission_type,
                mileage=car.car_model.mileage,
                rental_per_hr=car.car_model.rental_per_hr,
                dynamic_rental_price=car.car_model.dynamic_rental_price,
                kilometer_limit_per_hr=car.car_model.kilometer_limit_per_hr,
                reviews=[
                    schemas.ReviewPublic(
                        id=review.id,
                        rating=review.rating,
                        remarks=review.remarks,
                        created_by=review.creator.id if review.creator else "Unknown",
                        created_at=review.created_at,
                    )
                    for review in car.reviews
                ],
            )
            formatted_items.append(formatted_car)

        return schemas.PaginatedCarWithReviewsResponse(
            total=total, items=formatted_items
        )


    async def get_car_with_features_and_reviews(
        self, db: AsyncSession, car_id: int
    ) -> schemas.CarComplete:
        """
        Get car with all details by ID.
        
        Args:
            db: Database session
            car_id: Car ID to retrieve
        
        Returns:
            Car complete schema with all details
        """
        return await self.get_car(db, car_id)


    async def list_cars_with_features_and_reviews(
        self, db: AsyncSession, params: schemas.CarFilterParams, skip: int, limit: int
    ) -> schemas.PaginatedCarCompleteResponse:
        """
        List cars with all details.
        
        Args:
            db: Database session
            params: Car filter parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
        
        Returns:
            Paginated car complete response
        """
        items, total = await inventory_crud.get_all_cars_with_all_paginated(
            db, params, skip, limit
        )

        formatted_items = []
        for car in items:
            formatted_car = schemas.CarComplete(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                last_serviced_date=car.last_serviced_date,
                service_frequency_months=car.service_frequency_months,
                insured_till=car.insured_till,
                pollution_expiry=car.pollution_expiry,
                created_at=car.created_at,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                brand=car.car_model.brand,
                model=car.car_model.model,
                category=schemas.CategoryPublic(
                    id=car.car_model.category.id,
                    category_name=car.car_model.category.category_name,
                ),
                fuel=schemas.FuelPublic(
                    id=car.car_model.fuel.id, fuel_name=car.car_model.fuel.fuel_name
                ),
                capacity=schemas.CapacityPublic(
                    id=car.car_model.capacity.id,
                    capacity_value=car.car_model.capacity.capacity_value,
                ),
                transmission_type=car.car_model.transmission_type,
                mileage=car.car_model.mileage,
                rental_per_hr=car.car_model.rental_per_hr,
                dynamic_rental_price=car.car_model.dynamic_rental_price,
                kilometer_limit_per_hr=car.car_model.kilometer_limit_per_hr,
                features=[
                    schemas.FeaturePublic(
                        id=feature.id, feature_name=feature.feature_name
                    )
                    for feature in car.car_model.features
                ],
                reviews=[
                    schemas.ReviewPublic(
                        id=review.id,
                        rating=review.rating,
                        remarks=review.remarks,
                        created_by=review.creator.id if review.creator else "Unknown",
                        created_at=review.created_at,
                    )
                    for review in car.reviews
                ],
            )
            formatted_items.append(formatted_car)

        return schemas.PaginatedCarCompleteResponse(total=total, items=formatted_items)


    async def update_car(
        self,
        db: AsyncSession,
        car_id: int,
        car_in: schemas.CarUpdate,
        new_images: Optional[List[UploadFile]] = None,
        delete_image_urls: Optional[str] = None,
    ) -> models.Car:
        """
        Update car with optional image management.
        
        Args:
            db: Database session
            car_id: Car ID to update
            car_in: Car update data
            new_images: Optional list of new image files to upload
            delete_image_urls: Optional comma-separated URLs of images to delete
        
        Returns:
            Updated car model instance
        """
        delete_urls_list = None
        if delete_image_urls:
            delete_urls_list = [
                url.strip() for url in delete_image_urls.split(",") if url.strip()
            ]

        valid_new_images = None
        if new_images:
            filtered = [
                img
                for img in new_images
                if img and hasattr(img, "filename") and img.filename
            ]
            valid_new_images = filtered if filtered else None

        update_data = car_in.model_dump(exclude_none=True)
        filtered_update_data = {
            k: v for k, v in update_data.items() if v != "" and v is not None
        }
        car_in = schemas.CarUpdate(**filtered_update_data)

        db_car = await inventory_crud.get_car_with_features_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        if car_in.car_no and car_in.car_no != db_car.car_no:
            if await inventory_crud.get_car_by_car_no(db, car_in.car_no):
                raise DuplicateEntryException("Car with this number already exists")

        if car_in.color_id:
            await self._validate_color(db, car_in.color_id)

            if car_in.color_id != db_car.color_id:
                car_model_id = car_in.car_model_id or db_car.car_model_id
                result = await db.execute(
                    select(models.Car).where(
                        models.Car.car_model_id == car_model_id,
                        models.Car.color_id == car_in.color_id,
                        models.Car.id != car_id,
                    )
                )
                if result.scalar_one_or_none():
                    color = await inventory_crud.get_by_id(
                        db, models.Color, car_in.color_id
                    )
                    raise BadRequestException(
                        f"A car with color '{color.color_name}' already exists for this model"
                    )

        if car_in.car_model_id:
            car_model = await inventory_crud.get_car_model_by_id(
                db, car_in.car_model_id
            )
            if not car_model:
                raise BadRequestException(
                    f"Car model with id {car_in.car_model_id} not found"
                )

        if car_in.status_id:
            if not await rbac_crud.get_status_by_id(db, car_in.status_id):
                raise BadRequestException(
                    f"Status with id {car_in.status_id} not found"
                )

        current_images = list(db_car.image_urls)
        images_to_delete = []

        if delete_urls_list:
            for url in delete_urls_list:
                if url not in current_images:
                    raise BadRequestException(
                        f"Image URL not found in car images: {url}"
                    )
                images_to_delete.append(url)

        remaining_images_count = len(current_images) - len(images_to_delete)
        new_images_count = len(valid_new_images) if valid_new_images else 0
        total_images = remaining_images_count + new_images_count

        if total_images > 5:
            raise BadRequestException(
                f"Total images would be {total_images}. Maximum 5 images allowed"
            )

        if valid_new_images:
            for idx, image_file in enumerate(valid_new_images):
                await self._validate_image_format_and_size(image_file)

        if images_to_delete:
            await self._delete_car_images(images_to_delete)
            for url in images_to_delete:
                current_images.remove(url)

        if valid_new_images:
            car_id_for_upload = car_id

            available_slots = self._find_available_image_slots(
                current_images, car_id_for_upload, len(valid_new_images)
            )

            if len(available_slots) < len(valid_new_images):
                raise BadRequestException(
                    f"Not enough available slots for {len(valid_new_images)} images"
                )

            uploaded_urls = []
            for idx, image_file in enumerate(valid_new_images):
                try:
                    image_index = available_slots[
                        idx
                    ]  # Use available slot (e.g., 1, 3, 5)
                    url = await self._upload_car_image(
                        car_id_for_upload, image_file, image_index
                    )
                    current_images.append(url)
                    uploaded_urls.append(url)
                except Exception as e:
                    if uploaded_urls:
                        await self._delete_car_images(uploaded_urls)
                    raise BadRequestException(
                        f"Failed to upload new image {idx + 1}: {str(e)}"
                    )

        update_data = car_in.model_dump(exclude_none=True)
        update_data["image_urls"] = current_images

        car_update_schema = schemas.CarUpdate(**update_data)
        updated_car = await inventory_crud.partial_update_car(
            db, db_car, car_update_schema
        )

        return updated_car


    async def delete_car(self, db: AsyncSession, car_id: int) -> None:
        """
        Delete car and its images from blob storage.
        
        Args:
            db: Database session
            car_id: Car ID to delete
        
        Returns:
            None
        """
        db_car = await inventory_crud.get_by_id(db, models.Car, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        if db_car.image_urls:
            await self._delete_car_images(db_car.image_urls)

        await inventory_crud.delete(db, db_car)


    async def deactivate_car(self, db: AsyncSession, car_id: int) -> schemas.Msg:
        """
        Deactivates a car by setting status to INACTIVE.
        This does not delete the car record, only marks it as inactive.
        The car will not be available for bookings after deactivation.

        Args:
            db: Database session
            car_id: Car ID to deactivate

        Returns:
            Msg: Success message

        Raises:
            NotFoundException: If car not found
            BadRequestException: If car is already inactive
        """
        # Get car with status loaded
        db_car = await inventory_crud.get_car_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        # Check if already inactive
        if db_car.status.name == "INACTIVE":
            raise BadRequestException("Car is already inactive")

        # Get INACTIVE status
        inactive_status = await rbac_crud.get_status_by_name(db, StatusEnum.INACTIVE)
        if not inactive_status:
            raise NotFoundException("INACTIVE status not found in system")

        # Update car status to INACTIVE using partial update
        car_update = CarUpdate(status_id=inactive_status.id)
        await inventory_crud.partial_update_car(db, db_car, car_update)

        return schemas.Msg(
            message=f"Car {db_car.car_no} has been deactivated successfully. It will no longer be available for bookings."
        )


    async def activate_car(self, db: AsyncSession, car_id: int) -> schemas.Msg:
        """
        Activates a car by setting status to ACTIVE.
        This restores the car's availability for bookings after it was deactivated.

        Args:
            db: Database session
            car_id: Car ID to activate

        Returns:
            Msg: Success message

        Raises:
            NotFoundException: If car not found
            BadRequestException: If car is already active
        """
        # Get car with status loaded
        db_car = await inventory_crud.get_car_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        # Check if already active
        if db_car.status.name == "ACTIVE":
            raise BadRequestException("Car is already active")

        # Get ACTIVE status
        active_status = await rbac_crud.get_status_by_name(db, StatusEnum.ACTIVE)
        if not active_status:
            raise NotFoundException("ACTIVE status not found in system")

        # Update car status to ACTIVE using partial update
        car_update = CarUpdate(status_id=active_status.id)
        await inventory_crud.partial_update_car(db, db_car, car_update)

        return schemas.Msg(
            message=f"Car {db_car.car_no} has been activated successfully. It is now available for bookings."
        )


    async def get_cars_due_for_service(
        self, db: AsyncSession, days: int = 10
    ) -> List[schemas.CarWithFeatures]:
        """Get cars due for service."""
        cars = await inventory_crud.get_cars_due_for_service(db, days)

        formatted_cars = []
        for car in cars:
            formatted_car = schemas.CarWithFeatures(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                brand=car.car_model.brand,
                model=car.car_model.model,
                category=schemas.CategoryPublic(
                    id=car.car_model.category.id,
                    category_name=car.car_model.category.category_name,
                ),
                fuel=schemas.FuelPublic(
                    id=car.car_model.fuel.id, fuel_name=car.car_model.fuel.fuel_name
                ),
                capacity=schemas.CapacityPublic(
                    id=car.car_model.capacity.id,
                    capacity_value=car.car_model.capacity.capacity_value,
                ),
                transmission_type=car.car_model.transmission_type,
                mileage=car.car_model.mileage,
                rental_per_hr=car.car_model.rental_per_hr,
                dynamic_rental_price=car.car_model.dynamic_rental_price,
                kilometer_limit_per_hr=car.car_model.kilometer_limit_per_hr,
                features=[
                    schemas.FeaturePublic(
                        id=feature.id, feature_name=feature.feature_name
                    )
                    for feature in car.car_model.features
                ],
            )
            formatted_cars.append(formatted_car)

        return formatted_cars


    async def update_car_service(
        self, db: AsyncSession, car_id: int, service_data: schemas.CarServiceUpdate
    ) -> schemas.CarWithFeatures:
        """
        Update car service information.
        
        Args:
            db: Database session
            car_id: Car ID to update
            service_data: Service update data
        
        Returns:
            Updated car with features schema
        """
        db_car = await inventory_crud.get_car_with_features_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        db_car.last_serviced_date = service_data.last_serviced_date
        if service_data.service_frequency_months:
            db_car.service_frequency_months = service_data.service_frequency_months

        await db.commit()
        await db.refresh(db_car)

        return schemas.CarWithFeatures(
            id=db_car.id,
            car_no=db_car.car_no,
            manufacture_year=db_car.manufacture_year,
            image_urls=db_car.image_urls,
            color=schemas.ColorPublic(
                id=db_car.color.id, color_name=db_car.color.color_name
            ),
            status=schemas.StatusPublic(id=db_car.status.id, name=db_car.status.name),
            brand=db_car.car_model.brand,
            model=db_car.car_model.model,
            category=schemas.CategoryPublic(
                id=db_car.car_model.category.id,
                category_name=db_car.car_model.category.category_name,
            ),
            fuel=schemas.FuelPublic(
                id=db_car.car_model.fuel.id, fuel_name=db_car.car_model.fuel.fuel_name
            ),
            capacity=schemas.CapacityPublic(
                id=db_car.car_model.capacity.id,
                capacity_value=db_car.car_model.capacity.capacity_value,
            ),
            transmission_type=db_car.car_model.transmission_type,
            mileage=db_car.car_model.mileage,
            rental_per_hr=db_car.car_model.rental_per_hr,
            dynamic_rental_price=db_car.car_model.dynamic_rental_price,
            kilometer_limit_per_hr=db_car.car_model.kilometer_limit_per_hr,
            features=[
                schemas.FeaturePublic(id=feature.id, feature_name=feature.feature_name)
                for feature in db_car.car_model.features
            ],
        )


    async def get_cars_insurance_expiring(
        self, db: AsyncSession, days: int = 10
    ) -> List[schemas.CarWithFeatures]:
        """
        Get cars with insurance expiring soon.
        
        Args:
            db: Database session
            days: Number of days to look ahead
        
        Returns:
            List of cars with features schema
        """
        cars = await inventory_crud.get_cars_insurance_expiring(db, days)

        formatted_cars = []
        for car in cars:
            formatted_car = schemas.CarWithFeatures(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                brand=car.car_model.brand,
                model=car.car_model.model,
                category=schemas.CategoryPublic(
                    id=car.car_model.category.id,
                    category_name=car.car_model.category.category_name,
                ),
                fuel=schemas.FuelPublic(
                    id=car.car_model.fuel.id, fuel_name=car.car_model.fuel.fuel_name
                ),
                capacity=schemas.CapacityPublic(
                    id=car.car_model.capacity.id,
                    capacity_value=car.car_model.capacity.capacity_value,
                ),
                transmission_type=car.car_model.transmission_type,
                mileage=car.car_model.mileage,
                rental_per_hr=car.car_model.rental_per_hr,
                dynamic_rental_price=car.car_model.dynamic_rental_price,
                kilometer_limit_per_hr=car.car_model.kilometer_limit_per_hr,
                features=[
                    schemas.FeaturePublic(
                        id=feature.id, feature_name=feature.feature_name
                    )
                    for feature in car.car_model.features
                ],
            )
            formatted_cars.append(formatted_car)

        return formatted_cars


    async def update_car_insurance(
        self, db: AsyncSession, car_id: int, insurance_data: schemas.CarInsuranceUpdate
    ) -> schemas.CarWithFeatures:
        """
        Update car insurance information.
        
        Args:
            db: Database session
            car_id: Car ID to update
            insurance_data: Insurance update data
        
        Returns:
            Updated car with features schema
        """
        db_car = await inventory_crud.get_car_with_features_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        db_car.insured_till = insurance_data.insured_till
        await db.commit()
        await db.refresh(db_car)

        return schemas.CarWithFeatures(
            id=db_car.id,
            car_no=db_car.car_no,
            manufacture_year=db_car.manufacture_year,
            image_urls=db_car.image_urls,
            color=schemas.ColorPublic(
                id=db_car.color.id, color_name=db_car.color.color_name
            ),
            status=schemas.StatusPublic(id=db_car.status.id, name=db_car.status.name),
            brand=db_car.car_model.brand,
            model=db_car.car_model.model,
            category=schemas.CategoryPublic(
                id=db_car.car_model.category.id,
                category_name=db_car.car_model.category.category_name,
            ),
            fuel=schemas.FuelPublic(
                id=db_car.car_model.fuel.id, fuel_name=db_car.car_model.fuel.fuel_name
            ),
            capacity=schemas.CapacityPublic(
                id=db_car.car_model.capacity.id,
                capacity_value=db_car.car_model.capacity.capacity_value,
            ),
            transmission_type=db_car.car_model.transmission_type,
            mileage=db_car.car_model.mileage,
            rental_per_hr=db_car.car_model.rental_per_hr,
            dynamic_rental_price=db_car.car_model.dynamic_rental_price,
            kilometer_limit_per_hr=db_car.car_model.kilometer_limit_per_hr,
            features=[
                schemas.FeaturePublic(id=feature.id, feature_name=feature.feature_name)
                for feature in db_car.car_model.features
            ],
        )


    async def get_cars_pollution_expiring(
        self, db: AsyncSession, days: int = 10
    ) -> List[schemas.CarWithFeatures]:
        """
        Get cars with pollution certificate expiring soon.
        
        Args:
            db: Database session
            days: Number of days to look ahead
        
        Returns:
            List of cars with features schema
        """
        cars = await inventory_crud.get_cars_pollution_expiring(db, days)

        # Format cars to CarWithFeatures schema
        formatted_cars = []
        for car in cars:
            formatted_car = schemas.CarWithFeatures(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                brand=car.car_model.brand,
                model=car.car_model.model,
                category=schemas.CategoryPublic(
                    id=car.car_model.category.id,
                    category_name=car.car_model.category.category_name,
                ),
                fuel=schemas.FuelPublic(
                    id=car.car_model.fuel.id, fuel_name=car.car_model.fuel.fuel_name
                ),
                capacity=schemas.CapacityPublic(
                    id=car.car_model.capacity.id,
                    capacity_value=car.car_model.capacity.capacity_value,
                ),
                transmission_type=car.car_model.transmission_type,
                mileage=car.car_model.mileage,
                rental_per_hr=car.car_model.rental_per_hr,
                dynamic_rental_price=car.car_model.dynamic_rental_price,
                kilometer_limit_per_hr=car.car_model.kilometer_limit_per_hr,
                features=[
                    schemas.FeaturePublic(
                        id=feature.id, feature_name=feature.feature_name
                    )
                    for feature in car.car_model.features
                ],
            )
            formatted_cars.append(formatted_car)

        return formatted_cars


    async def update_car_pollution(
        self, db: AsyncSession, car_id: int, pollution_data: schemas.CarPollutionUpdate
    ) -> schemas.CarWithFeatures:
        """
        Update car pollution certificate information.
        
        Args:
            db: Database session
            car_id: Car ID to update
            pollution_data: Pollution update data
        
        Returns:
            Updated car with features schema
        """
        db_car = await inventory_crud.get_car_with_features_by_id(db, car_id)
        if not db_car:
            raise NotFoundException("Car not found")

        db_car.pollution_expiry = pollution_data.pollution_expiry
        await db.commit()
        await db.refresh(db_car)

        return schemas.CarWithFeatures(
            id=db_car.id,
            car_no=db_car.car_no,
            manufacture_year=db_car.manufacture_year,
            image_urls=db_car.image_urls,
            color=schemas.ColorPublic(
                id=db_car.color.id, color_name=db_car.color.color_name
            ),
            status=schemas.StatusPublic(id=db_car.status.id, name=db_car.status.name),
            brand=db_car.car_model.brand,
            model=db_car.car_model.model,
            category=schemas.CategoryPublic(
                id=db_car.car_model.category.id,
                category_name=db_car.car_model.category.category_name,
            ),
            fuel=schemas.FuelPublic(
                id=db_car.car_model.fuel.id, fuel_name=db_car.car_model.fuel.fuel_name
            ),
            capacity=schemas.CapacityPublic(
                id=db_car.car_model.capacity.id,
                capacity_value=db_car.car_model.capacity.capacity_value,
            ),
            transmission_type=db_car.car_model.transmission_type,
            mileage=db_car.car_model.mileage,
            rental_per_hr=db_car.car_model.rental_per_hr,
            dynamic_rental_price=db_car.car_model.dynamic_rental_price,
            kilometer_limit_per_hr=db_car.car_model.kilometer_limit_per_hr,
            features=[
                schemas.FeaturePublic(id=feature.id, feature_name=feature.feature_name)
                for feature in db_car.car_model.features
            ],
        )


    async def get_car_model_details_for_customer(
        self,
        db: AsyncSession,
        trip_details: Optional[schemas.TripDetailsInput] = None,
        car_model_id: Optional[int] = None,
        delivery_lat: Optional[float] = None,
        delivery_lon: Optional[float] = None,
        pickup_lat: Optional[float] = None,
        pickup_lon: Optional[float] = None,
    ) -> schemas.CarModelDetailsPublicForCustomer:
        """
        Get car model details for customer with availability filtering.
        
        Args:
            db: Database session
            trip_details: Optional trip details input
            car_model_id: Car model ID to retrieve
            delivery_lat: Delivery location latitude
            delivery_lon: Delivery location longitude
            pickup_lat: Pickup location latitude
            pickup_lon: Pickup location longitude
        
        Returns:
            Car model details public for customer schema
        """
        if trip_details:
            await self._validate_trip_details(trip_details)

        delivery_distance = pickup_distance = total_distance = 0.0
        if (
            delivery_lat is not None
            and delivery_lon is not None
            and pickup_lat is not None
            and pickup_lon is not None
        ):
            try:
                delivery_distance, pickup_distance, total_distance = (
                    await self._validate_delivery_pickup_locations(
                        delivery_lat, delivery_lon, pickup_lat, pickup_lon
                    )
                )
            except BadRequestException as e:
                raise BadRequestException(f"Location validation failed: {str(e)}")

        active_status = await rbac_crud.get_status_by_name(db, "ACTIVE")
        if not active_status:
            raise BadRequestException("Active status not found")

        car_model = await inventory_crud.get_car_model_by_id(db, car_model_id)
        if not car_model:
            raise NotFoundException("Car model not found")

        car_model_details = await inventory_crud.get_car_model_details_by_id(
            db, car_model_id
        )
        if not car_model_details:
            raise NotFoundException("Car model details not found")

        active_cars = [
            car for car in car_model.cars if car.status and car.status.name == "ACTIVE"
        ]

        if trip_details and active_cars:
            available_cars = []
            for car in active_cars:
                try:
                    # Check car availability for the trip dates
                    is_available = await booking_crud.check_car_availability(
                        db, car.id, trip_details.start_date, trip_details.end_date
                    )
                    if is_available:
                        available_cars.append(car)
                except Exception as e:
                    logger.error(
                        f"Error checking availability for car {car.id}: {str(e)}"
                    )
                    continue

            active_cars = available_cars

        cars_for_customer = []
        for car in active_cars:
            car_details = schemas.CarDetailsPublicForCustomer(
                id=car.id,
                car_no=car.car_no,
                manufacture_year=car.manufacture_year,
                image_urls=car.image_urls,
                last_serviced_date=car.last_serviced_date,
                service_frequency_months=car.service_frequency_months,
                insured_till=car.insured_till,
                pollution_expiry=car.pollution_expiry,
                reviews=[
                    schemas.ReviewPublic(
                        id=review.id,
                        rating=review.rating,
                        remarks=review.remarks,
                        created_at=review.created_at,
                        created_by=review.creator.id if review.creator else "Unknown",
                    )
                    for review in car.reviews
                ],
                created_at=car.created_at,
                color=schemas.ColorPublic(
                    id=car.color.id, color_name=car.color.color_name
                ),
                status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
            )
            cars_for_customer.append(car_details)

        return schemas.CarModelDetailsPublicForCustomer(
            id=car_model.id,
            brand=car_model.brand,
            model=car_model.model,
            category=schemas.CategoryPublic(
                id=car_model.category.id, category_name=car_model.category.category_name
            ),
            fuel=schemas.FuelPublic(
                id=car_model.fuel.id, fuel_name=car_model.fuel.fuel_name
            ),
            capacity=schemas.CapacityPublic(
                id=car_model.capacity.id,
                capacity_value=car_model.capacity.capacity_value,
            ),
            transmission_type=car_model.transmission_type,
            mileage=car_model.mileage,
            rental_per_hr=car_model.rental_per_hr,
            dynamic_rental_price=car_model.dynamic_rental_price,
            kilometer_limit_per_hr=car_model.kilometer_limit_per_hr,
            features=[
                schemas.FeaturePublic(id=feature.id, feature_name=feature.feature_name)
                for feature in car_model.features
            ],
            cars=cars_for_customer,
            created_at=car_model.created_at,
        )


    def apply_car_model_filters(self, query, filters):
        """
        Apply filters to car model query.
        
        Args:
            query: SQLAlchemy query to apply filters to
            filters: Car model filter parameters
        
        Returns:
            Filtered query
        """
        if not filters:
            return query

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.where(
                or_(
                    models.CarModel.brand.ilike(search_term),
                    models.CarModel.model.ilike(search_term),
                )
            )

        if filters.category_id:
            query = query.where(models.CarModel.category_id == filters.category_id)

        if filters.fuel_id:
            query = query.where(models.CarModel.fuel_id == filters.fuel_id)

        if filters.capacity_id:
            query = query.where(models.CarModel.capacity_id == filters.capacity_id)

        if filters.transmission_type:
            query = query.where(
                models.CarModel.transmission_type == filters.transmission_type
            )

        return query


    async def get_car_models_for_customers(
        self,
        db: AsyncSession,
        trip_details: Optional[schemas.TripDetailsInput] = None,
        filters: Optional[schemas.CarModelFilterParams] = None,
        delivery_lat: Optional[float] = None,
        delivery_lon: Optional[float] = None,
        pickup_lat: Optional[float] = None,
        pickup_lon: Optional[float] = None,
        sort_by: str = "dynamic_rental_price",
        sort_order: str = "asc",
        skip: int = 0,
        limit: int = 20,
    ) -> schemas.PaginatedCarModelPublicResponse:
        """
        Get car models for customers with filtering and pagination.
        
        Args:
            db: Database session
            trip_details: Optional trip details input
            filters: Optional car model filter parameters
            delivery_lat: Delivery location latitude
            delivery_lon: Delivery location longitude
            pickup_lat: Pickup location latitude
            pickup_lon: Pickup location longitude
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)
            skip: Number of records to skip
            limit: Maximum number of records to return
        
        Returns:
            Paginated car model public response
        """
        if trip_details:
            await self._validate_trip_details(trip_details)

        delivery_distance = pickup_distance = total_distance = 0.0
        if (
            delivery_lat is not None
            and delivery_lon is not None
            and pickup_lat is not None
            and pickup_lon is not None
        ):
            delivery_distance, pickup_distance, total_distance = (
                await self._validate_delivery_pickup_locations(
                    delivery_lat, delivery_lon, pickup_lat, pickup_lon
                )
            )

        active_status = await rbac_crud.get_status_by_name(db, "ACTIVE")
        if not active_status:
            raise BadRequestException("Active status not found")

        active_car_exists = (
            select(models.Car.id)
            .where(
                models.Car.car_model_id == models.CarModel.id,
                models.Car.status_id == active_status.id,
            )
            .limit(1)
        )

        query = (
            select(models.CarModel)
            .options(
                selectinload(models.CarModel.category),
                selectinload(models.CarModel.fuel),
                selectinload(models.CarModel.capacity),
                selectinload(models.CarModel.features),
                selectinload(models.CarModel.cars).selectinload(models.Car.color),
                selectinload(models.CarModel.cars).selectinload(models.Car.status),
            )
            .where(active_car_exists.exists())
        )

        query = self.apply_car_model_filters(query, filters)

        if sort_by == "dynamic_rental_price":
            query = query.order_by(
                models.CarModel.dynamic_rental_price.desc()
                if sort_order == "desc"
                else models.CarModel.dynamic_rental_price.asc()
            )
        else:
            query = query.order_by(
                models.CarModel.brand.asc(), models.CarModel.model.asc()
            )

        count_query = select(func.count(models.CarModel.id)).where(
            active_car_exists.exists()
        )
        count_query = self.apply_car_model_filters(count_query, filters)

        total_count = (await db.execute(count_query)).scalar()

        result = await db.execute(query.offset(skip).limit(limit))
        car_models = result.scalars().unique().all()

        processed_models = []

        for car_model in car_models:

            active_cars = [
                car
                for car in car_model.cars
                if car.status and car.status.name == "ACTIVE"
            ]

            if trip_details:
                available_cars = []
                for car in active_cars:
                    try:
                        is_available = await booking_crud.check_car_availability(
                            db, car.id, trip_details.start_date, trip_details.end_date
                        )
                        if is_available:
                            available_cars.append(car)
                    except Exception:
                        continue

                if not available_cars:
                    continue

                active_cars = available_cars

            if not active_cars:
                continue

            delivery_charges = Decimal("0.00")
            if total_distance > 0:
                delivery_charges = (
                    Decimal("1000.00")
                    if total_distance <= 30
                    else Decimal("2000.00") if total_distance <= 60 else Decimal("0.00")
                )

            cars_for_customer = [
                schemas.CarPublicForCustomer(
                    id=car.id,
                    car_no=car.car_no,
                    manufacture_year=car.manufacture_year,
                    image_urls=car.image_urls,
                    last_serviced_date=car.last_serviced_date,
                    service_frequency_months=car.service_frequency_months,
                    insured_till=car.insured_till,
                    pollution_expiry=car.pollution_expiry,
                    created_at=car.created_at,
                    color=schemas.ColorPublic(
                        id=car.color.id, color_name=car.color.color_name
                    ),
                    status=schemas.StatusPublic(id=car.status.id, name=car.status.name),
                )
                for car in active_cars
            ]

            processed_models.append(
                schemas.CarModelPublicForCustomer(
                    id=car_model.id,
                    brand=car_model.brand,
                    model=car_model.model,
                    category=schemas.CategoryPublic(
                        id=car_model.category.id,
                        category_name=car_model.category.category_name,
                    ),
                    fuel=schemas.FuelPublic(
                        id=car_model.fuel.id, fuel_name=car_model.fuel.fuel_name
                    ),
                    capacity=schemas.CapacityPublic(
                        id=car_model.capacity.id,
                        capacity_value=car_model.capacity.capacity_value,
                    ),
                    transmission_type=car_model.transmission_type,
                    mileage=car_model.mileage,
                    rental_per_hr=car_model.rental_per_hr,
                    dynamic_rental_price=car_model.dynamic_rental_price,
                    kilometer_limit_per_hr=car_model.kilometer_limit_per_hr,
                    features=[
                        schemas.FeaturePublic(id=f.id, feature_name=f.feature_name)
                        for f in car_model.features
                    ],
                    cars=cars_for_customer,
                    created_at=car_model.created_at,
                )
            )

        return schemas.PaginatedCarModelPublicResponse(
            total=total_count, items=processed_models, skip=skip, limit=limit
        )


    async def get_available_slots_for_car(
        self, db: AsyncSession, car_id: int
    ) -> schemas.CarAvailabilityResponse:
        """
        Get available time slots for a specific car.
        
        Args:
            db: Database session
            car_id: Car ID to check availability for
        
        Returns:
            Car availability response with available slots
        """
        car = await inventory_crud.get_car_by_id(db, car_id)
        if not car:
            raise NotFoundException("Car not found")

        available_slots = await self._get_available_slots_for_car(db, car_id)

        formatted_slots = []
        for slot in available_slots:
            duration_hours = (slot["end"] - slot["start"]).total_seconds() / 3600

            max_end_time = datetime.now(timezone.utc) + timedelta(days=15)
            effective_end = min(slot["end"], max_end_time)

            effective_duration = (effective_end - slot["start"]).total_seconds() / 3600

            if effective_duration >= 8:
                formatted_slots.append(
                    {
                        "start": slot["start"],
                        "end": effective_end,
                        "duration_hours": effective_duration,
                    }
                )

        return schemas.CarAvailabilityResponse(
            car_id=car_id,
            car_details={
                "id": car.id,
                "car_no": car.car_no,
                "brand": car.car_model.brand,
                "model": car.car_model.model,
                "color": car.color.color_name if car.color else "N/A",
            },
            available_slots=formatted_slots,
            max_advance_days=15,
        )


    async def _get_lookup_maps(self, db: AsyncSession) -> Dict[str, Dict]:
        """
        Get lookup maps for import validation.
        
        Args:
            db: Database session
        
        Returns:
            Dictionary containing lookup maps for categories, fuels, capacities, colors, and statuses
        """
        categories = await inventory_crud.get_all(db, models.Category)
        fuels = await inventory_crud.get_all(db, models.Fuel)
        capacities = await inventory_crud.get_all(db, models.Capacity)
        colors = await inventory_crud.get_all(db, models.Color)
        statuses = await rbac_crud.get_all_statuses(db)

        return {
            "categories": {cat.category_name.lower(): cat.id for cat in categories},
            "fuels": {fuel.fuel_name.lower(): fuel.id for fuel in fuels},
            "capacities": {str(cap.capacity_value): cap.id for cap in capacities},
            "colors": {color.color_name.lower(): color.id for color in colors},
            "statuses": {stat.name.lower(): stat.id for stat in statuses},
        }


    async def get_import_template(self) -> StreamingResponse:
        """
        Get import template.
        
        Args:
            None
        
        Returns:
            StreamingResponse with Excel template file
        """
        df = pd.DataFrame(columns=IMPORT_EXPORT_COLUMNS)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Cars", index=False)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=car_import_template.xlsx"
            },
        )


    async def import_cars(
        self, db: AsyncSession, file: UploadFile, creator: models.User
    ) -> schemas.Msg:
        """
        Import cars from file.
        
        Args:
            db: Database session
            file: Upload file containing car data
            creator: User importing the cars
        
        Returns:
            Message schema with import result
        """
        if file.content_type not in ALLOWED_MIMETYPES:
            raise BadRequestException(
                f"Invalid file type. Allowed: {', '.join(ALLOWED_MIMETYPES)}"
            )

        file_content = await file.read()
        if len(file_content) > (MAX_FILE_SIZE_MB * 1024 * 1024):
            raise BadRequestException(f"File size exceeds {MAX_FILE_SIZE_MB}MB limit.")

        try:
            if file.content_type == "text/csv":
                df = pd.read_csv(BytesIO(file_content))
            else:
                df = pd.read_excel(BytesIO(file_content))
            df = df.fillna("")
        except Exception as e:
            raise BadRequestException(f"Could not read file. Error: {str(e)}")

        if not all(col in df.columns for col in IMPORT_EXPORT_COLUMNS):
            missing = set(IMPORT_EXPORT_COLUMNS) - set(df.columns)
            raise BadRequestException(f"Missing required columns: {', '.join(missing)}")

        lookup_maps = await self._get_lookup_maps(db)

        errors = []
        cars_to_create = []

        for index, row in df.iterrows():
            try:
                row_data = row.to_dict()

                def parse_date(date_str):
                    if not date_str or pd.isna(date_str):
                        return None
                    try:
                        return pd.to_datetime(date_str)
                    except:
                        return None

                import_data = {
                    "Car Number": str(row_data.get("Car Number", "")).strip(),
                    "Brand": str(row_data.get("Brand", "")).strip(),
                    "Model": str(row_data.get("Model", "")).strip(),
                    "Color": str(row_data.get("Color", "")).strip(),
                    "Mileage": (
                        int(row_data.get("Mileage", 0))
                        if str(row_data.get("Mileage", "0")).strip()
                        else 0
                    ),
                    "Rental Per Hour": Decimal(
                        str(row_data.get("Rental Per Hour", "0"))
                    ).quantize(Decimal("0.01")),
                    "Manufacture Year": (
                        int(row_data.get("Manufacture Year", 0))
                        if str(row_data.get("Manufacture Year", "0")).strip()
                        else 0
                    ),
                    "Transmission Type": str(row_data.get("Transmission Type", ""))
                    .strip()
                    .upper(),
                    "Category": str(row_data.get("Category", "")).strip(),
                    "Fuel Type": str(row_data.get("Fuel Type", "")).strip(),
                    "Capacity": (
                        int(row_data.get("Capacity", 0))
                        if str(row_data.get("Capacity", "0")).strip()
                        else 0
                    ),
                    "Status": str(row_data.get("Status", "")).strip(),
                    "Features (comma-separated)": str(
                        row_data.get("Features (comma-separated)", "")
                    ).strip(),
                    "Last Serviced Date": parse_date(
                        row_data.get("Last Serviced Date")
                    ),
                    "Service Frequency Months": (
                        int(row_data.get("Service Frequency Months", 3))
                        if str(row_data.get("Service Frequency Months", "3")).strip()
                        else 3
                    ),
                    "Insured Till": parse_date(row_data.get("Insured Till")),
                    "Pollution Expiry": parse_date(row_data.get("Pollution Expiry")),
                }

                required_fields = [
                    "Car Number",
                    "Brand",
                    "Model",
                    "Color",
                    "Category",
                    "Fuel Type",
                    "Status",
                ]
                for field in required_fields:
                    if not import_data[field]:
                        raise ValueError(f"{field} is required")

                category_id = lookup_maps["categories"].get(
                    import_data["Category"].lower()
                )
                fuel_id = lookup_maps["fuels"].get(import_data["Fuel Type"].lower())
                capacity_id = lookup_maps["capacities"].get(
                    str(import_data["Capacity"])
                )
                color_id = lookup_maps["colors"].get(import_data["Color"].lower())
                status_id = lookup_maps["statuses"].get(import_data["Status"].lower())

                if not category_id:
                    raise ValueError(f"Category '{import_data['Category']}' not found.")
                if not fuel_id:
                    raise ValueError(
                        f"Fuel Type '{import_data['Fuel Type']}' not found."
                    )
                if not capacity_id:
                    raise ValueError(f"Capacity '{import_data['Capacity']}' not found.")
                if not color_id:
                    raise ValueError(f"Color '{import_data['Color']}' not found.")
                if not status_id:
                    raise ValueError(f"Status '{import_data['Status']}' not found.")

                try:
                    transmission_type = schemas.TransmissionType(
                        import_data["Transmission Type"]
                    )
                except ValueError:
                    raise ValueError(
                        f"Invalid Transmission Type: {import_data['Transmission Type']}"
                    )

                if await inventory_crud.get_car_by_car_no(
                    db, import_data["Car Number"]
                ):
                    raise ValueError(
                        f"Car Number '{import_data['Car Number']}' already exists."
                    )

                car_model = await inventory_crud.get_car_model_by_brand_model(
                    db, import_data["Brand"], import_data["Model"]
                )
                if not car_model:
                    car_model_data = schemas.CarModelCreate(
                        brand=import_data["Brand"],
                        model=import_data["Model"],
                        category_id=category_id,
                        fuel_id=fuel_id,
                        capacity_id=capacity_id,
                        transmission_type=transmission_type,
                        mileage=import_data["Mileage"],
                        rental_per_hr=import_data["Rental Per Hour"],
                        dynamic_rental_price=import_data["Rental Per Hour"],
                        kilometer_limit_per_hr=50,
                        features=[
                            f.strip()
                            for f in import_data["Features (comma-separated)"].split(
                                ","
                            )
                            if f.strip()
                        ],
                    )
                    car_model = await self.create_car_model(db, car_model_data, creator)

                result = await db.execute(
                    select(models.Car).where(
                        models.Car.car_model_id == car_model.id,
                        models.Car.color_id == color_id,
                    )
                )
                if result.scalar_one_or_none():
                    raise ValueError(
                        f"Color '{import_data['Color']}' already exists for car model '{import_data['Brand']} {import_data['Model']}'"
                    )

                car_in_create = schemas.CarCreate(
                    car_no=import_data["Car Number"],
                    car_model_id=car_model.id,
                    color_id=color_id,
                    manufacture_year=import_data["Manufacture Year"],
                    status_id=status_id,
                    last_serviced_date=import_data["Last Serviced Date"],
                    service_frequency_months=import_data["Service Frequency Months"],
                    insured_till=import_data["Insured Till"],
                    pollution_expiry=import_data["Pollution Expiry"],
                )
                cars_to_create.append(car_in_create)

            except (ValidationError, ValueError) as e:
                errors.append(f"Row {index + 2}: {str(e)}")
            except Exception as e:
                errors.append(f"Row {index + 2}: Unexpected error: {str(e)}")

        if errors:
            raise BadRequestException(
                detail=f"Validation failed. First 5 errors: {'; '.join(errors[:5])}"
            )

        created_count = 0
        try:
            for car_in in cars_to_create:
                await self.create_car(db, car_in, creator)
                created_count += 1

        except Exception as e:
            await db.rollback()
            raise BadRequestException(f"Error during database insert: {str(e)}")

        return schemas.Msg(message=f"Successfully imported {created_count} cars.")


    async def export_cars(
        self, db: AsyncSession, params: schemas.CarFilterParams
    ) -> StreamingResponse:
        """
        Export cars to Excel.
        
        Args:
            db: Database session
            params: Car filter parameters
        
        Returns:
            StreamingResponse with Excel export file
        """
        cars = await inventory_crud.get_all_cars_for_export(db, params)

        export_data = []
        for car in cars:
            def format_date(date_obj):
                if date_obj:
                    return date_obj.strftime("%Y-%m-%d %H:%M:%S")
                return ""

            export_data.append(
                {
                    "Car Number": car.car_no,
                    "Brand": car.car_model.brand,
                    "Model": car.car_model.model,
                    "Color": car.color.color_name if car.color else "N/A",
                    "Mileage": car.car_model.mileage,
                    "Rental Per Hour": float(car.car_model.rental_per_hr),
                    "Manufacture Year": car.manufacture_year,
                    "Transmission Type": car.car_model.transmission_type.value,
                    "Category": car.car_model.category.category_name,
                    "Fuel Type": car.car_model.fuel.fuel_name,
                    "Capacity": car.car_model.capacity.capacity_value,
                    "Status": car.status.name if car.status else "N/A",
                    "Features (comma-separated)": ", ".join(
                        [f.feature_name for f in car.car_model.features]
                    ),
                    "Last Serviced Date": format_date(car.last_serviced_date),
                    "Service Frequency Months": car.service_frequency_months,
                    "Insured Till": format_date(car.insured_till),
                    "Pollution Expiry": format_date(car.pollution_expiry),
                }
            )

        df = pd.DataFrame(export_data, columns=IMPORT_EXPORT_COLUMNS)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Cars", index=False)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=car_export.xlsx"},
        )


inventory_service = InventoryService()
