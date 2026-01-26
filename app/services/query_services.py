from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse


from app import models, schemas
from app.crud import system_crud, rbac_crud
from app.utils.exception_utils import NotFoundException, BadRequestException
from app.utils.email_utils import send_email


class QueryService:
    """
    Service layer for managing customer support queries and handles business logic on top of system CRUD functions.
    """
    async def get_query(self, db: AsyncSession, query_id: int) -> models.Query:
        """
        Fetch a single query by ID.
        
        Args:
            db: Async database session
            query_id: ID of the query
        
        Returns:
            Query ORM object or raises NotFoundException if query doesn't exist
        """
        db_query = await system_crud.get_query_by_id(db, query_id)
        if not db_query:
            raise NotFoundException("Query not found")
        return db_query


    async def get_all_queries(
        self, db: AsyncSession, params: schemas.QueryFilterParams, skip: int, limit: int
    ) -> schemas.PaginatedQueries:
        """
        Get paginated support queries with filters.
        
        Args:
            db: Async DB session
            params: Filter params including search, status, etc.
            skip: Pagination offset
            limit: Page size
        
        Returns:
            PaginatedQueries schema containing list and total count
        """
        items, total = await system_crud.get_paginated_queries(db, params, skip, limit)
        return schemas.PaginatedQueries(total=total, items=items)


    async def submit_query(
        self, db: AsyncSession, query_in: schemas.QueryCreate
    ) -> models.Query:
        """
        Submit a new customer support query and send acknowledgment email.
        
        Args:
            db: Async DB session
            query_in: User submitted query data
        
        Returns:
            Created Query object or raises BadRequestException if PENDING status is not configured
        """
        status_pending = await rbac_crud.get_status_by_name(
            db, models.StatusEnum.PENDING
        )
        if not status_pending:
            raise BadRequestException("System status 'PENDING' not found.")

        db_query = models.Query(**query_in.model_dump(), status_id=status_pending.id)
        created_query = await system_crud.create_query(db, db_query)

        await send_email(
            subject="We have received your query",
            recipients=[created_query.email],
            body=(
                f"Hi {created_query.name},\n\n"
                f"Thank you for contacting us. We have received your query and a support "
                f"agent will get back to you soon.\n\n"
                f"Your query: {created_query.message}"
            ),
        )
        return created_query


    async def respond_to_query(
        self,
        db: AsyncSession,
        query_id: int,
        response_in: schemas.QueryResponse,
        responder: models.User,
    ) -> schemas.Msg:
        """
        Respond to a customer query and notify via email.
        
        Args:
            db: Async DB session
            query_id: ID of customer query
            response_in: Response text schema
            responder: Admin user sending response
        
        Returns:
            Success message schema or raises BadRequestException if already responded or status missing
        """
        db_query = await self.get_query(db, query_id)

        status_responded = await rbac_crud.get_status_by_name(
            db, models.StatusEnum.RESPONDED
        )
        if not status_responded:
            raise BadRequestException("System status 'RESPONDED' not found.")

        if db_query.status_id == status_responded.id:
            raise BadRequestException("This query has already been responded to.")

        await system_crud.update_query_response(
            db, db_query, response_in.response, responder, status_responded
        )

        await send_email(
            subject="RE: Your query",
            recipients=[db_query.email],
            body=(
                f"Hi {db_query.name},\n\n"
                f"Here is the response to your recent query:\n\n"
                f"'{response_in.response}'\n\n"
                f"Regards,\nSupport Team"
            ),
        )
        return schemas.Msg(message="Response sent successfully")


    async def delete_query(self, db: AsyncSession, query_id: int) -> schemas.Msg:
        """
        Delete a query only after it has been responded to.
        
        Args:
            db: Async DB session
            query_id: ID of query to delete
        
        Returns:
            Success message schema or raises BadRequestException if query not yet responded
        """
        db_query = await self.get_query(db, query_id)

        status_responded = await rbac_crud.get_status_by_name(
            db, models.StatusEnum.RESPONDED
        )
        if not status_responded:
            raise BadRequestException("System status 'RESPONDED' not found.")

        if db_query.status_id != status_responded.id:
            raise BadRequestException(
                "Cannot delete a query that has not been responded to."
            )

        await system_crud.delete_query(db, db_query)
        return schemas.Msg(message="Query deleted successfully")


    async def export_queries(
        self, db: AsyncSession, params: schemas.QueryFilterParams
    ) -> StreamingResponse:
        """
        Export filtered support queries to Excel for admin use.
        
        Args:
            db: Async DB session
            params: Filter parameters
        
        Returns:
            StreamingResponse containing Excel file
        """
        queries = await system_crud.get_all_queries_for_export(db, params)

        export_data = []
        for q in queries:
            export_data.append(
                {
                    "ID": q.id,
                    "Date Submitted": q.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "Customer Name": q.name,
                    "Customer Email": q.email,
                    "Customer Phone": q.phone,
                    "Message": q.message,
                    "Status": q.status.name.value,
                    "Responded By": q.responder.email if q.responder else "N/A",
                    "Responded At": (
                        q.responded_at.strftime("%Y-%m-%d %H:%M:%S")
                        if q.responded_at
                        else "N/A"
                    ),
                    "Admin Response": q.response if q.response else "N/A",
                }
            )

        df = pd.DataFrame(export_data)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Support Queries", index=False)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=queries_export.xlsx"},
        )


query_service = QueryService()
