from pydantic import BaseModel, Field, ConfigDict
from fastapi import Query
from typing import List, Generic, TypeVar


from app.models.enums import StatusEnum


T = TypeVar("T")


class BaseSchema(BaseModel):
    """
    Schema with configuration to allow ORM mode for database models.
    """
    model_config = ConfigDict(from_attributes=True)


class Msg(BaseModel):
    """
    Schema for generic message responses.
    """
    message: str = Field(..., description="Response message content")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Schema for paginated responses with total count and items.
    """
    total: int = Field(..., description="Total number of records matching filters")
    items: List[T] = Field(..., description="List of paginated records")
    skip: int = Field(..., description="Number of records skipped for pagination")
    limit: int = Field(..., description="Maximum number of records returned")


class PaginationParams:
    """
    Schema for pagination parameters in requests.
    """
    def __init__(
        self,
        skip: int = Query(
            0, ge=0, description="Number of records to skip for pagination"
        ),
        limit: int = Query(
            20, ge=1, le=100, description="Maximum number of records to return per page"
        ),
    ):
        self.skip = skip
        self.limit = limit


class UserSimplePublic(BaseModel):
    """
    Schema for simple public user information.
    """
    id: str = Field(..., description="User unique identifier")
    name: str = Field(..., description="User's display name")
    model_config = ConfigDict(from_attributes=True)


class StatusPublic(BaseSchema):
    """
    Schema for status information.
    """
    id: int = Field(..., description="Status unique identifier")
    name: StatusEnum = Field(..., description="Status enum value")
