from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple


from app import models, schemas


class RBACCRUD:
    """
    Class for managing Role-Based Access Control (RBAC) operations
    """
    async def get_all_statuses(self, db: AsyncSession) -> List[models.Status]:
        """
        Retrieve all status records
        
        Args:
            db: Async database session
        
        Returns:
            List of Status ORM objects
        """
        result = await db.execute(select(models.Status))
        return result.scalars().all()


    async def get_permission_by_id(
        self, db: AsyncSession, perm_id: int
    ) -> Optional[models.Permission]:
        """
        Get a permission record by ID
        
        Args:
            db: Async database session
            perm_id: Permission ID
        
        Returns:
            Permission object if found, else None
        """
        return await db.get(models.Permission, perm_id)


    async def get_permissions_by_ids(
        self, db: AsyncSession, perm_ids: List[int]
    ) -> List[models.Permission]:
        """
        Retrieve multiple permissions by their IDs
        
        Args:
            db: Async database session
            perm_ids: List of permission IDs
        
        Returns:
            List of Permission objects
        """
        if not perm_ids:
            return []
        result = await db.execute(
            select(models.Permission).where(models.Permission.id.in_(perm_ids))
        )
        return result.scalars().all()


    async def get_all_permissions(self, db: AsyncSession) -> List[models.Permission]:
        """
        Get all permission records
        
        Args:
            db: Async database session
        
        Returns:
            List of Permission ORM objects
        """
        result = await db.execute(select(models.Permission))
        return result.scalars().all()


    async def get_all_permissions_paginated(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        scope: Optional[str] = None,
        sort_by: str = "scope",
        sort_order: str = "ASC",
    ) -> Tuple[List[models.Permission], int]:
        """
        Get paginated permission records with filtering and sorting
        
        Args:
            db: Async database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search term for name or scope
            scope: Filter by specific scope
            sort_by: Field to sort by (scope, name)
            sort_order: Sort direction (ASC/DESC)
        
        Returns:
            Tuple of (list of Permission ORM objects, total count)
        """
        query = select(models.Permission)
        count_query = select(func.count()).select_from(models.Permission)
        if search:
            search_filter = or_(
                models.Permission.name.ilike(f"%{search}%"),
                models.Permission.scope.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        if scope:
            query = query.where(models.Permission.scope == scope)
            count_query = count_query.where(models.Permission.scope == scope)
        sort_column = getattr(models.Permission, sort_by, models.Permission.scope)
        if sort_order.upper() == "DESC":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all(), total


    async def get_permission_by_name_and_scope(
        self, db: AsyncSession, name: str, scope: str
    ) -> Optional[models.Permission]:
        """
        Find a permission by name and scope
        
        Args:
            db: Async database session
            name: Permission name
            scope: Scope name
        
        Returns:
            Permission object if found, else None
        """
        result = await db.execute(
            select(models.Permission).where(
                models.Permission.name == name,
                models.Permission.scope == scope,
            )
        )
        return result.scalar_one_or_none()


    async def create_permission(
        self, db: AsyncSession, perm_in: schemas.PermissionCreate
    ) -> models.Permission:
        """
        Create a new permission
        
        Args:
            db: Async database session
            perm_in: Permission create schema
        
        Returns:
            Newly created Permission ORM object
        """
        db_perm = models.Permission(name=perm_in.name, scope=perm_in.scope)
        db.add(db_perm)
        await db.commit()
        await db.refresh(db_perm)
        return db_perm


    async def update_permission(
        self, db: AsyncSession, db_perm: models.Permission, perm_in: schemas.PermissionUpdate
    ) -> models.Permission:
        """
        Update an existing permission
        
        Args:
            db: Async database session
            db_perm: Existing Permission ORM object
            perm_in: Updated permission details
        
        Returns:
            Updated Permission ORM object
        """
        db_perm.name = perm_in.name
        db_perm.scope = perm_in.scope
        await db.commit()
        await db.refresh(db_perm)
        return db_perm


    async def delete_permission(self, db: AsyncSession, db_perm: models.Permission) -> None:
        """
        Delete a permission record
        
        Args:
            db: Async database session
            db_perm: Permission ORM object to delete
        
        Returns:
            None
        """
        await db.delete(db_perm)
        await db.commit()


    async def get_role_by_id(self, db: AsyncSession, role_id: int) -> Optional[models.Role]:
        """
        Retrieve a role by ID with its related permissions
        
        Args:
            db: Async database session
            role_id: Role ID
        
        Returns:
            Role object with permissions preloaded, else None
        """
        result = await db.execute(
            select(models.Role)
            .options(selectinload(models.Role.permissions))
            .where(models.Role.id == role_id)
        )
        return result.scalar_one_or_none()


    async def get_role_by_name(self, db: AsyncSession, name: str) -> Optional[models.Role]:
        """
        Retrieve a role by its name
        
        Args:
            db: Async database session
            name: Role name
        
        Returns:
            Role object if found, else None
        """
        result = await db.execute(
            select(models.Role)
            .options(selectinload(models.Role.permissions))
            .where(models.Role.name == name)
        )
        return result.scalar_one_or_none()


    async def get_all_roles(self, db: AsyncSession) -> List[models.Role]:
        """
        Retrieve all roles with their permissions
        
        Args:
            db: Async database session
        
        Returns:
            List of Role ORM objects
        """
        result = await db.execute(
            select(models.Role).options(selectinload(models.Role.permissions))
        )
        return result.scalars().unique().all()


    async def get_all_roles_paginated(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "ASC",
    ) -> Tuple[List[models.Role], int]:
        """
        Retrieve paginated roles with their permissions
        
        Args:
            db: Async database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search term for role name
            sort_by: Field to sort by (name)
            sort_order: Sort direction (ASC/DESC)
        
        Returns:
            Tuple of (list of Role ORM objects, total count)
        """
        query = select(models.Role).options(selectinload(models.Role.permissions))
        count_query = select(func.count()).select_from(models.Role)
        if search:
            search_filter = models.Role.name.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        sort_column = getattr(models.Role, sort_by, models.Role.name)
        if sort_order.upper() == "DESC":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().unique().all(), total


    async def create_role(self, db: AsyncSession, db_role: models.Role) -> models.Role:
        """
        Create a new role
        
        Args:
            db: Async database session
            db_role: Role ORM object
        
        Returns:
            Created Role object with permissions
        """
        db.add(db_role)
        await db.commit()
        await db.refresh(db_role)
        await db.refresh(db_role, attribute_names=["permissions"])
        return db_role


    async def update_role(self, db: AsyncSession, db_role: models.Role) -> models.Role:
        """
        Update role details
        
        Args:
            db: Async database session
            db_role: Role ORM object to update
        
        Returns:
            Updated Role object
        """
        await db.commit()
        await db.refresh(db_role)
        await db.refresh(db_role, attribute_names=["permissions"])
        return db_role


    async def delete_role(self, db: AsyncSession, db_role: models.Role) -> None:
        """
        Delete an existing role
        
        Args:
            db: Async database session
            db_role: Role ORM object to delete
        
        Returns:
            None
        """
        await db.delete(db_role)
        await db.commit()


    async def get_roles_by_permission_id(
        self, db: AsyncSession, perm_id: int
    ) -> List[models.Role]:
        """
        Get all roles containing a specific permission
        
        Args:
            db: Async database session
            perm_id: Permission ID
        
        Returns:
            List of Role objects
        """
        result = await db.execute(
            select(models.Role).where(
                models.Role.permissions.any(models.Permission.id == perm_id)
            )
        )
        return result.scalars().unique().all()


    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[models.User]:
        """
        Retrieve a user by ID with related status, role, and permissions
        
        Args:
            db: Async database session
            user_id: User ID
        
        Returns:
            User object if found, else None
        """
        result = await db.execute(
            select(models.User)
            .options(
                selectinload(models.User.status),
                selectinload(models.User.role).selectinload(models.Role.permissions),
            )
            .where(models.User.id == user_id)
        )
        return result.scalar_one_or_none()


    async def get_user_by_id_with_details(
        self, db: AsyncSession, user_id: str
    ) -> Optional[models.User]:
        """
        Retrieve a user by ID with all related details including customer/admin profiles
        
        Args:
            db: Async database session
            user_id: User ID
        
        Returns:
            User object with all details if found, else None
        """
        result = await db.execute(
            select(models.User)
            .options(
                selectinload(models.User.status),
                selectinload(models.User.role).selectinload(models.Role.permissions),
                selectinload(models.User.customer_details).selectinload(
                    models.CustomerDetails.tag
                ),
                selectinload(models.User.customer_details).selectinload(
                    models.CustomerDetails.address
                ),
                selectinload(models.User.admin_details),
            )
            .where(models.User.id == user_id)
        )
        return result.scalar_one_or_none()


    async def get_users_by_role_id(self, db: AsyncSession, role_id: int) -> List[models.User]:
        """
        Retrieve all users assigned to a specific role
        
        Args:
            db: Async database session
            role_id: Role ID
        
        Returns:
            List of User ORM objects
        """
        result = await db.execute(select(models.User).where(models.User.role_id == role_id))
        return result.scalars().all()


    async def get_all_users(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[models.User]:
        """
        Retrieve paginated list of users with status and roles
        
        Args:
            db: Async database session
            skip: Pagination offset
            limit: Pagination limit
        
        Returns:
            List of User ORM objects
        """
        result = await db.execute(
            select(models.User)
            .options(
                selectinload(models.User.status),
                selectinload(models.User.role).selectinload(models.Role.permissions),
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


    async def get_all_users_filtered(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        status: Optional[str] = None,
        role: Optional[str] = None,
        tag: Optional[str] = None,
        is_verified: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
    ) -> Tuple[List[models.User], int]:
        """
        Retrieve filtered and paginated list of users with status, roles and customer details
        
        Args:
            db: Async database session
            skip: Pagination offset
            limit: Pagination limit
            search: Search term for username, email or referral code
            status: Filter by status name
            role: Filter by role name
            tag: Filter by customer tag
            is_verified: Filter by verification status
            sort_by: Field to sort by
            sort_order: Sort direction
        
        Returns:
            Tuple of (List of User ORM objects, total count)
        """
        base_query = (
            select(models.User)
            .options(
                selectinload(models.User.status),
                selectinload(models.User.role).selectinload(models.Role.permissions),
                selectinload(models.User.customer_details).selectinload(
                    models.CustomerDetails.tag
                ),
            )
            .outerjoin(
                models.CustomerDetails, models.User.id == models.CustomerDetails.customer_id
            )
            .outerjoin(models.Tag, models.CustomerDetails.tag_id == models.Tag.id)
        )
        count_query = (
            select(func.count(models.User.id.distinct()))
            .outerjoin(
                models.CustomerDetails, models.User.id == models.CustomerDetails.customer_id
            )
            .outerjoin(models.Tag, models.CustomerDetails.tag_id == models.Tag.id)
        )
        filters = []
        if search:
            search_term = f"%{search}%"
            filters.append(
                or_(
                    models.User.username.ilike(search_term),
                    models.User.email.ilike(search_term),
                    models.User.referral_code.ilike(search_term),
                )
            )
        if status:
            base_query = base_query.join(
                models.Status, models.User.status_id == models.Status.id
            )
            count_query = count_query.join(
                models.Status, models.User.status_id == models.Status.id
            )
            filters.append(models.Status.name == status)
        if role:
            base_query = base_query.join(models.Role, models.User.role_id == models.Role.id)
            count_query = count_query.join(
                models.Role, models.User.role_id == models.Role.id
            )
            filters.append(models.Role.name == role)
        if tag:
            filters.append(models.Tag.name == tag)
        if is_verified is not None:
            filters.append(models.CustomerDetails.is_verified == is_verified)
        for f in filters:
            base_query = base_query.where(f)
            count_query = count_query.where(f)
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        if sort_by == "available_referrals":
            sort_by = "referral_count"
        sort_column = getattr(models.User, sort_by, models.User.created_at)
        if sort_order.upper() == "ASC":
            base_query = base_query.order_by(asc(sort_column))
        else:
            base_query = base_query.order_by(desc(sort_column))
        base_query = base_query.offset(skip).limit(limit)
        result = await db.execute(base_query)
        users = result.scalars().unique().all()
        return users, total


    async def update_user_role(
        self, db: AsyncSession, db_user: models.User, role_id: int
    ) -> models.User:
        """
        Update a user's role
        
        Args:
            db: Async database session
            db_user: User ORM object
            role_id: ID of new role
        
        Returns:
            Updated User ORM object
        """
        db_user.role_id = role_id
        await db.commit()
        await db.refresh(db_user)
        return db_user


    async def update_user_status(
        self, db: AsyncSession, db_user: models.User, status: models.Status
    ) -> models.User:
        """
        Update a user's status relation
        
        Args:
            db: Async database session
            db_user: User ORM object
            status: Status ORM object
        
        Returns:
            Updated User ORM object
        """
        db_user.status = status
        await db.commit()
        await db.refresh(db_user)
        return db_user


    async def delete_user(self, db: AsyncSession, db_user: models.User) -> None:
        """
        Delete a user record
        
        Args:
            db: Async database session
            db_user: User ORM object to delete
        
        Returns:
            None
        """
        await db.delete(db_user)
        await db.commit()


    async def get_status_by_id(self, db: AsyncSession, status_id: int) -> Optional[models.Status]:
        """
        Retrieve a status by its ID
        
        Args:
            db: Async database session
            status_id: Status ID
        
        Returns:
            Status object if found, else None
        """
        return await db.get(models.Status, status_id)


    async def get_status_by_name(
        self, db: AsyncSession, name: models.enums.StatusEnum
    ) -> Optional[models.Status]:
        """
        Retrieve a status by enum name
        
        Args:
            db: Async database session
            name: Status enum value
        
        Returns:
            Status object if found, else None
        """
        result = await db.execute(select(models.Status).where(models.Status.name == name))
        return result.scalar_one_or_none()


rbac_crud = RBACCRUD()