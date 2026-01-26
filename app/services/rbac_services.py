from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional


from app import models, schemas
from app.crud import rbac_crud, user_crud, booking_crud
from app.auth import security
from app.utils.id_utils import generate_prefixed_id
from app.utils.exception_utils import (
    NotFoundException,
    DuplicateEntryException,
)


class RBACService:
    """
    Service layer for all administrative operations like managing permissions, roles, and user accounts.
    """
    async def create_permission(
        self, db: AsyncSession, perm_in: schemas.PermissionCreate
    ) -> models.Permission:
        """
        Create a new permission.
        
        Args:
            db: Database session
            perm_in: Permission creation data
        
        Returns:
            The created permission object
        """
        existing = await rbac_crud.get_permission_by_name_and_scope(
            db, perm_in.name, perm_in.scope
        )
        if existing:
            raise DuplicateEntryException(
                "Permission with this name and scope already exists"
            )
        return await rbac_crud.create_permission(db, perm_in)


    async def get_all_permissions(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        scope: Optional[str] = None,
        sort_by: str = "scope",
        sort_order: str = "ASC",
    ) -> schemas.PermissionListResponse:
        """
        Fetch paginated permissions with filtering and sorting.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search query string
            scope: Filter by permission scope
            sort_by: Field to sort by
            sort_order: Sort order (ASC or DESC)
        
        Returns:
            Paginated list of permissions with total count
        """
        items, total = await rbac_crud.get_all_permissions_paginated(
            db, skip, limit, search, scope, sort_by, sort_order
        )
        return schemas.PermissionListResponse(items=items, total=total)


    async def update_permission(
        self, db: AsyncSession, perm_id: int, perm_in: schemas.PermissionUpdate
    ) -> models.Permission:
        """
        Update an existing permission.
        
        Args:
            db: Database session
            perm_id: ID of the permission to update
            perm_in: Updated permission data
        
        Returns:
            The updated permission object
        """
        db_perm = await rbac_crud.get_permission_by_id(db, perm_id)
        if not db_perm:
            raise NotFoundException("Permission not found")

        existing = await rbac_crud.get_permission_by_name_and_scope(
            db, perm_in.name, perm_in.scope
        )
        if existing and existing.id != perm_id:
            raise DuplicateEntryException(
                "Another permission with this name and scope exists"
            )

        return await rbac_crud.update_permission(db, db_perm, perm_in)


    async def delete_permission(self, db: AsyncSession, perm_id: int) -> None:
        """
        Delete a permission and remove it from roles using it.
        
        Args:
            db: Database session
            perm_id: ID of the permission to delete
        
        Returns:
            None
        """
        db_perm = await rbac_crud.get_permission_by_id(db, perm_id)
        if not db_perm:
            raise NotFoundException("Permission not found")

        roles_to_delete = await rbac_crud.get_roles_by_permission_id(db, perm_id)
        for role in roles_to_delete:
            await self.delete_role(db, role.id)

        await rbac_crud.delete_permission(db, db_perm)


    async def create_role(
        self, db: AsyncSession, role_in: schemas.RoleCreate
    ) -> models.Role:
        """
        Create a new role.
        
        Args:
            db: Database session
            role_in: Role creation data
        
        Returns:
            The created role object
        """
        existing = await rbac_crud.get_role_by_name(db, role_in.name)
        if existing:
            raise DuplicateEntryException("Role with this name already exists")

        db_role = models.Role(name=role_in.name)

        if role_in.permissions:
            permissions = await rbac_crud.get_permissions_by_ids(
                db, role_in.permissions
            )
            if len(permissions) != len(role_in.permissions):
                found_ids = {p.id for p in permissions}
                missing_id = next(
                    pid for pid in role_in.permissions if pid not in found_ids
                )
                raise NotFoundException(f"Permission with ID {missing_id} not found")
            db_role.permissions = permissions

        return await rbac_crud.create_role(db, db_role)


    async def get_all_roles(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "ASC",
    ) -> schemas.RoleListResponse:
        """
        Get paginated roles with permissions loaded.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search query string
            sort_by: Field to sort by
            sort_order: Sort order (ASC or DESC)
        
        Returns:
            Paginated list of roles with total count
        """
        items, total = await rbac_crud.get_all_roles_paginated(
            db, skip, limit, search, sort_by, sort_order
        )
        return schemas.RoleListResponse(items=items, total=total)


    async def get_role_by_id(self, db: AsyncSession, role_id: int) -> models.Role:
        """
        Retrieve a role by its ID.
        
        Args:
            db: Database session
            role_id: ID of the role to retrieve
        
        Returns:
            The role object
        """
        db_role = await rbac_crud.get_role_by_id(db, role_id)
        if not db_role:
            raise NotFoundException("Role not found")
        return db_role


    async def update_role(
        self, db: AsyncSession, role_id: int, role_in: schemas.RoleUpdate
    ) -> models.Role:
        """
        Update role name and permissions.
        
        Args:
            db: Database session
            role_id: ID of the role to update
            role_in: Updated role data
        
        Returns:
            The updated role object
        """
        db_role = await rbac_crud.get_role_by_id(db, role_id)
        if not db_role:
            raise NotFoundException("Role not found")

        existing = await rbac_crud.get_role_by_name(db, role_in.name)
        if existing and existing.id != role_id:
            raise DuplicateEntryException("Another role with this name already exists")

        db_role.name = role_in.name

        if role_in.permissions:
            permissions = await rbac_crud.get_permissions_by_ids(
                db, role_in.permissions
            )
            if len(permissions) != len(role_in.permissions):
                found_ids = {p.id for p in permissions}
                missing_id = next(
                    pid for pid in role_in.permissions if pid not in found_ids
                )
                raise NotFoundException(f"Permission with ID {missing_id} not found")
            db_role.permissions = permissions
        else:
            db_role.permissions = []

        return await rbac_crud.update_role(db, db_role)


    async def delete_role(self, db: AsyncSession, role_id: int) -> None:
        """
        Delete a role and all users assigned to it.
        
        Args:
            db: Database session
            role_id: ID of the role to delete
        
        Returns:
            None
        """
        db_role = await rbac_crud.get_role_by_id(db, role_id)
        if not db_role:
            raise NotFoundException("Role not found")

        users_to_delete = await rbac_crud.get_users_by_role_id(db, role_id)
        for user in users_to_delete:
            await self.delete_user(db, user.id)

        db_role.permissions.clear()
        await rbac_crud.delete_role(db, db_role)


    async def create_user(
        self, db: AsyncSession, user_in: schemas.UserCreateInternal
    ) -> models.User:
        """
        Admin creates a new user account.
        
        Args:
            db: Database session
            user_in: User creation data
        
        Returns:
            The created user object
        """
        if await user_crud.get_by_username(db, user_in.username):
            raise DuplicateEntryException("Username already registered")
        if await user_crud.get_by_email(db, user_in.email):
            raise DuplicateEntryException("Email already registered")

        role = await rbac_crud.get_role_by_id(db, user_in.role_id)
        if not role:
            raise NotFoundException("Specified role not found")

        status_obj = await rbac_crud.get_status_by_name(
            db, models.enums.StatusEnum.ACTIVE
        )
        if not status_obj:
            raise NotFoundException("Default 'active' status not found")

        user_id = await generate_prefixed_id(db, prefix="U")
        hashed_password = security.get_password_hash(user_in.password)

        user_in_db = schemas.UserCreate(
            **user_in.model_dump(exclude={"password", "role_id"}),
            password=hashed_password,
        )

        db_user = await user_crud.create_user(
            db,
            user_in=user_in_db,
            user_id=user_id,
            role_id=role.id,
            status_id=status_obj.id,
        )

        return await rbac_crud.get_user_by_id(db, db_user.id)


    async def get_all_users(
        self,
        db: AsyncSession,
        skip: int,
        limit: int,
        search: str = None,
        status: str = None,
        role: str = None,
        tag: str = None,
        is_verified: bool = None,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
    ) -> dict:
        """
        Paginated list of users with filtering and sorting.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search query string
            status: Filter by user status
            role: Filter by user role
            tag: Filter by customer tag
            is_verified: Filter by verification status
            sort_by: Field to sort by
            sort_order: Sort order (ASC or DESC)
        
        Returns:
            Dictionary containing items and total count
        """
        users, total = await rbac_crud.get_all_users_filtered(
            db, skip, limit, search, status, role, tag, is_verified, sort_by, sort_order
        )

        items = []
        for user in users:
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "referral_code": user.referral_code,
                "referral_count": user.referral_count,
                "total_referrals": user.total_referrals,
                "created_at": user.created_at,
                "tag": "ROOKIE",
                "is_verified": None,
            }
            if user.customer_details:
                user_data["tag"] = (
                    user.customer_details.tag.name
                    if user.customer_details.tag
                    else "ROOKIE"
                )
                user_data["is_verified"] = user.customer_details.is_verified
            items.append(user_data)

        return {"items": items, "total": total}


    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> models.User:
        """
        Get a user by ID.
        
        Args:
            db: Database session
            user_id: ID of the user to retrieve
        
        Returns:
            The user object
        """
        db_user = await rbac_crud.get_user_by_id(db, user_id)
        if not db_user:
            raise NotFoundException("User not found")
        return db_user


    async def get_user_full_profile(self, db: AsyncSession, user_id: str) -> dict:
        """
        Get a user's full profile with all customer/admin details.
        
        Args:
            db: Database session
            user_id: ID of the user to retrieve
        
        Returns:
            Dictionary containing complete user profile data
        """
        db_user = await rbac_crud.get_user_by_id_with_details(db, user_id)
        if not db_user:
            raise NotFoundException("User not found")

        result = {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "role": db_user.role,
            "status": db_user.status,
            "referral_code": db_user.referral_code,
            "referral_count": db_user.referral_count,
            "total_referrals": db_user.total_referrals,
            "created_at": db_user.created_at,
            "customer_details": None,
            "admin_details": None,
        }

        if db_user.customer_details:
            cd = db_user.customer_details
            result["customer_details"] = {
                "name": cd.name,
                "phone": cd.phone,
                "dob": cd.dob,
                "gender": cd.gender,
                "profile_url": cd.profile_url,
                "aadhaar_no": cd.aadhaar_no,
                "license_no": cd.license_no,
                "aadhaar_front_url": cd.aadhaar_front_url,
                "license_front_url": cd.license_front_url,
                "is_verified": cd.is_verified,
                "tag": cd.tag.name if cd.tag else None,
                "rookie_benefit_used": cd.rookie_benefit_used,
                "address": (
                    {
                        "id": cd.address.id,
                        "address_line": cd.address.address_line,
                        "area": cd.address.area,
                        "state": cd.address.state,
                        "country": cd.address.country,
                    }
                    if cd.address
                    else None
                ),
            }

        if db_user.admin_details:
            ad = db_user.admin_details
            result["admin_details"] = {
                "name": ad.name,
                "phone": ad.phone,
                "profile_url": ad.profile_url,
            }

        return result


    async def update_user_role(
        self, db: AsyncSession, user_id: str, data: schemas.AdminUserUpdate
    ) -> models.User:
        """
        Update a user's role.
        
        Args:
            db: Database session
            user_id: ID of the user to update
            data: Updated role data
        
        Returns:
            The updated user object
        """
        db_user = await rbac_crud.get_user_by_id(db, user_id)
        if not db_user:
            raise NotFoundException("User not found")

        role = await rbac_crud.get_role_by_id(db, data.role_id)
        if not role:
            raise NotFoundException("Specified role not found")

        updated_user = await rbac_crud.update_user_role(db, db_user, data.role_id)
        return await rbac_crud.get_user_by_id(db, updated_user.id)


    async def update_user_status(
        self,
        db: AsyncSession,
        user_id: str,
        data: schemas.AdminUserStatusUpdate,
        current_user: models.User,
    ) -> models.User:
        """
        Update user status (ACTIVE/INACTIVE).
        
        Args:
            db: Database session
            user_id: ID of the user to update
            data: Updated status data
            current_user: The currently authenticated user
        
        Returns:
            The updated user object
        """
        db_user = await rbac_crud.get_user_by_id(db, user_id)
        if not db_user:
            raise NotFoundException("User not found")

        if db_user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot change their own status",
            )

        status_obj = await rbac_crud.get_status_by_id(db, data.status_id)
        if not status_obj:
            raise NotFoundException(f"Status with ID {data.status_id} not found")

        updated_user = await rbac_crud.update_user_status(db, db_user, status_obj)
        return await rbac_crud.get_user_by_id(db, updated_user.id)


    async def delete_user(self, db: AsyncSession, user_id: str) -> None:
        """
        Delete a user.
        
        Args:
            db: Database session
            user_id: ID of the user to delete
        
        Returns:
            None
        """
        db_user = await rbac_crud.get_user_by_id(db, user_id)
        if not db_user:
            raise NotFoundException("User not found")

        await rbac_crud.delete_user(db, db_user)


    async def get_user_bookings_admin(
        self,
        db: AsyncSession,
        user_id: str,
        skip: int,
        limit: int,
        filters: schemas.BookingFilterParams,
    ) -> schemas.PaginatedResponse:
        """
        Get bookings for a specific user (admin view).
        
        Args:
            db: Database session
            user_id: ID of the user to get bookings for
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Booking filter parameters
        
        Returns:
            Paginated response with booking data
        """
        db_user = await rbac_crud.get_user_by_id(db, user_id)
        if not db_user:
            raise NotFoundException("User not found")

        items, total = await booking_crud.get_user_bookings_data(
            db, user_id, skip, limit, filters
        )
        return schemas.PaginatedResponse(
            total=total, items=items, skip=skip, limit=limit
        )


rbac_service = RBACService()
