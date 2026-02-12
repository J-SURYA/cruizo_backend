from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


from app.models.enums import TransmissionType


class ColorPublic(BaseModel):
    """
    Schema for car color details.
    """
    id: int
    color_name: str
    model_config = ConfigDict(from_attributes=True)


class CategoryPublic(BaseModel):
    """
    Schema for car category details.
    """
    id: int
    category_name: str
    model_config = ConfigDict(from_attributes=True)


class FuelPublic(BaseModel):
    """
    Schema for car fuel type details.
    """
    id: int
    fuel_name: str
    model_config = ConfigDict(from_attributes=True)


class CapacityPublic(BaseModel):
    """
    Schema for car capacity details.
    """
    id: int
    capacity_value: int
    model_config = ConfigDict(from_attributes=True)


class CarModelDropdown(BaseModel):
    """
    Schema for car model dropdown list (minimal fields).
    """
    id: int
    brand: str
    model: str
    model_config = ConfigDict(from_attributes=True)


class FeaturePublic(BaseModel):
    """
    Schema for car feature details.
    """
    id: int
    feature_name: str
    model_config = ConfigDict(from_attributes=True)


class StatusPublic(BaseModel):
    """
    Schema for car status details.
    """
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class ReviewPublic(BaseModel):
    """
    Schema for car review details.
    """
    id: int
    rating: int
    remarks: Optional[str] = None
    created_by: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CarModelBase(BaseModel):
    """
    Schema for base car model details.
    """
    brand: str
    model: str
    transmission_type: TransmissionType
    mileage: int
    rental_per_hr: Decimal
    dynamic_rental_price: Decimal
    kilometer_limit_per_hr: int = 50


class CarModelCreate(CarModelBase):
    """
    Schema for creating a new car model. All fields are required.
    """
    category_id: int
    fuel_id: int
    capacity_id: int
    features: List[str] = []


class CarModelUpdate(BaseModel):
    """
    Schema for updating a car model. All fields are optional (partial update).
    """
    brand: Optional[str] = None
    model: Optional[str] = None
    category_id: Optional[int] = None
    fuel_id: Optional[int] = None
    capacity_id: Optional[int] = None
    transmission_type: Optional[TransmissionType] = None
    mileage: Optional[int] = None
    rental_per_hr: Optional[Decimal] = None
    dynamic_rental_price: Optional[Decimal] = None
    kilometer_limit_per_hr: Optional[int] = None
    features: Optional[List[str]] = None


class CarComplete(BaseModel):
    """
    Schema for complete car details including nested relationships and reviews.
    """
    # Car fields
    id: int
    car_no: str
    manufacture_year: int
    image_urls: List[str]
    last_serviced_date: Optional[datetime] = None
    service_frequency_months: int = 3
    insured_till: Optional[datetime] = None
    pollution_expiry: Optional[datetime] = None
    created_at: datetime

    # Nested relationships
    color: ColorPublic
    status: StatusPublic

    # Car Model fields (fully nested)
    brand: str
    model: str
    category: CategoryPublic
    fuel: FuelPublic
    capacity: CapacityPublic
    transmission_type: TransmissionType
    mileage: int
    rental_per_hr: Decimal
    dynamic_rental_price: Decimal
    kilometer_limit_per_hr: int
    features: List[FeaturePublic]

    # Reviews
    reviews: List[ReviewPublic] = []

    model_config = ConfigDict(from_attributes=True)


class CarModelWithCars(BaseModel):
    """
    Schema for car model details including all cars of that model with complete data.
    """
    # Car Model fields
    id: int
    brand: str
    model: str
    transmission_type: TransmissionType
    mileage: int
    rental_per_hr: Decimal
    dynamic_rental_price: Decimal
    kilometer_limit_per_hr: int
    created_at: datetime

    # Nested relationships
    category: CategoryPublic
    fuel: FuelPublic
    capacity: CapacityPublic
    features: List[FeaturePublic]

    # All cars for this model (with complete data including reviews)
    cars: List[CarComplete]

    model_config = ConfigDict(from_attributes=True)


class CarSimple(BaseModel):
    """
    Schema for simple car details.
    """
    id: int
    car_no: str
    color: ColorPublic
    status: StatusPublic
    manufacture_year: int
    image_urls: List[str]
    model_config = ConfigDict(from_attributes=True)


class CarWithFeatures(BaseModel):
    """
    Schema for car details including features.
    """
    id: int
    car_no: str
    color: ColorPublic
    status: StatusPublic
    manufacture_year: int
    image_urls: List[str]
    brand: str
    model: str
    category: CategoryPublic
    fuel: FuelPublic
    capacity: CapacityPublic
    transmission_type: TransmissionType
    mileage: int
    rental_per_hr: Decimal
    dynamic_rental_price: Decimal
    kilometer_limit_per_hr: int
    features: List[FeaturePublic]
    model_config = ConfigDict(from_attributes=True)


class CarWithReviews(BaseModel):
    """
    Schema for car details including reviews.
    """
    id: int
    car_no: str
    color: ColorPublic
    status: StatusPublic
    manufacture_year: int
    image_urls: List[str]
    brand: str
    model: str
    category: CategoryPublic
    fuel: FuelPublic
    capacity: CapacityPublic
    transmission_type: TransmissionType
    mileage: int
    rental_per_hr: Decimal
    dynamic_rental_price: Decimal
    kilometer_limit_per_hr: int
    reviews: List[ReviewPublic]
    model_config = ConfigDict(from_attributes=True)


class CarCreate(BaseModel):
    """
    Schema for creating a new car. All fields are required.
    """
    car_no: str
    car_model_id: int
    color_id: int
    manufacture_year: int
    status_id: int
    last_serviced_date: datetime
    service_frequency_months: int
    insured_till: datetime
    pollution_expiry: datetime


class CarUpdate(BaseModel):
    """
    Schema for updating a car. All fields are optional (partial update).
    """
    car_no: Optional[str] = None
    car_model_id: Optional[int] = None
    color_id: Optional[int] = None
    manufacture_year: Optional[int] = None
    status_id: Optional[int] = None
    last_serviced_date: Optional[datetime] = None
    service_frequency_months: Optional[int] = None
    insured_till: Optional[datetime] = None
    pollution_expiry: Optional[datetime] = None
    image_urls: Optional[List[str]] = None


class PaginatedCarSimpleResponse(BaseModel):
    """
    Schema for paginated response of simple car details.
    """
    total: int
    items: List[CarSimple]


class PaginatedCarWithFeaturesResponse(BaseModel):
    """
    Schema for paginated response of car details including features.
    """
    total: int
    items: List[CarWithFeatures]


class PaginatedCarWithReviewsResponse(BaseModel):
    """
    Schema for paginated response of car details including reviews.
    """
    total: int
    items: List[CarWithReviews]


class PaginatedCarCompleteResponse(BaseModel):
    """
    Schema for paginated response of complete car details.
    """
    total: int
    items: List[CarComplete]


class PaginatedCarModelResponse(BaseModel):
    """
    Schema for paginated response of car model details including cars.
    """
    total: int
    items: List[CarModelWithCars]


class CarFilterParams(BaseModel):
    """
    Schema for filter parameters when querying cars.
    """
    search: Optional[str] = None
    category_id: Optional[int] = None
    fuel_id: Optional[int] = None
    capacity_id: Optional[int] = None
    transmission_type: Optional[TransmissionType] = None
    status_id: Optional[int] = None
    car_model_id: Optional[int] = None


class CarModelFilterParams(BaseModel):
    """
    Schema for filter parameters when querying car models.
    """
    search: Optional[str] = None
    category_id: Optional[int] = None
    fuel_id: Optional[int] = None
    capacity_id: Optional[int] = None
    transmission_type: Optional[TransmissionType] = None


class CarDetailsPublicForCustomer(BaseModel):
    """
    Schema for car details including reviews for customer view.
    """
    id: int
    car_no: str
    manufacture_year: int
    image_urls: List[str]
    last_serviced_date: Optional[datetime] = None
    service_frequency_months: int = 3
    insured_till: Optional[datetime] = None
    pollution_expiry: Optional[datetime] = None
    reviews: List[ReviewPublic]
    created_at: datetime
    color: ColorPublic
    status: StatusPublic
    model_config = ConfigDict(from_attributes=True)


class CarModelDetailsPublicForCustomer(BaseModel):
    """
    Schema for car model details including cars for customer view.
    """
    id: int
    brand: str
    model: str
    category: CategoryPublic
    fuel: FuelPublic
    capacity: CapacityPublic
    transmission_type: TransmissionType
    mileage: int
    rental_per_hr: Decimal
    dynamic_rental_price: Decimal
    kilometer_limit_per_hr: int
    features: List[FeaturePublic]
    cars: List[CarDetailsPublicForCustomer]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CarPublicForCustomer(BaseModel):
    """
    Schema for car details for customer's view.
    """
    id: int
    car_no: str
    manufacture_year: int
    image_urls: List[str]
    last_serviced_date: Optional[datetime] = None
    service_frequency_months: int = 3
    insured_till: Optional[datetime] = None
    pollution_expiry: Optional[datetime] = None
    created_at: datetime
    color: ColorPublic
    status: StatusPublic
    model_config = ConfigDict(from_attributes=True)


class CarModelPublicForCustomer(BaseModel):
    """
    Schema for car model details for customer's view.
    """
    id: int
    brand: str
    model: str
    category: CategoryPublic
    fuel: FuelPublic
    capacity: CapacityPublic
    transmission_type: TransmissionType
    mileage: int
    rental_per_hr: Decimal
    dynamic_rental_price: Decimal
    kilometer_limit_per_hr: int
    features: List[FeaturePublic]
    cars: List[CarPublicForCustomer]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaginatedCarModelPublicResponse(BaseModel):
    """
    Schema for paginated response of car model details for customer's view.
    """
    total: int
    items: List[CarModelPublicForCustomer]
    skip: int
    limit: int


class TripDetailsInput(BaseModel):
    """
    Schema for input trip details to check car availability.
    """
    start_date: datetime
    end_date: datetime


class CarAvailabilityResponse(BaseModel):
    """
    Schema for car availability response including available slots and car details.
    """
    car_id: int
    car_details: Dict[str, Any]
    available_slots: List[Dict[str, Any]]
    max_advance_days: int
    model_config = ConfigDict(from_attributes=True)


class CarServiceUpdate(BaseModel):
    """
    Schema for updating car service details.
    """
    last_serviced_date: datetime
    service_frequency_months: Optional[int] = None


class CarInsuranceUpdate(BaseModel):
    """
    Schema for updating car insurance details.
    """
    insured_till: datetime


class CarPollutionUpdate(BaseModel):
    """
    Schema for updating car pollution expiry details.
    """
    pollution_expiry: datetime


class Msg(BaseModel):
    """
    Schema for generic message response.
    """
    message: str


class ColorCreate(BaseModel):
    """
    Schema for creating a new car color.
    """
    color_name: str


class ColorUpdate(BaseModel):
    """
    Schema for updating a car color.
    """
    color_name: str


class CategoryCreate(BaseModel):
    """
    Schema for creating a new car category.
    """
    category_name: str


class CategoryUpdate(BaseModel):
    """
    Schema for updating a car category.
    """
    category_name: str


class FuelCreate(BaseModel):
    """
    Schema for creating a new car fuel type.
    """
    fuel_name: str


class FuelUpdate(BaseModel):
    """
    Schema for updating a car fuel type.
    """
    fuel_name: str


class CapacityCreate(BaseModel):
    """
    Schema for creating a new car capacity.
    """
    capacity_value: int


class CapacityUpdate(BaseModel):
    """
    Schema for updating a car capacity.
    """
    capacity_value: int


class FeatureCreate(BaseModel):
    """
    Schema for creating a new car feature.
    """
    feature_name: str


class FeatureUpdate(BaseModel):
    """
    Schema for updating a car feature.
    """
    feature_name: str
