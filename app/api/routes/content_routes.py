from fastapi import APIRouter, Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import content_service
from app.schemas.utility_schemas import PaginationParams


router = APIRouter()


@router.get(
    "/terms/active",
    response_model=schemas.TermsMasterPublic,
)
async def get_active_terms(
    db: AsyncSession = Depends(get_sql_session),
):
    """
    Retrieve the currently active terms and conditions.
    Public endpoint - no authentication required.

    Args:
        db: Database session dependency

    Returns:
        Currently active terms and conditions document
    """
    return await content_service.get_active_terms(db)


@router.get(
    "/terms/{terms_id}",
    response_model=schemas.TermsMasterPublic,
)
async def get_terms(
    terms_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["terms:read"]),
):
    """
    Retrieve specific terms and conditions by ID.

    Args:
        terms_id: Unique identifier of the terms document
        db: Database session dependency

    Returns:
        Terms and conditions document with specified ID
    """
    return await content_service.get_terms(db, terms_id)


@router.post("/terms", response_model=schemas.TermsMasterPublic)
async def create_terms(
    terms_in: schemas.TermsMasterCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["terms:create"]),
):
    """
    Create new terms and conditions document.

    Args:
        terms_in: Terms content and configuration
        db: Database session dependency
        current_user: Authenticated user creating the terms

    Returns:
        Newly created terms and conditions document
    """
    return await content_service.create_terms(db, terms_in, current_user)


@router.put(
    "/terms/{terms_id}",
    response_model=schemas.TermsMasterPublic,
)
async def update_terms(
    terms_id: int,
    terms_in: schemas.TermsMasterUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["terms:update"]),
):
    """
    Update existing terms and conditions document.

    Args:
        terms_id: Unique identifier of the terms to update
        terms_in: Updated terms content and configuration
        db: Database session dependency

    Returns:
        Updated terms and conditions document
    """
    return await content_service.update_terms(db, terms_id, terms_in)


@router.patch(
    "/terms/{terms_id}/set-active",
    response_model=schemas.TermsMasterPublic,
)
async def set_active_terms(
    terms_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["terms:update"]),
):
    """
    Activate specific terms and deactivate all others.

    Args:
        terms_id: Unique identifier of the terms to activate
        db: Database session dependency

    Returns:
        Activated terms and conditions document
    """
    return await content_service.set_active_terms(db, terms_id)


@router.delete(
    "/terms/{terms_id}",
    response_model=schemas.utility_schemas.Msg,
)
async def delete_terms(
    terms_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["terms:delete"]),
):
    """
    Delete terms and conditions document.

    Args:
        terms_id: Unique identifier of the terms to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await content_service.delete_terms(db, terms_id)
    return schemas.utility_schemas.Msg(message="Terms deleted successfully")


@router.get(
    "/terms",
    response_model=schemas.PaginatedTermsResponse,
)
async def list_terms(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["terms:read"]),
):
    """
    Retrieve paginated list of all terms and conditions documents.

    Args:
        pagination: Pagination parameters (skip, limit)
        db: Database session dependency

    Returns:
        Paginated list of terms and conditions documents
    """
    return await content_service.list_terms(db, pagination.skip, pagination.limit)


@router.get(
    "/helpcentre/active",
    response_model=schemas.HelpCentreMasterPublic,
)
async def get_active_help_centre(
    db: AsyncSession = Depends(get_sql_session),
):
    """
    Retrieve the currently active help centre content.
    Public endpoint - no authentication required.

    Args:
        db: Database session dependency

    Returns:
        Currently active help centre document
    """
    return await content_service.get_active_help_centre(db)


@router.get(
    "/helpcentre/{help_id}",
    response_model=schemas.HelpCentreMasterPublic,
)
async def get_help_centre(
    help_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["helpcentre:read"]),
):
    """
    Retrieve specific help centre content by ID.

    Args:
        help_id: Unique identifier of the help centre document
        db: Database session dependency

    Returns:
        Help centre document with specified ID
    """
    return await content_service.get_help_centre(db, help_id)


@router.post("/helpcentre", response_model=schemas.HelpCentreMasterPublic)
async def create_help_centre(
    help_in: schemas.HelpCentreMasterCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["helpcentre:create"]
    ),
):
    """
    Create new help centre content.

    Args:
        help_in: Help centre content and configuration
        db: Database session dependency
        current_user: Authenticated user creating the help centre

    Returns:
        Newly created help centre document
    """
    return await content_service.create_help_centre(db, help_in, current_user)


@router.put(
    "/helpcentre/{help_id}",
    response_model=schemas.HelpCentreMasterPublic,
)
async def update_help_centre(
    help_id: int,
    help_in: schemas.HelpCentreMasterUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["helpcentre:update"]),
):
    """
    Update existing help centre content.

    Args:
        help_id: Unique identifier of the help centre to update
        help_in: Updated help centre content and configuration
        db: Database session dependency

    Returns:
        Updated help centre document
    """
    return await content_service.update_help_centre(db, help_id, help_in)


@router.patch(
    "/helpcentre/{help_id}/set-active",
    response_model=schemas.HelpCentreMasterPublic,
)
async def set_active_help_centre(
    help_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["helpcentre:update"]),
):
    """
    Activate specific help centre and deactivate all others.

    Args:
        help_id: Unique identifier of the help centre to activate
        db: Database session dependency

    Returns:
        Activated help centre document
    """
    return await content_service.set_active_help_centre(db, help_id)


@router.delete(
    "/helpcentre/{help_id}",
    response_model=schemas.utility_schemas.Msg,
)
async def delete_help_centre(
    help_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["helpcentre:delete"]),
):
    """
    Delete help centre content.

    Args:
        help_id: Unique identifier of the help centre to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await content_service.delete_help_centre(db, help_id)
    return schemas.utility_schemas.Msg(message="Help centre deleted successfully")


@router.get(
    "/helpcentre",
    response_model=schemas.PaginatedHelpCentreResponse,
)
async def list_help_centre(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["helpcentre:read"]),
):
    """
    Retrieve paginated list of all help centre documents.

    Args:
        pagination: Pagination parameters (skip, limit)
        db: Database session dependency

    Returns:
        Paginated list of help centre documents
    """
    return await content_service.list_help_centre(db, pagination.skip, pagination.limit)


@router.get(
    "/privacypolicy/active",
    response_model=schemas.PrivacyPolicyMasterPublic,
)
async def get_active_privacy_policy(
    db: AsyncSession = Depends(get_sql_session),
):
    """
    Retrieve the currently active privacy policy.
    Public endpoint - no authentication required.

    Args:
        db: Database session dependency

    Returns:
        Currently active privacy policy document
    """
    return await content_service.get_active_privacy_policy(db)


@router.get(
    "/privacypolicy/{privacy_id}",
    response_model=schemas.PrivacyPolicyMasterPublic,
)
async def get_privacy_policy(
    privacy_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["privacypolicy:read"]),
):
    """
    Retrieve specific privacy policy by ID.

    Args:
        privacy_id: Unique identifier of the privacy policy document
        db: Database session dependency

    Returns:
        Privacy policy document with specified ID
    """
    return await content_service.get_privacy_policy(db, privacy_id)


@router.post("/privacypolicy", response_model=schemas.PrivacyPolicyMasterPublic)
async def create_privacy_policy(
    privacy_in: schemas.PrivacyPolicyMasterCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["privacypolicy:create"]
    ),
):
    """
    Create new privacy policy document.

    Args:
        privacy_in: Privacy policy content and configuration
        db: Database session dependency
        current_user: Authenticated user creating the privacy policy

    Returns:
        Newly created privacy policy document
    """
    return await content_service.create_privacy_policy(db, privacy_in, current_user)


@router.put(
    "/privacypolicy/{privacy_id}",
    response_model=schemas.PrivacyPolicyMasterPublic,
)
async def update_privacy_policy(
    privacy_id: int,
    privacy_in: schemas.PrivacyPolicyMasterUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["privacypolicy:update"]),
):
    """
    Update existing privacy policy document.

    Args:
        privacy_id: Unique identifier of the privacy policy to update
        privacy_in: Updated privacy policy content and configuration
        db: Database session dependency

    Returns:
        Updated privacy policy document
    """
    return await content_service.update_privacy_policy(db, privacy_id, privacy_in)


@router.patch(
    "/privacypolicy/{privacy_id}/set-active",
    response_model=schemas.PrivacyPolicyMasterPublic,
)
async def set_active_privacy_policy(
    privacy_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["privacypolicy:update"]),
):
    """
    Activate specific privacy policy and deactivate all others.

    Args:
        privacy_id: Unique identifier of the privacy policy to activate
        db: Database session dependency

    Returns:
        Activated privacy policy document
    """
    return await content_service.set_active_privacy_policy(db, privacy_id)


@router.delete(
    "/privacypolicy/{privacy_id}",
    response_model=schemas.utility_schemas.Msg,
)
async def delete_privacy_policy(
    privacy_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["privacypolicy:delete"]),
):
    """
    Delete privacy policy document.

    Args:
        privacy_id: Unique identifier of the privacy policy to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await content_service.delete_privacy_policy(db, privacy_id)
    return schemas.utility_schemas.Msg(message="Privacy policy deleted successfully")


@router.get(
    "/privacypolicy",
    response_model=schemas.PaginatedPrivacyPolicyResponse,
)
async def list_privacy_policy(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["privacypolicy:read"]),
):
    """
    Retrieve paginated list of all privacy policy documents.

    Args:
        pagination: Pagination parameters (skip, limit)
        db: Database session dependency

    Returns:
        Paginated list of privacy policy documents
    """
    return await content_service.list_privacy_policy(
        db, pagination.skip, pagination.limit
    )


@router.get(
    "/faq/active",
    response_model=schemas.FAQMasterPublic,
)
async def get_active_faq(
    db: AsyncSession = Depends(get_sql_session),
):
    """
    Retrieve the currently active FAQ content.
    Public endpoint - no authentication required.

    Args:
        db: Database session dependency

    Returns:
        Currently active FAQ document
    """
    return await content_service.get_active_faq(db)


@router.get(
    "/faq/{faq_id}",
    response_model=schemas.FAQMasterPublic,
)
async def get_faq(
    faq_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["faq:read"]),
):
    """
    Retrieve specific FAQ content by ID.

    Args:
        faq_id: Unique identifier of the FAQ document
        db: Database session dependency

    Returns:
        FAQ document with specified ID
    """
    return await content_service.get_faq(db, faq_id)


@router.post("/faq", response_model=schemas.FAQMasterPublic)
async def create_faq(
    faq_in: schemas.FAQMasterCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["faq:create"]),
):
    """
    Create new FAQ content.

    Args:
        faq_in: FAQ questions, answers and configuration
        db: Database session dependency
        current_user: Authenticated user creating the FAQ

    Returns:
        Newly created FAQ document
    """
    return await content_service.create_faq(db, faq_in, current_user)


@router.put(
    "/faq/{faq_id}",
    response_model=schemas.FAQMasterPublic,
)
async def update_faq(
    faq_id: int,
    faq_in: schemas.FAQMasterUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["faq:update"]),
):
    """
    Update existing FAQ content.

    Args:
        faq_id: Unique identifier of the FAQ to update
        faq_in: Updated FAQ questions, answers and configuration
        db: Database session dependency

    Returns:
        Updated FAQ document
    """
    return await content_service.update_faq(db, faq_id, faq_in)


@router.patch(
    "/faq/{faq_id}/set-active",
    response_model=schemas.FAQMasterPublic,
)
async def set_active_faq(
    faq_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["faq:update"]),
):
    """
    Activate specific FAQ and deactivate all others.

    Args:
        faq_id: Unique identifier of the FAQ to activate
        db: Database session dependency

    Returns:
        Activated FAQ document
    """
    return await content_service.set_active_faq(db, faq_id)


@router.delete(
    "/faq/{faq_id}",
    response_model=schemas.utility_schemas.Msg,
)
async def delete_faq(
    faq_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["faq:delete"]),
):
    """
    Delete FAQ content.

    Args:
        faq_id: Unique identifier of the FAQ to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await content_service.delete_faq(db, faq_id)
    return schemas.utility_schemas.Msg(message="FAQ deleted successfully")


@router.get(
    "/faq",
    response_model=schemas.PaginatedFAQResponse,
)
async def list_faq(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["faq:read"]),
):
    """
    Retrieve paginated list of all FAQ documents.

    Args:
        pagination: Pagination parameters (skip, limit)
        db: Database session dependency

    Returns:
        Paginated list of FAQ documents
    """
    return await content_service.list_faq(db, pagination.skip, pagination.limit)


@router.get(
    "/homepage/active",
    response_model=schemas.HomePagePublic,
)
async def get_active_homepage(db: AsyncSession = Depends(get_sql_session)):
    """
    Retrieve the currently active homepage content.

    Args:
        db: Database session dependency

    Returns:
        Currently active homepage document
    """
    return await content_service.get_active_homepage(db)


@router.get(
    "/homepage/{homepage_id}",
    response_model=schemas.HomePagePublic,
)
async def get_homepage(
    homepage_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["homepage:read"]),
):
    """
    Retrieve specific homepage content by ID.

    Args:
        homepage_id: Unique identifier of the homepage document
        db: Database session dependency

    Returns:
        Homepage document with specified ID
    """
    return await content_service.get_homepage(db, homepage_id)


@router.post("/homepage", response_model=schemas.HomePagePublic)
async def create_homepage(
    homepage_in: schemas.HomePageCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["homepage:create"]),
):
    """
    Create new homepage content.

    Args:
        homepage_in: Homepage sections, content and configuration
        db: Database session dependency
        current_user: Authenticated user creating the homepage

    Returns:
        Newly created homepage document
    """
    return await content_service.create_homepage(db, homepage_in, current_user)


@router.put(
    "/homepage/{homepage_id}",
    response_model=schemas.HomePagePublic,
)
async def update_homepage(
    homepage_id: int,
    homepage_in: schemas.HomePageUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["homepage:update"]),
):
    """
    Update existing homepage content.

    Args:
        homepage_id: Unique identifier of the homepage to update
        homepage_in: Updated homepage sections, content and configuration
        db: Database session dependency

    Returns:
        Updated homepage document
    """
    return await content_service.update_homepage(db, homepage_id, homepage_in)


@router.patch(
    "/homepage/{homepage_id}/set-active",
    response_model=schemas.HomePagePublic,
)
async def set_active_homepage(
    homepage_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["homepage:update"]),
):
    """
    Activate specific homepage and deactivate all others.

    Args:
        homepage_id: Unique identifier of the homepage to activate
        db: Database session dependency

    Returns:
        Activated homepage document
    """
    return await content_service.set_active_homepage(db, homepage_id)


@router.delete(
    "/homepage/{homepage_id}",
    response_model=schemas.utility_schemas.Msg,
)
async def delete_homepage(
    homepage_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["homepage:delete"]),
):
    """
    Delete homepage content.

    Args:
        homepage_id: Unique identifier of the homepage to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await content_service.delete_homepage(db, homepage_id)
    return schemas.utility_schemas.Msg(message="Homepage deleted successfully")


@router.get(
    "/homepage",
    response_model=schemas.PaginatedHomePageResponse,
)
async def list_homepage(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["homepage:read"]),
):
    """
    Retrieve paginated list of all homepage documents.

    Args:
        pagination: Pagination parameters (skip, limit)
        db: Database session dependency

    Returns:
        Paginated list of homepage documents
    """
    return await content_service.list_homepage(db, pagination.skip, pagination.limit)


@router.get(
    "/admin-helpcentre/active",
    response_model=schemas.AdminHelpCentreMasterPublic,
)
async def get_active_admin_help_centre(
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Depends(get_current_user),
):
    """
    Retrieve the currently active admin help centre content.
    Requires authentication - accessible to any logged-in user.

    Args:
        db: Database session dependency

    Returns:
        Currently active admin help centre document
    """
    return await content_service.get_active_admin_help_centre(db)


@router.get(
    "/admin-helpcentre/{admin_help_id}",
    response_model=schemas.AdminHelpCentreMasterPublic,
)
async def get_admin_help_centre(
    admin_help_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Depends(get_current_user),
):
    """
    Retrieve specific admin help centre by ID.
    Requires authentication - accessible to any logged-in user.

    Args:
        admin_help_id: Unique identifier of the admin help centre document
        db: Database session dependency

    Returns:
        Admin help centre document with specified ID
    """
    return await content_service.get_admin_help_centre(db, admin_help_id)


@router.post(
    "/admin-helpcentre",
    response_model=schemas.AdminHelpCentreMasterPublic,
)
async def create_admin_help_centre(
    admin_help_in: schemas.AdminHelpCentreMasterCreate,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(
        get_current_user, scopes=["helpcentre:create"]
    ),
):
    """
    Create new admin help centre document.
    Requires helpcentre:create permission.

    Args:
        admin_help_in: Admin help centre content and configuration
        db: Database session dependency
        current_user: Authenticated user creating the document

    Returns:
        Newly created admin help centre document
    """
    return await content_service.create_admin_help_centre(
        db, admin_help_in, current_user
    )


@router.put(
    "/admin-helpcentre/{admin_help_id}",
    response_model=schemas.AdminHelpCentreMasterPublic,
)
async def update_admin_help_centre(
    admin_help_id: int,
    admin_help_in: schemas.AdminHelpCentreMasterUpdate,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["helpcentre:update"]),
):
    """
    Update existing admin help centre document.
    Requires helpcentre:update permission.

    Args:
        admin_help_id: Unique identifier of the admin help centre to update
        admin_help_in: Updated admin help centre content and configuration
        db: Database session dependency

    Returns:
        Updated admin help centre document
    """
    return await content_service.update_admin_help_centre(
        db, admin_help_id, admin_help_in
    )


@router.patch(
    "/admin-helpcentre/{admin_help_id}/set-active",
    response_model=schemas.AdminHelpCentreMasterPublic,
)
async def set_active_admin_help_centre(
    admin_help_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["helpcentre:update"]),
):
    """
    Activate specific admin help centre and deactivate all others.
    Requires helpcentre:update permission.

    Args:
        admin_help_id: Unique identifier of the admin help centre to activate
        db: Database session dependency

    Returns:
        Activated admin help centre document
    """
    return await content_service.set_active_admin_help_centre(db, admin_help_id)


@router.delete(
    "/admin-helpcentre/{admin_help_id}",
    response_model=schemas.utility_schemas.Msg,
)
async def delete_admin_help_centre(
    admin_help_id: int,
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Security(get_current_user, scopes=["helpcentre:delete"]),
):
    """
    Delete admin help centre document.
    Requires helpcentre:delete permission.

    Args:
        admin_help_id: Unique identifier of the admin help centre to delete
        db: Database session dependency

    Returns:
        Success message confirming deletion
    """
    await content_service.delete_admin_help_centre(db, admin_help_id)
    return schemas.utility_schemas.Msg(message="Admin Help Centre deleted successfully")


@router.get(
    "/admin-helpcentre",
    response_model=schemas.PaginatedAdminHelpCentreResponse,
)
async def list_admin_help_centre(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_sql_session),
    _: models.User = Depends(get_current_user),
):
    """
    Retrieve paginated list of all admin help centre documents.
    Requires authentication - accessible to any logged-in user.

    Args:
        pagination: Pagination parameters (skip, limit)
        db: Database session dependency

    Returns:
        Paginated list of admin help centre documents
    """
    return await content_service.list_admin_help_centre(
        db, pagination.skip, pagination.limit
    )
