from fastapi import (
    APIRouter,
    Depends,
    Security,
    File,
    UploadFile,
    Body,
    Form,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union, Annotated
import json

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.core.dependencies import get_sql_session
from app.services import user_service

router = APIRouter()


@router.get("/profile", response_model=schemas.UserProfilePublic)
async def get_user_profile(
    user: models.User = Security(get_current_user, scopes=["profile:read:self"]),
    db: AsyncSession = Depends(get_sql_session),
):
    """
    Retrieve the authenticated user's complete profile information.

    Args:
        user: Authenticated user object from security dependency
        db: Database session dependency

    Returns:
        Complete user profile information including role-specific details
    """
    return await user_service.get_user_profile(db, user)


@router.patch("/customer/profile/update", response_model=schemas.CustomerDetailsPublic)
async def update_customer_profile(
    data: Annotated[str, Form()] = "{}",
    profile_image: Union[UploadFile, str, None] = File(default=None),
    aadhaar_front: Union[UploadFile, str, None] = File(default=None),
    licence_front: Union[UploadFile, str, None] = File(default=None),
    user: models.User = Security(get_current_user, scopes=["profile:update:self"]),
    db: AsyncSession = Depends(get_sql_session),
):
    """
    Update customer profile details including personal information and document uploads.

    **Note:** Since this endpoint supports file uploads, it uses multipart/form-data.
    The profile data must be sent as a JSON string in the 'data' form field.

    All fields in the JSON are optional - only provided fields will be updated.
    Once data is saved, it cannot be removed (set to null/empty) in future updates,
    except for profile images which can be updated or removed.

    **JSON Schema:**
    ```json
    {
      "name": "string (optional, max 50 chars)",
      "phone": "string (optional, max 10 chars)",
      "dob": "date (optional, YYYY-MM-DD format)",
      "gender": "string (optional, max 20 chars)",
      "aadhaar_no": "string (optional, max 12 chars)",
      "license_no": "string (optional, max 15 chars)",
      "address": {
        "address_line": "string (required if address provided, max 255 chars)",
        "area": "string (required if address provided, max 100 chars)",
        "state": "string (required if address provided, max 100 chars)",
        "country": "string (required if address provided, max 100 chars)"
      }
    }
    ```

    Args:
        data: JSON string containing customer profile update data
        profile_image: Optional profile picture upload (JPG/PNG, max 2MB)
        aadhaar_front: Optional front side of Aadhaar card (JPG/PNG, max 2MB)
        licence_front: Optional front side of driving license (JPG/PNG, max 2MB)
        user: Authenticated customer user object
        db: Database session dependency

    Returns:
        Updated customer profile details
    """
    try:
        data_dict = json.loads(data)
        data_obj = schemas.CustomerDetailsUpdate(**data_dict)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON format for data field",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}",
        )

    profile_img = (
        profile_image
        if (hasattr(profile_image, "filename") and profile_image.filename)
        else None
    )
    aadhaar_img = (
        aadhaar_front
        if (hasattr(aadhaar_front, "filename") and aadhaar_front.filename)
        else None
    )
    licence_img = (
        licence_front
        if (hasattr(licence_front, "filename") and licence_front.filename)
        else None
    )

    return await user_service.update_customer_profile(
        db=db,
        user=user,
        data=data_obj,
        profile_image=profile_img,
        aadhaar_front=aadhaar_img,
        licence_front=licence_img,
    )


@router.patch("/admin/profile/update", response_model=schemas.AdminDetailsPublic)
async def update_admin_profile(
    data: Annotated[str, Form()] = "{}",
    profile_image: Union[UploadFile, str, None] = File(default=None),
    user: models.User = Security(get_current_user, scopes=["profile:update:self"]),
    db: AsyncSession = Depends(get_sql_session),
):
    """
    Update admin user profile information.

    **Note:** Since this endpoint supports file uploads, it uses multipart/form-data.
    The profile data must be sent as a JSON string in the 'data' form field.

    All fields in the JSON are optional - only provided fields will be updated.
    Once data is saved, it cannot be removed (set to null/empty) in future updates,
    except for profile images which can be updated or removed.

    **JSON Schema:**
    ```json
    {
      "name": "string (optional, max 50 chars)",
      "phone": "string (optional, max 10 chars)"
    }
    ```

    Args:
        data: JSON string containing admin profile update data
        profile_image: Optional profile picture upload (JPG/PNG, max 2MB)
        user: Authenticated admin user object
        db: Database session dependency

    Returns:
        Updated admin profile details
    """
    try:
        data_dict = json.loads(data) if data else {}
        data_obj = schemas.AdminDetailsUpdate(**data_dict)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON format for data field",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}",
        )

    profile_img = (
        profile_image
        if (hasattr(profile_image, "filename") and profile_image.filename)
        else None
    )

    return await user_service.update_admin_profile(db, user, data_obj, profile_img)


@router.post("/reset-password", response_model=schemas.Msg)
async def reset_password(
    request: schemas.PasswordResetWithOld,
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["users:update"]),
):
    """
    Reset user password by validating old password and setting new one.

    Invalidates all active user sessions after password change for security.

    Args:
        request: Password reset request containing old and new passwords
        db: Database session dependency
        current_user: Authenticated user requesting password reset

    Returns:
        Success message confirming password reset
    """
    await user_service.reset_password(
        db=db,
        user_id=current_user.id,
        old_password=request.old_password,
        new_password=request.new_password,
    )
    return schemas.Msg(message="Password has been reset successfully")


@router.post("/forgot-password", response_model=schemas.Msg)
async def forgot_password(
    request: schemas.PasswordResetRequest, db: AsyncSession = Depends(get_sql_session)
):
    """
    Initiate password reset process by generating reset token.

    In production environment, the reset token would be sent via email.
    This demo endpoint returns the token directly for testing purposes.

    Args:
        request: Password reset request containing user email
        db: Database session dependency

    Returns:
        Message containing generated reset token (for demo purposes)
    """
    message = await user_service.forgot_password(db, request.email)
    return schemas.Msg(
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/change-password", response_model=schemas.Msg)
async def change_password(
    request: schemas.PasswordResetConfirm, db: AsyncSession = Depends(get_sql_session)
):
    """
    Change user password using valid reset token.

    Args:
        request: Password change request containing reset token and new password
        db: Database session dependency

    Returns:
        Success message confirming password change
    """
    await user_service.change_password_with_token(
        db=db, token=request.token, new_password=request.new_password
    )
    return schemas.Msg(message="Password changed successfully")


@router.delete("/account", response_model=schemas.Msg)
async def delete_account(
    db: AsyncSession = Depends(get_sql_session),
    current_user: models.User = Security(get_current_user, scopes=["users:update"]),
):
    """
    Delete the authenticated user's account (self-service).

    This operation sets the user's status to INACTIVE instead of deleting the record.
    All active sessions are revoked for security. The user will not be able to login
    after deletion, but their data remains in the system.

    Args:
        db: Database session dependency
        current_user: Authenticated user requesting account deletion

    Returns:
        Success message confirming account deletion
    """
    return await user_service.delete_account(db, current_user.id)
