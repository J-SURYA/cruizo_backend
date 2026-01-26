from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import List, Optional
from datetime import datetime


from .utility_schemas import StatusPublic


class QueryBase(BaseModel):
    """
    Schema for customer support query information.
    """
    name: str = Field(..., max_length=255, description="Customer's full name")
    phone: str = Field(..., max_length=20, description="Customer's phone number")
    email: EmailStr = Field(..., description="Customer's email address")
    message: str = Field(..., description="Customer's query message")


class QueryCreate(QueryBase):
    """
    Schema for creating a new customer support query through Contact Us form.
    """
    pass


class QueryPublic(QueryBase):
    """
    Schema for query information in list views.
    """
    id: int = Field(..., description="Query unique identifier")
    status: StatusPublic = Field(..., description="Current status of the query")
    created_at: datetime = Field(..., description="Query creation timestamp")
    responded_at: Optional[datetime] = Field(
        None, description="Timestamp when query was responded to"
    )
    model_config = ConfigDict(from_attributes=True)


class UserSimplePublic(BaseModel):
    """
    Schema for minimal user details for nesting in query responses.
    """
    id: str = Field(..., description="User unique identifier")
    email: str = Field(..., description="User's email address")
    model_config = ConfigDict(from_attributes=True)


class QueryDetailedPublic(QueryPublic):
    """
    Schema for detailed query view including admin response and responder information.
    """
    response: Optional[str] = Field(None, description="Admin's response to the query")
    responder: Optional[UserSimplePublic] = Field(
        None, description="Admin user who responded to the query"
    )

    class Config:
        from_attributes = True


class QueryResponse(BaseModel):
    """
    Schema for admin response to a customer query.
    """
    response: str = Field(
        ..., min_length=10, description="Admin's detailed response message"
    )


class PaginatedQueries(BaseModel):
    """
    Schema for paginated response for customer query lists.
    """
    total: int = Field(..., description="Total number of queries matching filters")
    items: List[QueryDetailedPublic] = Field(..., description="List of query records")


class QueryFilterParams:
    """
    Schema for filter parameters helper class for customer query searches.
    """
    def __init__(
        self,
        search: Optional[str] = None,
        status_id: Optional[int] = None,
    ):
        self.search = search
        self.status_id = status_id
