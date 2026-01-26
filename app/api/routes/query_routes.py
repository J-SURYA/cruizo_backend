from fastapi import APIRouter, Depends, Security
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import query_service

router = APIRouter()


@router.post("", response_model=schemas.QueryPublic)
async def submit_query(
    query_in: schemas.QueryCreate,
    db: AsyncSession = Depends(get_sql_session),
):
    """
    Submit a new customer support query through the Contact Us form.

    This endpoint is publicly accessible and does not require authentication.

    Args:
        query_in: Query details including contact information and message
        db: Database session dependency

    Returns:
        Submitted query details with tracking information
    """
    return await query_service.submit_query(db, query_in)


@router.get(
    "",
    response_model=schemas.PaginatedQueries,
)
async def get_all_queries(
    pagination: schemas.PaginationParams = Depends(),
    filter_params: schemas.QueryFilterParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["queries:read"]),
):
    """
    Retrieve all customer support queries with pagination and filtering.

    Args:
        pagination: Pagination parameters (skip, limit)
        filter_params: Query filtering criteria (status, date range, etc.)
        db: Database session dependency

    Returns:
        Paginated list of customer queries with response status
    """
    return await query_service.get_all_queries(
        db, filter_params, pagination.skip, pagination.limit
    )


@router.get(
    "/export",
    response_class=StreamingResponse,
)
async def export_queries(
    filter_params: schemas.QueryFilterParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["exports:create"]),
):
    """
    Export customer support queries to Excel format for reporting.

    Args:
        filter_params: Query filtering criteria for export
        db: Database session dependency

    Returns:
        Streaming response with Excel file containing query data
    """
    return await query_service.export_queries(db, filter_params)


@router.get(
    "/{query_id}",
    response_model=schemas.QueryDetailedPublic,
)
async def get_query_details(
    query_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["queries:read"]),
):
    """
    Retrieve detailed information for a specific customer query.

    Args:
        query_id: Unique identifier of the query to retrieve
        db: Database session dependency

    Returns:
        Complete query details including responses and metadata
    """
    return await query_service.get_query(db, query_id)


@router.patch(
    "/{query_id}/respond",
    response_model=schemas.Msg,
)
async def respond_to_query(
    query_id: int,
    response_in: schemas.QueryResponse,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["queries:respond"]),
):
    """
    Submit a response to a customer query and send email notification.

    Args:
        query_id: Unique identifier of the query to respond to
        response_in: Response content and configuration
        db: Database session dependency
        current_user: Authenticated admin user submitting the response

    Returns:
        Success message confirming response submission
    """
    return await query_service.respond_to_query(db, query_id, response_in, current_user)


@router.delete(
    "/{query_id}",
    response_model=schemas.Msg,
)
async def delete_query(
    query_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["queries:delete"]),
):
    """
    Delete a customer support query.

    Note: Queries can only be deleted after they have been responded to.

    Args:
        query_id: Unique identifier of the query to delete
        db: Database session dependency

    Returns:
        Success message confirming query deletion
    """
    return await query_service.delete_query(db, query_id)
