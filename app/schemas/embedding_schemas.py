from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class CarEmbeddingBase(BaseModel):
    """
    Schema for car embeddings.
    """
    car_id: int
    content: str
    embedding: Optional[List[float]] = None
    meta_data: Optional[Dict[str, Any]] = None


class CarEmbeddingCreate(CarEmbeddingBase):
    """
    Schema for creating car embeddings.
    """
    pass


class CarEmbeddingUpdate(BaseModel):
    """
    Schema for updating car embeddings.
    """
    content: Optional[str] = None
    embedding: Optional[List[float]] = None
    meta_data: Optional[Dict[str, Any]] = None


class CarEmbeddingResponse(CarEmbeddingBase):
    """
    Schema for car embedding responses.
    """
    id: int
    search_count: int
    last_searched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchEmbeddingResult(BaseModel):
    """
    Schema for batch embedding operation results.
    """
    total_cars: int
    processed: int
    errors: int
    success_rate: float
    failed_car_ids: Optional[List[int]] = None


class DocumentEmbeddingCreate(BaseModel):
    """
    Schema for creating document embeddings.
    """
    doc_type: str
    doc_id: str
    title: Optional[str] = None
    chunk_index: Optional[int] = None
    content: str
    embedding: Optional[List[float]] = None
    meta_data: Optional[Dict[str, Any]] = None


class DocumentEmbeddingResponse(BaseModel):
    """
    Schema for document embedding responses.
    """
    id: int
    doc_type: str
    doc_id: str
    title: Optional[str] = None
    chunk_index: Optional[int] = None
    content: str
    meta_data: Dict[str, Any]
    search_count: int
    last_searched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentBatchResult(BaseModel):
    """
    Schema for document batch embedding operation results.
    """
    total_processed: int
    terms: int
    faq: int
    help: int
    privacy: int
    errors: int
