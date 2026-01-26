from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple
from datetime import datetime, timedelta


from app import models, schemas


class InventoryCRUD:
    """
    Class for managing inventory-related database operations.
    """
    async def get_by_id(
        self, db: AsyncSession, model: type[models.Base], obj_id: int
    ) -> Optional[models.Base]:
        """
        Get object by ID.

        Args:
            db: Database session
            model: Model class
            obj_id: Object ID

        Returns:
            Object if found, None otherwise
        """
        return await db.get(model, obj_id)


    async def get_all(self, db: AsyncSession, model: type[models.Base]) -> List[models.Base]:
        """
        Get all objects of a model.

        Args:
            db: Database session
            model: Model class

        Returns:
            List of all model objects
        """
        result = await db.execute(select(model))
        return result.scalars().all()


    async def delete(self, db: AsyncSession, db_obj: models.Base) -> None:
        """
        Delete object.

        Args:
            db: Database session
            db_obj: Object to delete

        Returns:
            None
        """
        await db.delete(db_obj)
        await db.commit()


    async def get_category_by_name(
        self, db: AsyncSession, name: str
    ) -> Optional[models.Category]:
        """
        Get category by name.

        Args:
            db: Database session
            name: Category name

        Returns:
            Category if found, None otherwise
        """
        result = await db.execute(
            select(models.Category).where(models.Category.category_name.ilike(name))
        )
        return result.scalar_one_or_none()


    async def create_category(
        self, db: AsyncSession, category_in: schemas.CategoryCreate
    ) -> models.Category:
        """
        Create category.

        Args:
            db: Database session
            category_in: Category data

        Returns:
            Created category
        """
        db_category = models.Category(**category_in.model_dump())
        db.add(db_category)
        await db.commit()
        await db.refresh(db_category)
        return db_category


    async def update_category(
        self, db: AsyncSession, db_category: models.Category, category_in: schemas.CategoryUpdate
    ) -> models.Category:
        """
        Update category.

        Args:
            db: Database session
            db_category: Category to update
            category_in: Updated category data

        Returns:
            Updated category
        """
        db_category.category_name = category_in.category_name
        await db.commit()
        await db.refresh(db_category)
        return db_category


    async def get_fuel_by_name(self, db: AsyncSession, name: str) -> Optional[models.Fuel]:
        """
        Get fuel by name.

        Args:
            db: Database session
            name: Fuel name

        Returns:
            Fuel if found, None otherwise
        """
        result = await db.execute(
            select(models.Fuel).where(models.Fuel.fuel_name.ilike(name))
        )
        return result.scalar_one_or_none()


    async def create_fuel(self, db: AsyncSession, fuel_in: schemas.FuelCreate) -> models.Fuel:
        """
        Create fuel.

        Args:
            db: Database session
            fuel_in: Fuel data

        Returns:
            Created fuel
        """
        db_fuel = models.Fuel(**fuel_in.model_dump())
        db.add(db_fuel)
        await db.commit()
        await db.refresh(db_fuel)
        return db_fuel


    async def update_fuel(
        self, db: AsyncSession, db_fuel: models.Fuel, fuel_in: schemas.FuelUpdate
    ) -> models.Fuel:
        """
        Update fuel.

        Args:
            db: Database session
            db_fuel: Fuel to update
            fuel_in: Updated fuel data

        Returns:
            Updated fuel
        """
        db_fuel.fuel_name = fuel_in.fuel_name
        await db.commit()
        await db.refresh(db_fuel)
        return db_fuel


    async def get_capacity_by_value(
        self, db: AsyncSession, value: int
    ) -> Optional[models.Capacity]:
        """
        Get capacity by value.

        Args:
            db: Database session
            value: Capacity value

        Returns:
            Capacity if found, None otherwise
        """
        result = await db.execute(
            select(models.Capacity).where(models.Capacity.capacity_value == value)
        )
        return result.scalar_one_or_none()


    async def create_capacity(
        self, db: AsyncSession, capacity_in: schemas.CapacityCreate
    ) -> models.Capacity:
        """
        Create capacity.

        Args:
            db: Database session
            capacity_in: Capacity data

        Returns:
            Created capacity
        """
        db_capacity = models.Capacity(**capacity_in.model_dump())
        db.add(db_capacity)
        await db.commit()
        await db.refresh(db_capacity)
        return db_capacity


    async def update_capacity(
        self, db: AsyncSession, db_capacity: models.Capacity, capacity_in: schemas.CapacityUpdate
    ) -> models.Capacity:
        """
        Update capacity.

        Args:
            db: Database session
            db_capacity: Capacity to update
            capacity_in: Updated capacity data

        Returns:
            Updated capacity
        """
        db_capacity.capacity_value = capacity_in.capacity_value
        await db.commit()
        await db.refresh(db_capacity)
        return db_capacity


    async def get_feature_by_name(self, db: AsyncSession, name: str) -> Optional[models.Feature]:
        """
        Get feature by name.

        Args:
            db: Database session
            name: Feature name

        Returns:
            Feature if found, None otherwise
        """
        result = await db.execute(
            select(models.Feature).where(models.Feature.feature_name.ilike(name))
        )
        return result.scalar_one_or_none()


    async def create_feature(
        self, db: AsyncSession, feature_in: schemas.FeatureCreate
    ) -> models.Feature:
        """
        Create feature.

        Args:
            db: Database session
            feature_in: Feature data

        Returns:
            Created feature
        """
        db_feature = models.Feature(**feature_in.model_dump())
        db.add(db_feature)
        await db.commit()
        await db.refresh(db_feature)
        return db_feature


    async def update_feature(
        self, db: AsyncSession, db_feature: models.Feature, feature_in: schemas.FeatureUpdate
    ) -> models.Feature:
        """
        Update feature.

        Args:
            db: Database session
            db_feature: Feature to update
            feature_in: Updated feature data

        Returns:
            Updated feature
        """
        db_feature.feature_name = feature_in.feature_name
        await db.commit()
        await db.refresh(db_feature)
        return db_feature


    async def get_color_by_name(self, db: AsyncSession, name: str) -> Optional[models.Color]:
        """
        Get color by name.

        Args:
            db: Database session
            name: Color name

        Returns:
            Color if found, None otherwise
        """
        result = await db.execute(
            select(models.Color).where(models.Color.color_name.ilike(name))
        )
        return result.scalar_one_or_none()


    async def create_color(self, db: AsyncSession, color_in: schemas.ColorCreate) -> models.Color:
        """
        Create color.

        Args:
            db: Database session
            color_in: Color data

        Returns:
            Created color
        """
        db_color = models.Color(**color_in.model_dump())
        db.add(db_color)
        await db.commit()
        await db.refresh(db_color)
        return db_color


    async def update_color(
        self, db: AsyncSession, db_color: models.Color, color_in: schemas.ColorUpdate
    ) -> models.Color:
        """
        Update color.

        Args:
            db: Database session
            db_color: Color to update
            color_in: Updated color data

        Returns:
            Updated color
        """
        db_color.color_name = color_in.color_name
        await db.commit()
        await db.refresh(db_color)
        return db_color


    async def get_or_create_features(
        self, db: AsyncSession, feature_names: List[str]
    ) -> List[models.Feature]:
        """
        Get or create features.

        Args:
            db: Database session
            feature_names: List of feature names

        Returns:
            List of feature objects
        """
        if not feature_names:
            return []

        normalized_names = [name.strip().lower() for name in feature_names if name.strip()]
        if not normalized_names:
            return []

        existing_features_result = await db.execute(
            select(models.Feature).where(
                func.lower(models.Feature.feature_name).in_(normalized_names)
            )
        )
        existing_features = existing_features_result.scalars().all()
        existing_names = {f.feature_name.lower() for f in existing_features}

        new_features = []
        for original_name in feature_names:
            normalized = original_name.strip().lower()
            if normalized and normalized not in existing_names:
                db_feature = models.Feature(feature_name=original_name.strip())
                db.add(db_feature)
                new_features.append(db_feature)
                existing_names.add(normalized)

        if new_features:
            await db.commit()
            for f in new_features:
                await db.refresh(f)

        return existing_features + new_features


    async def get_car_model_by_id(
        self, db: AsyncSession, car_model_id: int
    ) -> Optional[models.CarModel]:
        """
        Get car model by ID with all relationships including car reviews.

        Args:
            db: Database session
            car_model_id: Car model ID

        Returns:
            Car model if found, None otherwise
        """
        result = await db.execute(
            select(models.CarModel)
            .options(
                selectinload(models.CarModel.category),
                selectinload(models.CarModel.fuel),
                selectinload(models.CarModel.capacity),
                selectinload(models.CarModel.features),
                selectinload(models.CarModel.cars).selectinload(models.Car.color),
                selectinload(models.CarModel.cars).selectinload(models.Car.status),
                selectinload(models.CarModel.cars)
                .selectinload(models.Car.reviews)
                .selectinload(models.Review.creator),
            )
            .where(models.CarModel.id == car_model_id)
        )
        return result.scalar_one_or_none()


    async def get_car_model_by_brand_model(
        self, db: AsyncSession, brand: str, model: str
    ) -> Optional[models.CarModel]:
        """
        Get car model by brand and model.

        Args:
            db: Database session
            brand: Car brand
            model: Car model

        Returns:
            Car model if found, None otherwise
        """
        result = await db.execute(
            select(models.CarModel).where(
                models.CarModel.brand == brand, models.CarModel.model == model
            )
        )
        return result.scalar_one_or_none()


    async def get_car_model_details_by_id(
        self, db: AsyncSession, car_model_id: int
    ) -> Optional[models.CarModel]:
        """
        Get car model details by ID.

        Args:
            db: Database session
            car_model_id: Car model ID

        Returns:
            Car model if found, None otherwise
        """
        result = await db.execute(
            select(models.CarModel)
            .options(
                selectinload(models.CarModel.category),
                selectinload(models.CarModel.fuel),
                selectinload(models.CarModel.capacity),
                selectinload(models.CarModel.features),
                selectinload(models.CarModel.cars).selectinload(models.Car.color),
                selectinload(models.CarModel.cars).selectinload(models.Car.status),
                selectinload(models.CarModel.cars)
                .selectinload(models.Car.reviews)
                .selectinload(models.Review.creator),
            )
            .where(models.CarModel.id == car_model_id)
        )
        return result.scalar_one_or_none()


    async def get_all_car_models(self, db: AsyncSession) -> List[models.CarModel]:
        """
        Get all car models.

        Args:
            db: Database session

        Returns:
            List of all car models
        """
        result = await db.execute(
            select(models.CarModel)
            .options(
                selectinload(models.CarModel.category),
                selectinload(models.CarModel.fuel),
                selectinload(models.CarModel.capacity),
                selectinload(models.CarModel.features),
            )
            .order_by(models.CarModel.brand, models.CarModel.model)
        )
        return result.scalars().all()


    async def create_car_model(
        self, db: AsyncSession, car_model_in: schemas.CarModelCreate
    ) -> models.CarModel:
        """
        Create car model.

        Args:
            db: Database session
            car_model_in: Car model data

        Returns:
            Created car model
        """
        features = await self.get_or_create_features(db, car_model_in.features)

        car_model_data = car_model_in.model_dump(exclude={"features"})

        db_car_model = models.CarModel(**car_model_data)
        db_car_model.features = features

        db.add(db_car_model)
        await db.commit()
        await db.refresh(db_car_model)
        return db_car_model


    async def update_car_model(
        self,
        db: AsyncSession,
        db_car_model: models.CarModel,
        car_model_in: schemas.CarModelUpdate,
    ) -> models.CarModel:
        """
        Update car model.

        Args:
            db: Database session
            db_car_model: Car model to update
            car_model_in: Updated car model data

        Returns:
            Updated car model
        """
        update_data = car_model_in.model_dump(exclude_unset=True, exclude={"features"})

        for key, value in update_data.items():
            if value is not None:
                setattr(db_car_model, key, value)

        if car_model_in.features is not None:
            features = await self.get_or_create_features(db, car_model_in.features)
            db_car_model.features = features

        await db.commit()
        await db.refresh(db_car_model)
        return db_car_model


    def _get_car_base_query(self) -> select:
        """
        Get base car query.

        Returns:
            SQLAlchemy select query
        """
        return select(models.Car).options(
            selectinload(models.Car.car_model).selectinload(models.CarModel.category),
            selectinload(models.Car.car_model).selectinload(models.CarModel.fuel),
            selectinload(models.Car.car_model).selectinload(models.CarModel.capacity),
            selectinload(models.Car.color),
            selectinload(models.Car.status),
        )


    def _get_car_with_features_query(self) -> select:
        """
        Get car query with features.

        Returns:
            SQLAlchemy select query
        """
        return self._get_car_base_query().options(
            selectinload(models.Car.car_model).selectinload(models.CarModel.features)
        )


    def _get_car_with_reviews_query(self) -> select:
        """
        Get car query with reviews.

        Returns:
            SQLAlchemy select query
        """
        return self._get_car_base_query().options(
            selectinload(models.Car.reviews).joinedload(models.Review.creator)
        )


    def _get_car_with_all_query(self) -> select:
        """
        Get car query with all details.

        Returns:
            SQLAlchemy select query
        """
        return self._get_car_with_features_query().options(
            selectinload(models.Car.reviews).joinedload(models.Review.creator)
        )


    def _apply_car_filters(self, query: select, params: schemas.CarFilterParams) -> select:
        """
        Apply filters to car query.

        Args:
            query: SQLAlchemy select query
            params: Filter parameters

        Returns:
            Filtered query
        """
        query = query.join(models.CarModel)

        if params.search:
            search_term = f"%{params.search}%"
            query = query.where(
                or_(
                    models.Car.car_no.ilike(search_term),
                    models.CarModel.brand.ilike(search_term),
                    models.CarModel.model.ilike(search_term),
                )
            )
        if params.category_id:
            query = query.where(models.CarModel.category_id == params.category_id)
        if params.fuel_id:
            query = query.where(models.CarModel.fuel_id == params.fuel_id)
        if params.capacity_id:
            query = query.where(models.CarModel.capacity_id == params.capacity_id)
        if params.transmission_type:
            query = query.where(
                models.CarModel.transmission_type == params.transmission_type
            )
        if params.status_id:
            query = query.where(models.Car.status_id == params.status_id)
        if params.car_model_id:
            query = query.where(models.Car.car_model_id == params.car_model_id)

        return query


    async def _get_paginated_cars(
        self,
        db: AsyncSession,
        base_query: select,
        params: schemas.CarFilterParams,
        skip: int,
        limit: int,
    ) -> Tuple[List[models.Car], int]:
        """
        Get paginated cars.

        Args:
            db: Database session
            base_query: Base query
            params: Filter parameters
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            Tuple of car list and total count
        """
        filtered_query = self._apply_car_filters(base_query, params)

        count_query = select(func.count()).select_from(filtered_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        items_query = (
            filtered_query.order_by(models.Car.created_at.desc()).offset(skip).limit(limit)
        )
        items_result = await db.execute(items_query)
        items = items_result.scalars().unique().all()

        return items, total


    async def get_car_by_id(self, db: AsyncSession, car_id: int) -> Optional[models.Car]:
        """
        Get car by ID.

        Args:
            db: Database session
            car_id: Car ID

        Returns:
            Car if found, None otherwise
        """
        query = self._get_car_base_query().where(models.Car.id == car_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()


    async def get_car_with_features_by_id(
        self, db: AsyncSession, car_id: int
    ) -> Optional[models.Car]:
        """
        Get car with features by ID.

        Args:
            db: Database session
            car_id: Car ID

        Returns:
            Car with features if found, None otherwise
        """
        query = self._get_car_with_features_query().where(models.Car.id == car_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()


    async def get_car_with_reviews_by_id(
        self, db: AsyncSession, car_id: int
    ) -> Optional[models.Car]:
        """
        Get car with reviews by ID.

        Args:
            db: Database session
            car_id: Car ID

        Returns:
            Car with reviews if found, None otherwise
        """
        query = self._get_car_with_reviews_query().where(models.Car.id == car_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()


    async def get_car_with_all_by_id(self, db: AsyncSession, car_id: int) -> Optional[models.Car]:
        """
        Get car with all details by ID.

        Args:
            db: Database session
            car_id: Car ID

        Returns:
            Car with all details if found, None otherwise
        """
        query = self._get_car_with_all_query().where(models.Car.id == car_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()


    async def get_all_cars_paginated(
        self, db: AsyncSession, params: schemas.CarFilterParams, skip: int, limit: int
    ) -> Tuple[List[models.Car], int]:
        """
        Get all cars paginated.

        Args:
            db: Database session
            params: Filter parameters
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            Tuple of car list and total count
        """
        return await self._get_paginated_cars(db, self._get_car_base_query(), params, skip, limit)


    async def get_all_cars_with_features_paginated(
        self, db: AsyncSession, params: schemas.CarFilterParams, skip: int, limit: int
    ) -> Tuple[List[models.Car], int]:
        """
        Get all cars with features paginated.

        Args:
            db: Database session
            params: Filter parameters
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            Tuple of car list and total count
        """
        return await self._get_paginated_cars(
            db, self._get_car_with_features_query(), params, skip, limit
        )


    async def get_all_cars_with_reviews_paginated(
        self, db: AsyncSession, params: schemas.CarFilterParams, skip: int, limit: int
    ) -> Tuple[List[models.Car], int]:
        """
        Get all cars with reviews paginated.

        Args:
            db: Database session
            params: Filter parameters
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            Tuple of car list and total count
        """
        return await self._get_paginated_cars(
            db, self._get_car_with_reviews_query(), params, skip, limit
        )


    async def get_all_cars_with_all_paginated(
        self, db: AsyncSession, params: schemas.CarFilterParams, skip: int, limit: int
    ) -> Tuple[List[models.Car], int]:
        """
        Get all cars with all details paginated.

        Args:
            db: Database session
            params: Filter parameters
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            Tuple of car list and total count
        """
        return await self._get_paginated_cars(db, self._get_car_with_all_query(), params, skip, limit)


    async def get_car_by_car_no(self, db: AsyncSession, car_no: str) -> Optional[models.Car]:
        """
        Get car by car number.

        Args:
            db: Database session
            car_no: Car number

        Returns:
            Car if found, None otherwise
        """
        result = await db.execute(select(models.Car).where(models.Car.car_no == car_no))
        return result.scalar_one_or_none()


    async def create_car(self, db: AsyncSession, car_in_db: models.Car) -> models.Car:
        """
        Create car.

        Args:
            db: Database session
            car_in_db: Car object to create

        Returns:
            Created car
        """
        db.add(car_in_db)
        await db.commit()
        await db.refresh(car_in_db)
        return car_in_db


    async def update_car(
        self, db: AsyncSession, db_car: models.Car, car_in: schemas.CarUpdate
    ) -> models.Car:
        """
        Update car.

        Args:
            db: Database session
            db_car: Car to update
            car_in: Updated car data

        Returns:
            Updated car
        """
        update_data = car_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_car, key, value)
        await db.commit()
        await db.refresh(db_car)
        return db_car


    async def partial_update_car(
        self, db: AsyncSession, db_car: models.Car, car_in: schemas.CarUpdate
    ) -> models.Car:
        """
        Partial update car.

        Args:
            db: Database session
            db_car: Car to update
            car_in: Updated car data

        Returns:
            Updated car
        """
        update_data = car_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_car, key, value)
        await db.commit()
        await db.refresh(db_car)
        return db_car


    async def get_all_cars_for_export(
        self, db: AsyncSession, params: schemas.CarFilterParams
    ) -> List[models.Car]:
        """
        Get all cars for export.

        Args:
            db: Database session
            params: Filter parameters

        Returns:
            List of cars
        """
        query = self._apply_car_filters(self._get_car_with_features_query(), params).order_by(
            models.CarModel.brand.asc(),
            models.CarModel.model.asc(),
            models.Car.car_no.asc(),
        )

        result = await db.execute(query)
        return result.scalars().unique().all()


    async def get_cars_due_for_service(
        self, db: AsyncSession, days: int = 10
    ) -> List[models.Car]:
        """
        Get cars due for service.

        Args:
            db: Database session
            days: Number of days to check ahead

        Returns:
            List of cars due for service
        """
        current_time = datetime.utcnow()
        check_date = current_time + timedelta(days=days)

        interval_expr = models.Car.service_frequency_months * text("INTERVAL '1 month'")

        query = self._get_car_with_features_query().where(
            or_(
                models.Car.last_serviced_date.is_(None),
                models.Car.last_serviced_date <= (func.now() - interval_expr),
                and_(
                    models.Car.last_serviced_date.isnot(None),
                    func.date(models.Car.last_serviced_date + interval_expr)
                    <= func.date(check_date),
                ),
            )
        )

        result = await db.execute(query)
        return result.scalars().unique().all()


    async def get_cars_insurance_expiring(
        self, db: AsyncSession, days: int = 10
    ) -> List[models.Car]:
        """
        Get cars with insurance expiring.

        Args:
            db: Database session
            days: Number of days to check ahead

        Returns:
            List of cars with insurance expiring
        """
        current_time = datetime.utcnow()
        check_date = current_time + timedelta(days=days)

        query = self._get_car_with_features_query().where(
            or_(models.Car.insured_till.is_(None), models.Car.insured_till <= check_date)
        )

        result = await db.execute(query)
        return result.scalars().unique().all()


    async def get_cars_pollution_expiring(
        self, db: AsyncSession, days: int = 10
    ) -> List[models.Car]:
        """
        Get cars with pollution certificate expiring.

        Args:
            db: Database session
            days: Number of days to check ahead

        Returns:
            List of cars with pollution certificate expiring
        """
        current_time = datetime.utcnow()
        check_date = current_time + timedelta(days=days)

        query = self._get_car_with_features_query().where(
            or_(
                models.Car.pollution_expiry.is_(None),
                models.Car.pollution_expiry <= check_date,
            )
        )

        result = await db.execute(query)
        return result.scalars().unique().all()


inventory_crud = InventoryCRUD()