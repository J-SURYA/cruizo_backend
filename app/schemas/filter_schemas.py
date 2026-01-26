from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class SearchFilter(BaseModel):
    """
    Schema for car search criteria extracted from user query.
    """

    category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None

    max_price_per_hour: Optional[float] = None
    min_price_per_hour: Optional[float] = None
    max_price_per_day: Optional[float] = None
    min_price_per_day: Optional[float] = None
    min_seats: Optional[int] = None
    max_seats: Optional[int] = None

    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    color: Optional[str] = None

    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_mileage: Optional[float] = None
    max_mileage: Optional[float] = None

    status: Optional[str] = None

    days_since_last_service: Optional[int] = None
    insurance_valid: Optional[bool] = None
    pollution_valid: Optional[bool] = None

    min_avg_rating: Optional[float] = None
    min_total_reviews: Optional[int] = None
    features: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None

    doc_types: Optional[List[str]] = None

    class Config:
        model_config = ConfigDict(from_attributes=True)
