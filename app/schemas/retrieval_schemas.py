from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


from .filter_schemas import SearchFilter


class SearchIntent(BaseModel):
    """
    Schema for search intent with type, confidence, and optional percentages for hybrid intent.
    """
    intent_type: Literal["inventory", "documents", "hybrid"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    car_percentage: Optional[float] = Field(None, ge=0.0, le=1.0)
    document_percentage: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator("car_percentage", "document_percentage")
    @classmethod
    def validate_percentages(cls, v, info):
        intent_type = info.data.get("intent_type")

        if intent_type == "hybrid":
            if v is None:
                raise ValueError("Percentages required for hybrid intent")

            if not (0 <= v <= 1):
                raise ValueError("Percentage must be between 0 and 1")

        return v

    @model_validator(mode="after")
    def validate_total_percentage(self):
        if (
            self.intent_type == "hybrid"
            and self.car_percentage is not None
            and self.document_percentage is not None
        ):
            total = self.car_percentage + self.document_percentage
            if total > 1:
                raise ValueError("Total percentage cannot exceed 1.0")

        return self


class SearchQuery(BaseModel):
    """
    Schema for search query with text, embedding, intent, filters, and parameters.
    """
    text_query: str
    query_embedding: List[float]
    intent: SearchIntent
    filters: Optional[SearchFilter] = None
    top_k: int = Field(default=10, ge=1, le=100)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    class Config:
        model_config = ConfigDict(from_attributes=True)


class SearchResultItem(BaseModel):
    """
    Schema for individual search result item with various attributes.
    """
    id: int
    score: float = Field(..., ge=0.0, le=1.0)
    content: str
    metadata: Dict[str, Any]
    doc_type: str
    source: str

    car_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    price_per_hour: Optional[float] = None
    price_per_day: Optional[float] = None

    document_title: Optional[str] = None
    chunk_index: Optional[int] = None

    class Config:
        model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    """
    Schema for search response with query details, intent, results, and filters applied.
    """
    query_id: Optional[str] = None
    query_text: str
    intent: SearchIntent
    total_results: int
    results: List[SearchResultItem]
    filters_applied: Dict[str, Any]

    class Config:
        model_config = ConfigDict(from_attributes=True)


class BookingHistoryRequest(BaseModel):
    """
    Schema for booking history request with user ID, limits, and filters.
    """
    user_id: str
    limit: int = Field(default=10, ge=1, le=50)
    recent_bookings_count: int = Field(default=5, ge=1, le=20)
    exclude_current_bookings: bool = True
    additional_filters: Optional[SearchFilter] = None

    class Config:
        model_config = ConfigDict(from_attributes=True)


class BookingHistoryResponse(BaseModel):
    """
    Schema for booking history response with user ID and list of booked car IDs.
    """
    user_id: str
    recommendations: List[SearchResultItem]
    recent_booked_cars: List[int]
    recommendation_reason: str
    total_recommendations: int

    class Config:
        model_config = ConfigDict(from_attributes=True)
