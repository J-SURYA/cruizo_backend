from fastapi import APIRouter, Depends, Security, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Union
from datetime import datetime

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import inventory_service

router = APIRouter()


@router.get("/colors/{color_id}", response_model=schemas.ColorPublic)
async def get_color(
    color_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    Get color by ID.

    Args:
        color_id: Unique identifier of the color
        db: Database session dependency

    Returns:
        Color details
    """
    return await inventory_service.get_color(db, color_id)


@router.post("/colors", response_model=schemas.ColorPublic)
async def create_color(
    color_in: schemas.ColorCreate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:create"]),
):
    """
    Create new color.

    Args:
        color_in: Color data including name and hex code
        db: Database session dependency

    Returns:
        Newly created color details
    """
    return await inventory_service.create_color(db, color_in)


@router.get("/colors", response_model=List[schemas.ColorPublic])
async def list_colors(
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    List all colors.

    Args:
        db: Database session dependency

    Returns:
        List of all colors in the system
    """
    return await inventory_service.get_all_colors(db)


@router.put("/colors/{color_id}", response_model=schemas.ColorPublic)
async def update_color(
    color_id: int,
    color_in: schemas.ColorUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:update"]),
):
    """
    Update color.

    Args:
        color_id: Unique identifier of the color to update
        color_in: Updated color data
        db: Database session dependency

    Returns:
        Updated color details
    """
    return await inventory_service.update_color(db, color_id, color_in)


@router.delete("/colors/{color_id}", response_model=schemas.Msg)
async def delete_color(
    color_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:delete"]),
):
    """
    Delete color.

    Args:
        color_id: Unique identifier of the color to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await inventory_service.delete_color(db, color_id)
    return schemas.Msg(message="Color deleted successfully")


@router.get("/car-models/{car_model_id}", response_model=schemas.CarModelWithCars)
async def get_car_model(
    car_model_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    Get car model by ID.

    Args:
        car_model_id: Unique identifier of the car model
        db: Database session dependency

    Returns:
        Car model details with associated cars
    """
    return await inventory_service.get_car_model(db, car_model_id)


@router.post("/car-models", response_model=schemas.CarModelWithCars)
async def create_car_model(
    car_model_in: schemas.CarModelCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["cars:create"]),
):
    """
    Create new car model.

    Args:
        car_model_in: Car model data including brand, model name, specifications
        db: Database session dependency
        current_user: Authenticated user with cars:create permission

    Returns:
        Newly created car model with associated cars
    """
    car_model = await inventory_service.create_car_model(db, car_model_in, current_user)
    return await inventory_service.get_car_model(db, car_model.id)


@router.get("/car-models", response_model=schemas.PaginatedCarModelResponse)
async def list_car_models(
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    List all car models.

    Args:
        db: Database session dependency

    Returns:
        Paginated list of all car models
    """
    car_models = await inventory_service.get_all_car_models(db)
    return schemas.PaginatedCarModelResponse(total=len(car_models), items=car_models)


@router.put("/car-models/{car_model_id}", response_model=schemas.CarModelWithCars)
async def update_car_model(
    car_model_id: int,
    car_model_in: schemas.CarModelUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:update"]),
):
    """
    Update car model.

    Args:
        car_model_id: Unique identifier of the car model to update
        car_model_in: Updated car model data
        db: Database session dependency

    Returns:
        Updated car model with associated cars
    """
    await inventory_service.update_car_model(db, car_model_id, car_model_in)
    return await inventory_service.get_car_model(db, car_model_id)


@router.delete("/car-models/{car_model_id}", response_model=schemas.Msg)
async def delete_car_model(
    car_model_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:delete"]),
):
    """
    Delete car model.

    Args:
        car_model_id: Unique identifier of the car model to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await inventory_service.delete_car_model(db, car_model_id)
    return schemas.Msg(message="Car model deleted successfully")


@router.get("/categories/{category_id}", response_model=schemas.CategoryPublic)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    Get category by ID.

    Args:
        category_id: Unique identifier of the category
        db: Database session dependency

    Returns:
        Category details
    """
    return await inventory_service.get_category(db, category_id)


@router.post("/categories", response_model=schemas.CategoryPublic)
async def create_category(
    category_in: schemas.CategoryCreate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:create"]),
):
    """
    Create new category.

    Args:
        category_in: Category data including name
        db: Database session dependency

    Returns:
        Newly created category details
    """
    return await inventory_service.create_category(db, category_in)


@router.get("/categories", response_model=List[schemas.CategoryPublic])
async def list_categories(
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    List all categories.

    Args:
        db: Database session dependency

    Returns:
        List of all categories in the system
    """
    return await inventory_service.get_all_categories(db)


@router.put("/categories/{category_id}", response_model=schemas.CategoryPublic)
async def update_category(
    category_id: int,
    category_in: schemas.CategoryUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:update"]),
):
    """
    Update category.

    Args:
        category_id: Unique identifier of the category to update
        category_in: Updated category data
        db: Database session dependency

    Returns:
        Updated category details
    """
    return await inventory_service.update_category(db, category_id, category_in)


@router.delete("/categories/{category_id}", response_model=schemas.Msg)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:delete"]),
):
    """
    Delete category.

    Args:
        category_id: Unique identifier of the category to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await inventory_service.delete_category(db, category_id)
    return schemas.Msg(message="Category deleted successfully")


@router.get("/fuels/{fuel_id}", response_model=schemas.FuelPublic)
async def get_fuel(
    fuel_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    Get fuel type by ID.

    Args:
        fuel_id: Unique identifier of the fuel type
        db: Database session dependency

    Returns:
        Fuel type details
    """
    return await inventory_service.get_fuel(db, fuel_id)


@router.post("/fuels", response_model=schemas.FuelPublic)
async def create_fuel(
    fuel_in: schemas.FuelCreate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:create"]),
):
    """
    Create new fuel type.

    Args:
        fuel_in: Fuel type data including name
        db: Database session dependency

    Returns:
        Newly created fuel type details
    """
    return await inventory_service.create_fuel(db, fuel_in)


@router.get("/fuels", response_model=List[schemas.FuelPublic])
async def list_fuels(
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    List all fuel types.

    Args:
        db: Database session dependency

    Returns:
        List of all fuel types in the system
    """
    return await inventory_service.get_all_fuels(db)


@router.put("/fuels/{fuel_id}", response_model=schemas.FuelPublic)
async def update_fuel(
    fuel_id: int,
    fuel_in: schemas.FuelUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:update"]),
):
    """
    Update fuel type.

    Args:
        fuel_id: Unique identifier of the fuel type to update
        fuel_in: Updated fuel type data
        db: Database session dependency

    Returns:
        Updated fuel type details
    """
    return await inventory_service.update_fuel(db, fuel_id, fuel_in)


@router.delete("/fuels/{fuel_id}", response_model=schemas.Msg)
async def delete_fuel(
    fuel_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:delete"]),
):
    """
    Delete fuel type.

    Args:
        fuel_id: Unique identifier of the fuel type to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await inventory_service.delete_fuel(db, fuel_id)
    return schemas.Msg(message="Fuel type deleted successfully")


@router.get("/capacities/{capacity_id}", response_model=schemas.CapacityPublic)
async def get_capacity(
    capacity_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    Get capacity by ID.

    Args:
        capacity_id: Unique identifier of the capacity
        db: Database session dependency

    Returns:
        Capacity details
    """
    return await inventory_service.get_capacity(db, capacity_id)


@router.post("/capacities", response_model=schemas.CapacityPublic)
async def create_capacity(
    capacity_in: schemas.CapacityCreate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:create"]),
):
    """
    Create new capacity.

    Args:
        capacity_in: Capacity data including seating capacity
        db: Database session dependency

    Returns:
        Newly created capacity details
    """
    return await inventory_service.create_capacity(db, capacity_in)


@router.get("/capacities", response_model=List[schemas.CapacityPublic])
async def list_capacities(
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    List all capacities.

    Args:
        db: Database session dependency

    Returns:
        List of all capacities in the system
    """
    return await inventory_service.get_all_capacities(db)


@router.put("/capacities/{capacity_id}", response_model=schemas.CapacityPublic)
async def update_capacity(
    capacity_id: int,
    capacity_in: schemas.CapacityUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:update"]),
):
    """
    Update capacity.

    Args:
        capacity_id: Unique identifier of the capacity to update
        capacity_in: Updated capacity data
        db: Database session dependency

    Returns:
        Updated capacity details
    """
    return await inventory_service.update_capacity(db, capacity_id, capacity_in)


@router.delete("/capacities/{capacity_id}", response_model=schemas.Msg)
async def delete_capacity(
    capacity_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:delete"]),
):
    """
    Delete capacity.

    Args:
        capacity_id: Unique identifier of the capacity to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await inventory_service.delete_capacity(db, capacity_id)
    return schemas.Msg(message="Capacity deleted successfully")


@router.get("/features/{feature_id}", response_model=schemas.FeaturePublic)
async def get_feature(
    feature_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    Get feature by ID.

    Args:
        feature_id: Unique identifier of the feature
        db: Database session dependency

    Returns:
        Feature details
    """
    return await inventory_service.get_feature(db, feature_id)


@router.post("/features", response_model=schemas.FeaturePublic)
async def create_feature(
    feature_in: schemas.FeatureCreate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:create"]),
):
    """
    Create new feature.

    Args:
        feature_in: Feature data including name and description
        db: Database session dependency

    Returns:
        Newly created feature details
    """
    return await inventory_service.create_feature(db, feature_in)


@router.get("/features", response_model=List[schemas.FeaturePublic])
async def list_features(
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:read"]),
):
    """
    List all features.

    Args:
        db: Database session dependency

    Returns:
        List of all features in the system
    """
    return await inventory_service.get_all_features(db)


@router.put("/features/{feature_id}", response_model=schemas.FeaturePublic)
async def update_feature(
    feature_id: int,
    feature_in: schemas.FeatureUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:update"]),
):
    """
    Update feature.

    Args:
        feature_id: Unique identifier of the feature to update
        feature_in: Updated feature data
        db: Database session dependency

    Returns:
        Updated feature details
    """
    return await inventory_service.update_feature(db, feature_id, feature_in)


@router.delete("/features/{feature_id}", response_model=schemas.Msg)
async def delete_feature(
    feature_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["lookups:delete"]),
):
    """
    Delete feature.

    Args:
        feature_id: Unique identifier of the feature to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await inventory_service.delete_feature(db, feature_id)
    return schemas.Msg(message="Feature deleted successfully")


@router.get("/cars", response_model=schemas.PaginatedCarSimpleResponse)
async def list_cars(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    fuel_id: Optional[int] = None,
    capacity_id: Optional[int] = None,
    transmission_type: Optional[schemas.TransmissionType] = None,
    status_id: Optional[int] = None,
    car_model_id: Optional[int] = None,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    List cars with pagination and filtering.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for car number or model
        category_id: Filter by category
        fuel_id: Filter by fuel type
        capacity_id: Filter by capacity
        transmission_type: Filter by transmission type
        status_id: Filter by status
        car_model_id: Filter by car model
        db: Database session dependency

    Returns:
        Paginated list of cars with basic details
    """
    filters = schemas.CarFilterParams(
        search=search,
        category_id=category_id,
        fuel_id=fuel_id,
        capacity_id=capacity_id,
        transmission_type=transmission_type,
        status_id=status_id,
        car_model_id=car_model_id,
    )
    return await inventory_service.list_cars(db, filters, skip, limit)


@router.get(
    "/cars/with-features", response_model=schemas.PaginatedCarWithFeaturesResponse
)
async def list_cars_with_features(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    fuel_id: Optional[int] = None,
    capacity_id: Optional[int] = None,
    transmission_type: Optional[schemas.TransmissionType] = None,
    status_id: Optional[int] = None,
    car_model_id: Optional[int] = None,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    List cars with features included.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for car number or model
        category_id: Filter by category
        fuel_id: Filter by fuel type
        capacity_id: Filter by capacity
        transmission_type: Filter by transmission type
        status_id: Filter by status
        car_model_id: Filter by car model
        db: Database session dependency

    Returns:
        Paginated list of cars with feature details
    """
    filters = schemas.CarFilterParams(
        search=search,
        category_id=category_id,
        fuel_id=fuel_id,
        capacity_id=capacity_id,
        transmission_type=transmission_type,
        status_id=status_id,
        car_model_id=car_model_id,
    )
    return await inventory_service.list_cars_with_features(db, filters, skip, limit)


@router.get(
    "/cars/with-reviews", response_model=schemas.PaginatedCarWithReviewsResponse
)
async def list_cars_with_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    fuel_id: Optional[int] = None,
    capacity_id: Optional[int] = None,
    transmission_type: Optional[schemas.TransmissionType] = None,
    status_id: Optional[int] = None,
    car_model_id: Optional[int] = None,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read", "reviews:read"]),
):
    """
    List cars with reviews included.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for car number or model
        category_id: Filter by category
        fuel_id: Filter by fuel type
        capacity_id: Filter by capacity
        transmission_type: Filter by transmission type
        status_id: Filter by status
        car_model_id: Filter by car model
        db: Database session dependency

    Returns:
        Paginated list of cars with review details
    """
    filters = schemas.CarFilterParams(
        search=search,
        category_id=category_id,
        fuel_id=fuel_id,
        capacity_id=capacity_id,
        transmission_type=transmission_type,
        status_id=status_id,
        car_model_id=car_model_id,
    )
    return await inventory_service.list_cars_with_reviews(db, filters, skip, limit)


@router.get(
    "/cars/with-all-details", response_model=schemas.PaginatedCarCompleteResponse
)
async def list_cars_with_features_and_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    fuel_id: Optional[int] = None,
    capacity_id: Optional[int] = None,
    transmission_type: Optional[schemas.TransmissionType] = None,
    status_id: Optional[int] = None,
    car_model_id: Optional[int] = None,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read", "reviews:read"]),
):
    """
    List cars with all details including features and reviews.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for car number or model
        category_id: Filter by category
        fuel_id: Filter by fuel type
        capacity_id: Filter by capacity
        transmission_type: Filter by transmission type
        status_id: Filter by status
        car_model_id: Filter by car model
        db: Database session dependency

    Returns:
        Paginated list of cars with complete details
    """
    filters = schemas.CarFilterParams(
        search=search,
        category_id=category_id,
        fuel_id=fuel_id,
        capacity_id=capacity_id,
        transmission_type=transmission_type,
        status_id=status_id,
        car_model_id=car_model_id,
    )
    return await inventory_service.list_cars_with_features_and_reviews(
        db, filters, skip, limit
    )


@router.get("/cars/import-template", response_class=StreamingResponse)
async def get_import_template(
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    Get car import template CSV file.

    Args:
        None

    Returns:
        Streaming CSV file with template headers for bulk car import
    """
    return await inventory_service.get_import_template()


@router.post("/cars/import", response_model=schemas.Msg)
async def import_cars(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["cars:create"]),
):
    """
    Import cars from CSV file.

    Args:
        file: CSV file containing car data
        db: Database session dependency
        current_user: Authenticated user with cars:create permission

    Returns:
        Success message with import statistics
    """
    return await inventory_service.import_cars(db, file, current_user)


@router.get("/cars/export", response_class=StreamingResponse)
async def export_cars(
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    fuel_id: Optional[int] = None,
    capacity_id: Optional[int] = None,
    transmission_type: Optional[schemas.TransmissionType] = None,
    status_id: Optional[int] = None,
    car_model_id: Optional[int] = None,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    Export cars to Excel file.

    Args:
        search: Search term for car number or model
        category_id: Filter by category
        fuel_id: Filter by fuel type
        capacity_id: Filter by capacity
        transmission_type: Filter by transmission type
        status_id: Filter by status
        car_model_id: Filter by car model
        db: Database session dependency

    Returns:
        Streaming Excel file with car data
    """
    filters = schemas.CarFilterParams(
        search=search,
        category_id=category_id,
        fuel_id=fuel_id,
        capacity_id=capacity_id,
        transmission_type=transmission_type,
        status_id=status_id,
        car_model_id=car_model_id,
    )
    return await inventory_service.export_cars(db, filters)


@router.get("/cars/for-service", response_model=List[schemas.CarWithFeatures])
async def get_cars_for_service(
    days: int = Query(10, ge=1, le=365, description="Days before expiry to check"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    Get cars due for service within specified days.

    Args:
        days: Number of days to check before service due date
        db: Database session dependency

    Returns:
        List of cars that need service soon
    """
    return await inventory_service.get_cars_due_for_service(db, days)


@router.get("/cars/insurance-expiring", response_model=List[schemas.CarWithFeatures])
async def get_cars_insurance_expiring(
    days: int = Query(10, ge=1, le=365, description="Days before expiry to check"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    Get cars with insurance expiring within specified days.

    Args:
        days: Number of days to check before insurance expiry
        db: Database session dependency

    Returns:
        List of cars with insurance expiring soon
    """
    return await inventory_service.get_cars_insurance_expiring(db, days)


@router.get("/cars/pollution-expiring", response_model=List[schemas.CarWithFeatures])
async def get_cars_pollution_expiring(
    days: int = Query(10, ge=1, le=365, description="Days before expiry to check"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    Get cars with pollution certificate expiring within specified days.

    Args:
        days: Number of days to check before pollution certificate expiry
        db: Database session dependency

    Returns:
        List of cars with pollution certificate expiring soon
    """
    return await inventory_service.get_cars_pollution_expiring(db, days)


@router.get("/cars/{car_id}", response_model=schemas.CarComplete)
async def get_car(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    Get car by ID.

    Args:
        car_id: ID of the car to retrieve
        db: Database session dependency

    Returns:
        Complete car details
    """
    return await inventory_service.get_car(db, car_id)


@router.get("/cars/{car_id}/features", response_model=schemas.CarWithFeatures)
async def get_car_with_features(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read"]),
):
    """
    Get car with features by ID.

    Args:
        car_id: ID of the car to retrieve
        db: Database session dependency

    Returns:
        Car details with associated features
    """
    return await inventory_service.get_car_with_features(db, car_id)


@router.get("/cars/{car_id}/reviews", response_model=schemas.CarWithReviews)
async def get_car_with_reviews(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read", "reviews:read"]),
):
    """
    Get car with reviews by ID.

    Args:
        car_id: ID of the car to retrieve
        db: Database session dependency

    Returns:
        Car details with all reviews
    """
    return await inventory_service.get_car_with_reviews(db, car_id)


@router.get("/cars/{car_id}/all-details", response_model=schemas.CarComplete)
async def get_car_with_features_and_reviews(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:read", "reviews:read"]),
):
    """
    Get car with all details by ID.

    Args:
        car_id: ID of the car to retrieve
        db: Database session dependency

    Returns:
        Complete car details with features and reviews
    """
    return await inventory_service.get_car_with_features_and_reviews(db, car_id)


@router.post("/cars", response_model=schemas.CarWithFeatures)
async def create_car(
    car_no: str = Form(...),
    car_model_id: int = Form(...),
    color_id: int = Form(...),
    manufacture_year: int = Form(...),
    status_id: int = Form(...),
    last_serviced_date: datetime = Form(...),
    service_frequency_months: int = Form(...),
    insured_till: datetime = Form(...),
    pollution_expiry: datetime = Form(...),
    images: List[UploadFile] = File(
        None, description="0-5 car images (JPG/PNG, max 2MB each)"
    ),
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["cars:create"]),
):
    """
    Create new car with optional images.

    Args:
        car_no: Car registration number
        car_model_id: ID of the car model
        color_id: ID of the car color
        manufacture_year: Year of manufacture
        status_id: ID of the car status
        last_serviced_date: Date of last service
        service_frequency_months: Service interval in months
        insured_till: Insurance expiry date
        pollution_expiry: Pollution certificate expiry date
        images: Optional list of car images (0-5 images)
        db: Database session dependency
        current_user: Authenticated user with cars:create permission

    Returns:
        Newly created car with features
    """
    car_in = schemas.CarCreate(
        car_no=car_no,
        car_model_id=car_model_id,
        color_id=color_id,
        manufacture_year=manufacture_year,
        status_id=status_id,
        last_serviced_date=last_serviced_date,
        service_frequency_months=service_frequency_months,
        insured_till=insured_till,
        pollution_expiry=pollution_expiry,
    )
    car = await inventory_service.create_car(db, car_in, current_user, images)
    return await inventory_service.get_car_with_features(db, car.id)


@router.put("/cars/{car_id}", response_model=schemas.CarWithFeatures)
async def update_car(
    car_id: int,
    car_no: Optional[str] = Form(None),
    car_model_id: Union[int, str, None] = Form(None),
    color_id: Union[int, str, None] = Form(None),
    manufacture_year: Union[int, str, None] = Form(None),
    status_id: Union[int, str, None] = Form(None),
    last_serviced_date: Union[datetime, str, None] = Form(None),
    service_frequency_months: Union[int, str, None] = Form(None),
    insured_till: Union[datetime, str, None] = Form(None),
    pollution_expiry: Union[datetime, str, None] = Form(None),
    new_images: Optional[List[UploadFile]] = File(
        None, description="New images to add (max total 5)"
    ),
    delete_image_urls: Optional[str] = Form(
        None, description="Comma-separated URLs to delete"
    ),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:update"]),
):
    """
    Update car with optional image management.

    Args:
        car_id: ID of the car to update
        car_no: Updated car registration number
        car_model_id: Updated car model ID
        color_id: Updated color ID
        manufacture_year: Updated manufacture year
        status_id: Updated status ID
        last_serviced_date: Updated last service date
        service_frequency_months: Updated service interval
        insured_till: Updated insurance expiry date
        pollution_expiry: Updated pollution certificate expiry
        new_images: New images to add
        delete_image_urls: Comma-separated URLs of images to delete
        db: Database session dependency

    Returns:
        Updated car with features
    """

    def parse_int(value: Union[int, str, None]) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def parse_datetime(value: Union[datetime, str, None]) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    car_in = schemas.CarUpdate(
        car_no=car_no if car_no else None,
        car_model_id=parse_int(car_model_id),
        color_id=parse_int(color_id),
        manufacture_year=parse_int(manufacture_year),
        status_id=parse_int(status_id),
        last_serviced_date=parse_datetime(last_serviced_date),
        service_frequency_months=parse_int(service_frequency_months),
        insured_till=parse_datetime(insured_till),
        pollution_expiry=parse_datetime(pollution_expiry),
    )
    car = await inventory_service.update_car(
        db, car_id, car_in, new_images, delete_image_urls
    )
    return await inventory_service.get_car_with_features(db, car.id)


@router.delete("/cars/{car_id}", response_model=schemas.Msg)
async def delete_car(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:delete"]),
):
    """
    Delete car.

    Args:
        car_id: ID of the car to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await inventory_service.delete_car(db, car_id)
    return schemas.Msg(message="Car deleted successfully")


@router.patch("/cars/{car_id}/deactivate", response_model=schemas.Msg)
async def deactivate_car(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:update"]),
):
    """
    Deactivate car by setting status to INACTIVE.

    Args:
        car_id: ID of the car to deactivate
        db: Database session dependency

    Returns:
        Success message confirming car deactivation
    """
    return await inventory_service.deactivate_car(db, car_id)


@router.patch("/cars/{car_id}/activate", response_model=schemas.Msg)
async def activate_car(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:update"]),
):
    """
    Activate car by setting status to ACTIVE.

    Args:
        car_id: ID of the car to activate
        db: Database session dependency

    Returns:
        Success message confirming car activation
    """
    return await inventory_service.activate_car(db, car_id)


@router.post("/cars/{car_id}/service", response_model=schemas.CarWithFeatures)
async def update_car_service(
    car_id: int,
    service_data: schemas.CarServiceUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:update"]),
):
    """
    Update car service information.

    Args:
        car_id: ID of the car to update
        service_data: Service information including date and frequency
        db: Database session dependency

    Returns:
        Updated car with features
    """
    return await inventory_service.update_car_service(db, car_id, service_data)


@router.post("/cars/{car_id}/update-insurance", response_model=schemas.CarWithFeatures)
async def update_car_insurance(
    car_id: int,
    insurance_data: schemas.CarInsuranceUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:update"]),
):
    """
    Update car insurance information.

    Args:
        car_id: ID of the car to update
        insurance_data: Insurance information including expiry date
        db: Database session dependency

    Returns:
        Updated car with features
    """
    return await inventory_service.update_car_insurance(db, car_id, insurance_data)


@router.post("/cars/{car_id}/update-pollution", response_model=schemas.CarWithFeatures)
async def update_car_pollution(
    car_id: int,
    pollution_data: schemas.CarPollutionUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["cars:update"]),
):
    """
    Update car pollution certificate information.

    Args:
        car_id: ID of the car to update
        pollution_data: Pollution certificate information including expiry date
        db: Database session dependency

    Returns:
        Updated car with features
    """
    return await inventory_service.update_car_pollution(db, car_id, pollution_data)


@router.get(
    "/customer/car-models", response_model=schemas.PaginatedCarModelPublicResponse
)
async def get_car_models_for_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    fuel_id: Optional[int] = None,
    capacity_id: Optional[int] = None,
    transmission_type: Optional[schemas.TransmissionType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    delivery_lat: Optional[float] = Query(None, ge=-90, le=90),
    delivery_lon: Optional[float] = Query(None, ge=-180, le=180),
    pickup_lat: Optional[float] = Query(None, ge=-90, le=90),
    pickup_lon: Optional[float] = Query(None, ge=-180, le=180),
    sort_by: str = Query(
        "dynamic_rental_price",
        description="Sort by dynamic_rental_price or kilometer_limit_per_hr",
    ),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:create"]),
):
    """
    Get car models for customers with optional availability checking.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for car model
        category_id: Filter by category
        fuel_id: Filter by fuel type
        capacity_id: Filter by capacity
        transmission_type: Filter by transmission type
        start_date: Trip start date for availability check
        end_date: Trip end date for availability check
        delivery_lat: Delivery location latitude
        delivery_lon: Delivery location longitude
        pickup_lat: Pickup location latitude
        pickup_lon: Pickup location longitude
        sort_by: Field to sort results by
        sort_order: Sort direction (asc or desc)
        db: Database session dependency

    Returns:
        Paginated list of car models with availability information
    """

    # Build filters
    filters = schemas.CarModelFilterParams(
        search=search,
        category_id=category_id,
        fuel_id=fuel_id,
        capacity_id=capacity_id,
        transmission_type=transmission_type,
    )

    # Build trip details if provided
    trip_details = None
    if start_date and end_date:
        trip_details = schemas.TripDetailsInput(
            start_date=start_date, end_date=end_date
        )

    return await inventory_service.get_car_models_for_customers(
        db=db,
        trip_details=trip_details,
        filters=filters,
        delivery_lat=delivery_lat,
        delivery_lon=delivery_lon,
        pickup_lat=pickup_lat,
        pickup_lon=pickup_lon,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/customer/car-models/{car_model_id}",
    response_model=schemas.CarModelDetailsPublicForCustomer,
)
async def get_car_model_details_for_customer(
    car_model_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    delivery_lat: Optional[float] = Query(None, ge=-90, le=90),
    delivery_lon: Optional[float] = Query(None, ge=-180, le=180),
    pickup_lat: Optional[float] = Query(None, ge=-90, le=90),
    pickup_lon: Optional[float] = Query(None, ge=-180, le=180),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:create"]),
):
    """
    Get car model details for customer with optional availability checking.

    Args:
        car_model_id: ID of the car model
        start_date: Trip start date for availability check
        end_date: Trip end date for availability check
        delivery_lat: Delivery location latitude
        delivery_lon: Delivery location longitude
        pickup_lat: Pickup location latitude
        pickup_lon: Pickup location longitude
        db: Database session dependency

    Returns:
        Detailed car model information with availability status
    """

    # Build trip details if provided
    trip_details = None
    if start_date and end_date:
        trip_details = schemas.TripDetailsInput(
            start_date=start_date, end_date=end_date
        )

    return await inventory_service.get_car_model_details_for_customer(
        db=db,
        car_model_id=car_model_id,
        trip_details=trip_details,
        delivery_lat=delivery_lat,
        delivery_lon=delivery_lon,
        pickup_lat=pickup_lat,
        pickup_lon=pickup_lon,
    )


@router.get(
    "/customer/cars/{car_id}/available-slots",
    response_model=schemas.CarAvailabilityResponse,
)
async def get_available_slots_for_car(
    car_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["bookings:create"]),
):
    """
    Get available time slots for specific car.

    Args:
        car_id: ID of the car
        db: Database session dependency

    Returns:
        Car availability information with time slots
    """
    return await inventory_service.get_available_slots_for_car(db, car_id)
