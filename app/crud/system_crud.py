from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, Query
from typing import List, Optional, Tuple
from datetime import datetime


from app import models, schemas


class SystemCRUD:
    """
    Class for managing user notifications and support queries.
    """
    def _get_notification_base_query(self) -> Query:
        """
        Base query for fetching notifications with related sender, receiver, and status.

        Returns:
            SQLAlchemy select query with joined relationships.
        """
        return select(models.Notification).options(
            selectinload(models.Notification.sender),
            selectinload(models.Notification.receiver),
            selectinload(models.Notification.status),
        )


    async def create_notification(
        self, db: AsyncSession, notification: models.Notification
    ) -> models.Notification:
        """
        Insert a new notification into the database.

        Args:
            db: Async database session
            notification: Notification ORM object

        Returns:
            Created notification record
        """
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification


    async def get_notification_by_id(
        self, db: AsyncSession, notification_id: int
    ) -> Optional[models.Notification]:
        """
        Retrieve a notification by its ID.

        Args:
            db: Async database session
            notification_id: Notification ID

        Returns:
            Notification object if found, otherwise None
        """
        query = self._get_notification_base_query().where(
            models.Notification.id == notification_id
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_paginated_notifications(
        self,
        db: AsyncSession,
        base_query: Query,
        params: schemas.NotificationFilterParams,
        skip: int,
        limit: int,
    ) -> Tuple[List[models.Notification], int]:
        """
        Paginate and filter notifications.

        Args:
            db: Async database session
            base_query: Base query for notifications
            params: Filter parameters (search, type, status_id)
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (list_of_notifications, total_count)
        """
        if params.search:
            search_term = f"%{params.search}%"
            base_query = base_query.where(
                or_(
                    models.Notification.subject.ilike(search_term),
                    models.Notification.body.ilike(search_term),
                )
            )
        if params.type:
            base_query = base_query.where(models.Notification.type == params.type)
        if params.status_id:
            base_query = base_query.where(models.Notification.status_id == params.status_id)

        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        items_query = (
            base_query.order_by(models.Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await db.execute(items_query)).scalars().unique().all()

        return items, total


    async def mark_notification_as_read(
        self, db: AsyncSession, db_notification: models.Notification, status_read: models.Status
    ) -> models.Notification:
        """
        Mark a notification as read and update timestamp.

        Args:
            db: Async database session
            db_notification: Notification ORM instance
            status_read: Status object representing 'read' status

        Returns:
            Updated notification object
        """
        db_notification.status_id = status_read.id
        db_notification.read_at = datetime.utcnow()
        await db.commit()
        await db.refresh(db_notification)
        return db_notification


    def _get_query_base_query(self) -> Query:
        """
        Base query for fetching user support queries with status and responder.

        Returns:
            SQLAlchemy select query with relationships loaded
        """
        return select(models.Query).options(
            selectinload(models.Query.status),
            selectinload(models.Query.responder),
        )


    async def create_query(self, db: AsyncSession, query: models.Query) -> models.Query:
        """
        Create a new support query.

        Args:
            db: Async database session
            query: Query ORM object

        Returns:
            Created query object
        """
        db.add(query)
        await db.commit()
        await db.refresh(query)
        return query


    async def get_query_by_id(self, db: AsyncSession, query_id: int) -> Optional[models.Query]:
        """
        Retrieve support query by ID.

        Args:
            db: Async database session
            query_id: ID of the query

        Returns:
            Query object if exists, else None
        """
        query = self._get_query_base_query().where(models.Query.id == query_id)
        return (await db.execute(query)).scalar_one_or_none()


    async def get_paginated_queries(
        self,
        db: AsyncSession,
        params: schemas.QueryFilterParams,
        skip: int,
        limit: int,
    ) -> Tuple[List[models.Query], int]:
        """
        Paginate and filter support queries.

        Args:
            db: Async database session
            params: Filter params (search, status_id)
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (queries_list, total_count)
        """
        base_query = self._get_query_base_query()

        if params.search:
            search_term = f"%{params.search}%"
            base_query = base_query.where(
                or_(
                    models.Query.name.ilike(search_term),
                    models.Query.email.ilike(search_term),
                    models.Query.phone.ilike(search_term),
                    models.Query.message.ilike(search_term),
                )
            )
        if params.status_id:
            base_query = base_query.where(models.Query.status_id == params.status_id)

        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        items_query = (
            base_query.order_by(models.Query.created_at.desc()).offset(skip).limit(limit)
        )
        items = (await db.execute(items_query)).scalars().unique().all()

        return items, total


    async def update_query_response(
        self,
        db: AsyncSession,
        db_query: models.Query,
        response: str,
        responder: models.User,
        status_responded: models.Status,
    ) -> models.Query:
        """
        Save admin response to a user query and update status.

        Args:
            db: Async database session
            db_query: Query ORM object
            response: Response text
            responder: User responding to query
            status_responded: Status indicating query has been responded

        Returns:
            Updated query object
        """
        db_query.response = response
        db_query.responded_at = datetime.utcnow()
        db_query.responded_by = responder.id
        db_query.status_id = status_responded.id

        await db.commit()
        await db.refresh(db_query)
        return db_query


    async def delete_query(self, db: AsyncSession, db_query: models.Query) -> None:
        """
        Delete a support query.

        Args:
            db: Async database session
            db_query: Query ORM object
        """
        await db.delete(db_query)
        await db.commit()


    async def get_all_notifications_for_export(
        self, db: AsyncSession, params: schemas.NotificationFilterParams
    ) -> List[models.Notification]:
        """
        Retrieve all notifications matching filters for export.

        Args:
            db: Async database session
            params: Notification filter options

        Returns:
            List of Notification objects
        """
        query = self._get_notification_base_query()

        if params.search:
            search_term = f"%{params.search}%"
            query = query.where(
                or_(
                    models.Notification.subject.ilike(search_term),
                    models.Notification.body.ilike(search_term),
                )
            )
        if params.type:
            query = query.where(models.Notification.type == params.type)
        if params.status_id:
            query = query.where(models.Notification.status_id == params.status_id)

        query = query.order_by(models.Notification.created_at.desc())
        result = await db.execute(query)
        return result.scalars().unique().all()


    async def get_all_queries_for_export(
        self, db: AsyncSession, params: schemas.QueryFilterParams
    ) -> List[models.Query]:
        """
        Retrieve all support queries matching filters for export.

        Args:
            db: Async database session
            params: Query filter options

        Returns:
            List of Query objects
        """
        query = self._get_query_base_query()

        if params.search:
            search_term = f"%{params.search}%"
            query = query.where(
                or_(
                    models.Query.name.ilike(search_term),
                    models.Query.email.ilike(search_term),
                    models.Query.phone.ilike(search_term),
                    models.Query.message.ilike(search_term),
                )
            )
        if params.status_id:
            query = query.where(models.Query.status_id == params.status_id)

        query = query.order_by(models.Query.created_at.desc())

        result = await db.execute(query)
        return result.scalars().unique().all()


system_crud = SystemCRUD()