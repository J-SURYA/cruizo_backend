from fastapi import APIRouter, Depends, Security, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import rbac_service

router = APIRouter()


@router.post("/permissions", response_model=schemas.PermissionPublic)
async def create_permission(
    perm_in: schemas.PermissionCreate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["permissions:create"]),
):
    """
    Create a new system permission.

    Args:
        perm_in: Permission configuration including name and description
        db: Database session dependency

    Returns:
        Newly created permission details
    """
    return await rbac_service.create_permission(db, perm_in)


@router.get("/permissions", response_model=schemas.PermissionListResponse)
async def get_permissions(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(
        None, description="Search by permission name or scope"
    ),
    scope: Optional[str] = Query(None, description="Filter by scope"),
    sort_by: str = Query("scope", description="Sort by field (scope, name)"),
    sort_order: str = Query("ASC", description="Sort order (ASC or DESC)"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["permissions:read"]),
):
    """
    Retrieve paginated list of system permissions with filtering and sorting.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for permission name or scope
        scope: Filter by specific scope
        sort_by: Field to sort by (scope, name)
        sort_order: Sort direction (ASC/DESC)
        db: Database session dependency

    Returns:
        Paginated list of permissions with total count
    """
    return await rbac_service.get_all_permissions(
        db, skip, limit, search, scope, sort_by, sort_order
    )


@router.put("/permissions/{perm_id}", response_model=schemas.PermissionPublic)
async def update_permission(
    perm_id: int,
    perm_in: schemas.PermissionUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["permissions:update"]),
):
    """
    Update an existing permission.

    Args:
        perm_id: Unique identifier of the permission to update
        perm_in: Updated permission configuration
        db: Database session dependency

    Returns:
        Updated permission details
    """
    return await rbac_service.update_permission(db, perm_id, perm_in)


@router.delete("/permissions/{perm_id}", response_model=schemas.Msg)
async def delete_permission(
    perm_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["permissions:delete"]),
):
    """
    Delete a permission from the system.

    WARNING: This operation will cascade delete all roles associated with
    this permission and all users associated with those roles.

    Args:
        perm_id: Unique identifier of the permission to delete
        db: Database session dependency

    Returns:
        Success message confirming permission deletion
    """
    await rbac_service.delete_permission(db, perm_id)
    return schemas.Msg(message="Permission deleted successfully")


@router.post("/roles", response_model=schemas.RolePublic)
async def create_role(
    role_in: schemas.RoleCreate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["roles:create"]),
):
    """
    Create a new role with assigned permissions.

    Args:
        role_in: Role configuration including name, description and permissions
        db: Database session dependency

    Returns:
        Newly created role details with assigned permissions
    """
    return await rbac_service.create_role(db, role_in)


@router.get("/roles", response_model=schemas.RoleListResponse)
async def get_roles(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(None, description="Search by role name"),
    sort_by: str = Query("name", description="Sort by field (name)"),
    sort_order: str = Query("ASC", description="Sort order (ASC or DESC)"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["roles:read"]),
):
    """
    Retrieve paginated list of roles and their associated permissions.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for role name
        sort_by: Field to sort by (name)
        sort_order: Sort direction (ASC/DESC)
        db: Database session dependency

    Returns:
        Paginated list of roles with total count
    """
    return await rbac_service.get_all_roles(
        db, skip, limit, search, sort_by, sort_order
    )


@router.get("/roles/{role_id}", response_model=schemas.RolePublic)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["roles:read"]),
):
    """
    Retrieve a specific role by ID.

    Args:
        role_id: Unique identifier of the role to retrieve
        db: Database session dependency

    Returns:
        Complete role details including all assigned permissions
    """
    return await rbac_service.get_role_by_id(db, role_id)


@router.put("/roles/{role_id}", response_model=schemas.RolePublic)
async def update_role(
    role_id: int,
    role_in: schemas.RoleUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["roles:update"]),
):
    """
    Update an existing role and its permissions.

    Args:
        role_id: Unique identifier of the role to update
        role_in: Updated role configuration including permissions
        db: Database session dependency

    Returns:
        Updated role details with modified permissions
    """
    return await rbac_service.update_role(db, role_id, role_in)


@router.delete("/roles/{role_id}", response_model=schemas.Msg)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["roles:delete"]),
):
    """
    Delete a role from the system.

    WARNING: This operation will cascade delete all users associated
    with this role.

    Args:
        role_id: Unique identifier of the role to delete
        db: Database session dependency

    Returns:
        Success message confirming role deletion
    """
    await rbac_service.delete_role(db, role_id)
    return schemas.Msg(message="Role deleted successfully")


@router.post("/users", response_model=schemas.UserAdminPublic)
async def create_user(
    user_in: schemas.UserCreateInternal,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["users:create"]),
):
    """
    Create a new user with specific role assignment.

    Args:
        user_in: User creation data including role assignment
        db: Database session dependency

    Returns:
        Newly created user details with role information
    """
    return await rbac_service.create_user(db, user_in)


@router.get("/users", response_model=schemas.UserListResponse)
async def get_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(
        None, description="Search by username, email, or referral code"
    ),
    status: Optional[str] = Query(
        None, description="Filter by status (ACTIVE, INACTIVE, SUSPENDED, PENDING)"
    ),
    role: Optional[str] = Query(
        None, description="Filter by role name (ADMIN, CUSTOMER)"
    ),
    tag: Optional[str] = Query(
        None, description="Filter by customer tag (ROOKIE, TRAVELER, PRO)"
    ),
    is_verified: Optional[bool] = Query(
        None, description="Filter by verification status"
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort by field (username, email, created_at, total_referrals)",
    ),
    sort_order: str = Query("DESC", description="Sort order (ASC or DESC)"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["users:read"]),
):
    """
    Retrieve paginated list of all system users with filtering and sorting.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for username, email, or referral code
        status: Filter by user status
        role: Filter by role name
        tag: Filter by customer tag
        is_verified: Filter by verification status
        sort_by: Field to sort by
        sort_order: Sort direction (ASC/DESC)
        db: Database session dependency

    Returns:
        Paginated list of user details with total count
    """
    return await rbac_service.get_all_users(
        db, skip, limit, search, status, role, tag, is_verified, sort_by, sort_order
    )


@router.get("/users/{user_id}", response_model=schemas.UserAdminFullProfile)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["users:read"]),
):
    """
    Retrieve detailed information for a specific user including all profile details.

    Args:
        user_id: Unique identifier of the user to retrieve
        db: Database session dependency

    Returns:
        Complete user details including role, permissions, and customer/admin profile
    """
    return await rbac_service.get_user_full_profile(db, user_id)


@router.put("/users/{user_id}/role", response_model=schemas.UserAdminPublic)
async def update_user_role(
    user_id: str,
    data: schemas.AdminUserUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["users:update"]),
):
    """
    Update a user's role assignment.

    Args:
        user_id: Unique identifier of the user to update
        data: Role update configuration
        db: Database session dependency

    Returns:
        Updated user details with new role assignment
    """
    return await rbac_service.update_user_role(db, user_id, data)


@router.put(
    "/users/{user_id}/status",
    response_model=schemas.UserAdminPublic,
)
async def update_user_status(
    user_id: str,
    data: schemas.AdminUserStatusUpdate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["users:update"]),
):
    """
    Update a user's account status (active/inactive).

    Args:
        user_id: Unique identifier of the user to update
        data: Status update configuration
        db: Database session dependency
        current_user: Authenticated admin user performing the update

    Returns:
        Updated user details with new status
    """
    return await rbac_service.update_user_status(db, user_id, data, current_user)


@router.get("/users/{user_id}/bookings", response_model=schemas.PaginatedResponse)
async def get_user_bookings_admin(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(
        None, description="Search in car info (color, model, car_no)"
    ),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    booking_status: Optional[str] = Query(None, description="Filter by booking status"),
    review_rating: Optional[int] = Query(
        None, ge=1, le=5, description="Filter by review rating (1-5)"
    ),
    sort_by: str = Query(
        "start_time", description="Sort by field: start_time, end_time, created_at"
    ),
    sort_order: str = Query("DESC", description="Sort order: ASC or DESC"),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["users:read"]),
):
    """
    Retrieve paginated list of bookings for a specific user (admin view).

    Args:
        user_id: Unique identifier of the user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        search: Search term for car info
        payment_status: Filter by payment status
        booking_status: Filter by booking status
        review_rating: Filter by review rating
        sort_by: Field to sort by
        sort_order: Sort direction (ASC/DESC)
        db: Database session dependency

    Returns:
        Paginated list of user's bookings with total count
    """
    filters = schemas.BookingFilterParams(
        search=search,
        payment_status=payment_status,
        booking_status=booking_status,
        review_rating=review_rating,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await rbac_service.get_user_bookings_admin(
        db, user_id, skip, limit, filters
    )
