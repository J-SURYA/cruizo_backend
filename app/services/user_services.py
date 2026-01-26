from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
from jose import jwt
import uuid
from azure.storage.blob import ContentSettings
from fastapi import UploadFile
import re


from app import models, schemas
from app.auth import security
from app.core.config import settings
from app.crud import user_crud, auth_crud, rbac_crud
from app.utils.email_utils import send_email
from app.utils.exception_utils import (
    DuplicateEntryException,
    CredentialsException,
    NotFoundException,
    BadRequestException,
)
from app.models.enums import Tags, StatusEnum
from app.core.dependencies import get_container_client


class UserService:
    """
    Service class handling user-related operations including profile management, image uploads, password reset, and user data updates.
    """
    async def get_user_profile(
        self, db: AsyncSession, user: models.User
    ) -> schemas.UserProfilePublic:
        """
        Fetches the complete profile of the logged-in user with nested related details.
        
        Args:
            db: Database session
            user: Authenticated user object
        
        Returns:
            Complete user profile with role-specific details
        """
        user_with_details = await user_crud.get_user_with_details(db, user.id)
        if not user_with_details:
            raise NotFoundException("User profile not found")

        role_name = user_with_details.role.name.lower()

        if role_name == "customer":
            return await self._build_customer_profile(user_with_details)
        else:
            return await self._build_admin_profile(user_with_details)


    async def _build_customer_profile(
        self, user: models.User
    ) -> schemas.UserProfilePublic:
        """
        Builds customer profile response with customer-specific details.
        
        Args:
            user: User object with customer details
        
        Returns:
            Formatted customer profile
        """
        customer = user.customer_details
        customer_details_obj = None

        if customer:
            address_obj = (
                schemas.AddressBase.model_validate(
                    customer.address
                    if isinstance(customer.address, dict)
                    else customer.address.__dict__
                )
                if customer.address
                else None
            )

            customer_details_obj = schemas.CustomerDetailsPublic(
                username=user.username,
                name=customer.name,
                phone=customer.phone,
                dob=customer.dob,
                gender=customer.gender,
                profile_url=customer.profile_url,
                aadhaar_no=customer.aadhaar_no,
                license_no=customer.license_no,
                aadhaar_front_url=customer.aadhaar_front_url,
                license_front_url=customer.license_front_url,
                is_verified=customer.is_verified,
                tag=customer.tag.name if customer.tag else None,
                address=address_obj,
            )

        profile = schemas.UserProfilePublic(
            username=user.username,
            email=user.email,
            role=user.role.name,
            status=user.status.name,
            referral_code=user.referral_code,
            referral_count=user.referral_count,
            total_referrals=user.total_referrals,
            details=customer_details_obj,
        )
        return profile


    async def _build_admin_profile(
        self, user: models.User
    ) -> schemas.UserProfilePublic:
        """
        Builds admin profile response with admin-specific details.
        
        Args:
            user: User object with admin details
        
        Returns:
            Formatted admin profile
        """
        admin = user.admin_details
        admin_details_obj = None

        if admin:
            admin_details_obj = schemas.AdminDetailsPublic(
                username=user.username,
                name=admin.name,
                phone=admin.phone,
                profile_url=admin.profile_url,
            )

        profile = schemas.UserProfilePublic(
            username=user.username,
            email=user.email,
            role=user.role.name,
            status=user.status.name,
            referral_code=user.referral_code,
            referral_count=user.referral_count,
            total_referrals=user.total_referrals,
            details=admin_details_obj,
        )
        return profile


    def _sanitize_username(self, username: str) -> str:
        """
        Sanitizes username for safe use in blob names.
        
        Args:
            username: Original username
        
        Returns:
            Sanitized username safe for blob storage
        """
        sanitized = re.sub(r"[^a-zA-Z0-9-_]", "-", username.strip())
        return sanitized.lower()


    def _validate_image_format(self, file: UploadFile) -> None:
        """
        Validates image file format (JPG or PNG only).
        
        Args:
            file: UploadFile object containing the image
        
        Returns:
            None
        """
        content_type = (file.content_type or "").lower()
        filename = (file.filename or "").lower()

        valid_content_types = ["image/jpeg", "image/jpg", "image/png"]
        valid_extensions = [".jpg", ".jpeg", ".png"]

        is_valid_type = content_type in valid_content_types
        is_valid_extension = any(filename.endswith(ext) for ext in valid_extensions)

        if not (is_valid_type or is_valid_extension):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only JPG and PNG images are accepted",
            )


    async def _upload_image_and_get_url(
        self, container_name: str, file: UploadFile, blob_name: str
    ) -> str:
        """
        Uploads a JPG or PNG image file to Azure Blob Storage and returns the URL.
        
        Args:
            container_name: Azure container name
            file: UploadFile object containing the image
            blob_name: Name for the blob in storage
        
        Returns:
            Public URL of the uploaded image
        """
        self._validate_image_format(file)

        try:
            container_client = await get_container_client(container_name)

            file_bytes = await file.read()
            file_size = len(file_bytes)

            MAX_FILE_SIZE = 2 * 1024 * 1024
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Image file size must be less than 2 MB",
                )

            content_type = (file.content_type or "").lower()
            filename = (file.filename or "").lower()

            is_png = content_type == "image/png" or filename.endswith(".png")
            is_jpg = (
                content_type in ["image/jpeg", "image/jpg"]
                or filename.endswith(".jpg")
                or filename.endswith(".jpeg")
            )

            if is_png:
                if not blob_name.lower().endswith(".png"):
                    blob_name = f"{blob_name}.png"
                content_settings = ContentSettings(content_type="image/png")
            elif is_jpg:
                if not blob_name.lower().endswith((".jpg", ".jpeg")):
                    blob_name = f"{blob_name}.jpg"
                content_settings = ContentSettings(content_type="image/jpeg")
            else:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Only JPG and PNG images are accepted",
                )

            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.upload_blob(
                file_bytes,
                overwrite=True,
                content_settings=content_settings,
            )
            return blob_client.url
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Image upload failed: {str(e)}",
            )


    async def upload_profile_image(
        self, db: AsyncSession, user: models.User, file: UploadFile
    ) -> schemas.ImageUrlResponse:
        """
        Uploads profile image and updates user profile URL in database.
        
        Args:
            db: Database session
            user: User object
            file: Profile image file
        
        Returns:
            URL of the uploaded profile image
        """
        image_url = await self._upload_image_and_get_url(
            container_name=settings.PROFILE_CONTAINER_NAME,
            file=file,
            blob_name=self._sanitize_username(user.username),
        )

        role_name = user.role.name.lower()
        if role_name == "customer":
            db_customer = await user_crud.get_customer_details(db, user.id)
            if not db_customer:
                raise NotFoundException("Customer profile not found")
            await user_crud.update_customer_details(
                db, db_customer, {"profile_url": image_url}
            )
        else:
            db_admin = await user_crud.get_admin_details(db, user.id)
            if not db_admin:
                raise NotFoundException("Admin profile not found")
            updated_schema = schemas.AdminDetailsUpdate(
                name=db_admin.name, phone=db_admin.phone, profile_url=image_url
            )
            await user_crud.update_admin_details(db, db_admin, updated_schema)

        return schemas.ImageUrlResponse(url=image_url)


    async def upload_aadhaar_images(
        self,
        db: AsyncSession,
        user: models.User,
        front_file: UploadFile,
    ) -> schemas.AadhaarImagesUploadResponse:
        """
        Uploads Aadhaar card front image.
        
        Args:
            db: Database session
            user: User object
            front_file: Aadhaar front image
        
        Returns:
            URL of uploaded Aadhaar image
        """
        db_customer = await user_crud.get_customer_details(db, user.id)
        if not db_customer:
            raise NotFoundException("Customer profile not found")

        front_url = await self._upload_image_and_get_url(
            container_name=settings.AADHAAR_CONTAINER_NAME,
            file=front_file,
            blob_name=f"{self._sanitize_username(user.username)}_front",
        )

        await user_crud.update_customer_details(
            db,
            db_customer,
            {"aadhaar_front_url": front_url},
        )

        return schemas.AadhaarImagesUploadResponse(aadhaar_front_url=front_url)


    async def upload_licence_images(
        self,
        db: AsyncSession,
        user: models.User,
        front_file: UploadFile,
    ) -> schemas.LicenceImagesUploadResponse:
        """
        Uploads driving license front image.
        
        Args:
            db: Database session
            user: User object
            front_file: License front image
        
        Returns:
            URLs of uploaded license images
        """
        db_customer = await user_crud.get_customer_details(db, user.id)
        if not db_customer:
            raise NotFoundException("Customer profile not found")

        front_url = await self._upload_image_and_get_url(
            container_name=settings.LICENSE_CONTAINER_NAME,
            file=front_file,
            blob_name=f"{self._sanitize_username(user.username)}_front",
        )

        await user_crud.update_customer_details(
            db,
            db_customer,
            {"license_front_url": front_url},
        )

        return schemas.LicenceImagesUploadResponse(license_front_url=front_url)


    async def update_customer_profile(
        self,
        db: AsyncSession,
        user: models.User,
        data: schemas.CustomerDetailsUpdate,
        profile_image: UploadFile | None = None,
        aadhaar_front: UploadFile | None = None,
        licence_front: UploadFile | None = None,
    ) -> schemas.CustomerDetailsPublic:
        """
        Updates or creates customer profile with address and document images.
        
        Args:
            db: Database session
            user: User object
            data: Customer details update data
            profile_image: Optional profile image
            aadhaar_front: Optional Aadhaar front image
            licence_front: Optional license front image
        
        Returns:
            Updated customer profile
        """
        data_dict = data.model_dump(exclude_none=True)
        data_dict = {k: v for k, v in data_dict.items() if v != "" and v is not None}

        address_data = data_dict.pop("address", None)
        address_schema = schemas.AddressBase(**address_data) if address_data else None

        if profile_image is not None:
            uploaded = await self._upload_image_and_get_url(
                container_name=settings.PROFILE_CONTAINER_NAME,
                file=profile_image,
                blob_name=self._sanitize_username(user.username),
            )
            data_dict["profile_url"] = uploaded

        if aadhaar_front is not None:
            uploaded = await self._upload_image_and_get_url(
                container_name=settings.AADHAAR_CONTAINER_NAME,
                file=aadhaar_front,
                blob_name=f"{self._sanitize_username(user.username)}_front",
            )
            data_dict["aadhaar_front_url"] = uploaded

        if licence_front is not None:
            uploaded = await self._upload_image_and_get_url(
                container_name=settings.LICENSE_CONTAINER_NAME,
                file=licence_front,
                blob_name=f"{self._sanitize_username(user.username)}_front",
            )
            data_dict["license_front_url"] = uploaded

        db_customer = await user_crud.get_customer_details(db, user.id)

        try:
            if db_customer:
                protected_fields = [
                    "name",
                    "phone",
                    "dob",
                    "gender",
                    "aadhaar_no",
                    "license_no",
                ]
                for field in protected_fields:
                    existing_value = getattr(db_customer, field, None)
                    if existing_value is not None and field not in data_dict:
                        data_dict[field] = existing_value

                if address_schema:
                    address_dict = address_schema.model_dump()
                    if all(address_dict.values()):
                        db_address = await user_crud.create_address(db, address_schema)
                        data_dict["address_id"] = db_address.id
                    elif db_customer.address_id:
                        data_dict["address_id"] = db_customer.address_id
                elif address_data is not None and db_customer.address_id:
                    data_dict["address_id"] = db_customer.address_id

                final_aadhaar = data_dict.get("aadhaar_no") or db_customer.aadhaar_no
                final_license = data_dict.get("license_no") or db_customer.license_no
                data_dict["is_verified"] = bool(final_aadhaar and final_license)

                updated = await user_crud.update_customer_details(
                    db, db_customer, details_in=data_dict
                )
            else:
                tag = await user_crud.get_tag_by_name(db, tag_name=Tags.ROOKIE)
                if not tag:
                    raise NotFoundException(
                        "Default 'Rookie' tag not found. Please seed the database."
                    )

                address_id = None
                if address_schema:
                    address_dict = address_schema.model_dump()
                    if all(address_dict.values()):
                        db_address = await user_crud.create_address(db, address_schema)
                        address_id = db_address.id

                data_dict["is_verified"] = bool(
                    data_dict.get("aadhaar_no") and data_dict.get("license_no")
                )

                customer_data_dict = {
                    "customer_id": user.id,
                    "address_id": address_id,
                    "tag_id": tag.id,
                    **data_dict,
                }

                updated = await user_crud.create_customer_details(
                    db, details_in=customer_data_dict
                )

            await db.commit()
            await db.refresh(updated, attribute_names=["address", "tag"])

        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A profile with this phone number, Aadhaar, or License already exists.",
            )
        except Exception:
            await db.rollback()
            raise

        address_obj = (
            schemas.AddressPublic.model_validate(updated.address)
            if updated.address
            else None
        )

        return schemas.CustomerDetailsPublic(
            username=user.username,
            name=updated.name,
            phone=updated.phone,
            dob=updated.dob,
            gender=updated.gender,
            profile_url=updated.profile_url,
            aadhaar_no=updated.aadhaar_no,
            license_no=updated.license_no,
            aadhaar_front_url=updated.aadhaar_front_url,
            license_front_url=updated.license_front_url,
            is_verified=updated.is_verified,
            tag=updated.tag.name if updated.tag else None,
            address=address_obj,
        )


    async def update_admin_profile(
        self,
        db: AsyncSession,
        user: models.User,
        data: schemas.AdminDetailsUpdate,
        profile_image: UploadFile | None = None,
    ) -> schemas.AdminDetailsPublic:
        """
        Updates or creates admin profile.
        
        Args:
            db: Database session
            user: User object
            data: Admin details update data
            profile_image: Optional profile image
        
        Returns:
            Updated admin profile
        """
        data_dict = data.model_dump(exclude_none=True)
        data_dict = {k: v for k, v in data_dict.items() if v != "" and v is not None}

        if profile_image is not None:
            uploaded = await self._upload_image_and_get_url(
                container_name=settings.PROFILE_CONTAINER_NAME,
                file=profile_image,
                blob_name=self._sanitize_username(user.username),
            )
            data_dict["profile_url"] = uploaded

        data = schemas.AdminDetailsUpdate(**data_dict)

        try:
            db_admin = await user_crud.get_admin_details(db, user.id)

            if db_admin:
                protected_fields = ["name", "phone"]
                for field in protected_fields:
                    existing_value = getattr(db_admin, field, None)
                    if existing_value is not None and field not in data_dict:
                        data_dict[field] = existing_value

                data = schemas.AdminDetailsUpdate(**data_dict)
                updated = await user_crud.update_admin_details(db, db_admin, data)
            else:
                if not data_dict.get("name") or not data_dict.get("phone"):
                    raise ValueError(
                        "Name and phone are required for new admin profile"
                    )
                updated = await user_crud.create_admin_details(db, user.id, data)

        except IntegrityError:
            await db.rollback()
            raise DuplicateEntryException(
                "A profile with this phone number already exists."
            )

        except Exception:
            await db.rollback()
            raise

        return schemas.AdminDetailsPublic(
            username=user.username,
            name=updated.name,
            phone=updated.phone,
            profile_url=updated.profile_url,
        )


    async def forgot_password(self, db: AsyncSession, email: str) -> str:
        """
        Generates password reset token and sends email to user.
        
        Args:
            db: Database session
            email: User's email address
        
        Returns:
            Success message
        """
        user = await user_crud.get_by_email(db, email)
        if not user:
            return "If the email exists, a password reset link has been sent"

        expire = datetime.now(timezone.utc) + timedelta(minutes=10)
        payload = {
            "exp": expire,
            "sub": str(user.id),
            "jti": str(uuid.uuid4()),
            "type": "password-reset",
        }
        reset_token = jwt.encode(
            payload, settings.PASSWORD_RESET_SECRET_KEY, algorithm=settings.ALGORITHM
        )

        frontend_url = settings.FRONTEND_URL
        reset_url = f"{frontend_url}/forgot-password?token={reset_token}"

        await self.send_password_reset_email(user.email, user.username, reset_url)

        return True


    async def send_password_reset_email(
        self, email: str, username: str, reset_url: str
    ):
        """
        Send password reset email to user.
        
        Args:
            email: User's email address
            username: User's username
            reset_url: Password reset URL
        
        Returns:
            None
        """
        try:
            await send_email(
                subject="Reset Your CRUIZO Password",
                recipients=[email],
                body=(
                    f"Hi {username},\n\n"
                    f"We received a request to reset your password for your CRUIZO account.\n\n"
                    f"Click the link below to reset your password:\n"
                    f"{reset_url}\n\n"
                    f"This link will expire in 30 minutes.\n\n"
                    f"If you didn't request this reset, please ignore this email.\n\n"
                    f"Best regards,\n"
                    f"The CRUIZO Team"
                ),
                html=(
                    f"<h3>Hi {username},</h3>"
                    f"<p>We received a request to reset your password for your CRUIZO account.</p>"
                    f"<p><a href='{reset_url}' style='background-color: #3B82F6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;'>Reset Your Password</a></p>"
                    f"<p>This link will expire in 10 minutes.</p>"
                    f"<p>If you didn't request this reset, please ignore this email.</p>"
                    f"<br>"
                    f"<p>Best regards,<br>The CRUIZO Team</p>"
                ),
            )
            print(f"📧 Password reset email sent to: {email}")
            print(f"🔗 Reset URL: {reset_url}")

        except Exception as e:
            print(f"Failed to send password reset email: {e}")


    async def change_password_with_token(
        self, db: AsyncSession, token: str, new_password: str
    ):
        """
        Changes user password using valid reset token.
        
        Args:
            db: Database session
            token: Password reset token
            new_password: New password to set
        
        Returns:
            True if password changed successfully
        """
        try:
            payload = security.decode_token(
                token=token, secret_key=settings.PASSWORD_RESET_SECRET_KEY
            )

            if payload.type != "password-reset":
                raise CredentialsException("Invalid token type")

            user_id = payload.sub
        except Exception:
            raise CredentialsException("Invalid or expired reset token")

        user = await user_crud.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("User not found")

        user.password = security.get_password_hash(new_password)
        await user_crud.update_user(db, user)
        await auth_crud.revoke_all_user_sessions(db, user.id)
        return True


    async def reset_password(
        self, db: AsyncSession, user_id: str, old_password: str, new_password: str
    ):
        """
        Resets password after validating old password.
        
        Args:
            db: Database session
            user_id: User ID
            old_password: Current password for validation
            new_password: New password to set
        
        Returns:
            True if password reset successfully
        """
        user = await user_crud.get_by_id(db, user_id)

        if not user:
            raise NotFoundException("User not found")

        if not security.verify_password(old_password, user.password):
            raise CredentialsException("Old password is incorrect")

        user.password = security.get_password_hash(new_password)
        await user_crud.update_user(db, user)
        await auth_crud.revoke_all_user_sessions(db, user.id)
        return True


    async def delete_account(self, db: AsyncSession, user_id: str) -> schemas.Msg:
        """
        Deletes a user account by setting status to INACTIVE (self-service).
        
        Args:
            db: Database session
            user_id: User ID to delete/deactivate
        
        Returns:
            Success message
        """
        user = await user_crud.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("User not found")

        if user.status.name == "INACTIVE":
            raise BadRequestException("User account is already inactive")

        inactive_status = await rbac_crud.get_status_by_name(db, StatusEnum.INACTIVE)
        if not inactive_status:
            raise NotFoundException("INACTIVE status not found in system")

        await auth_crud.revoke_all_user_sessions(db, user_id)

        await rbac_crud.update_user_status(db, user, inactive_status)

        return schemas.Msg(
            message="Your account has been deleted successfully. All active sessions have been revoked."
        )


user_service = UserService()
