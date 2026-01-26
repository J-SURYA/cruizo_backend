from pydantic import EmailStr, Field, model_serializer
from typing import Optional, List, Union
from datetime import date, datetime


from app.models.enums import StatusEnum
from .utility_schemas import BaseSchema, StatusPublic


class TokenPayload(BaseSchema):
    """
    Schema for JWT token payload data.
    """
    sub: str = Field(..., description="Subject (user ID)")
    jti: str = Field(..., description="JWT unique identifier")
    exp: datetime = Field(..., description="Token expiration timestamp")
    type: str = Field(..., description="Token type (access/refresh)")


class Token(BaseSchema):
    """
    Schema for authentication token pair response.
    """
    access_token: str = Field(..., description="JWT access token for API authorization")
    refresh_token: str = Field(
        ..., description="JWT refresh token for obtaining new access tokens"
    )
    role: Optional[str] = Field(None, description="User role associated with the token")


class TokenResponse(BaseSchema):
    """
    Schema for authentication token response (access token only).
    """
    access_token: str = Field(..., description="JWT access token for API authorization")
    role: Optional[str] = Field(None, description="User role associated with the token")



class PasswordResetRequest(BaseSchema):
    """
    Schema for initiating password reset process.
    """
    email: EmailStr = Field(..., description="User's registered email address")


class PasswordResetConfirm(BaseSchema):
    """
    Schema for confirming password reset with token.
    """
    token: str = Field(..., description="Password reset token received via email")
    new_password: str = Field(..., description="New password to set")


class PasswordResetWithOld(BaseSchema):
    """
    Schema for password reset with old password validation.
    """
    old_password: str = Field(
        ..., min_length=8, description="Current password for validation"
    )
    new_password: str = Field(..., min_length=8, description="New password to set")


class PermissionBase(BaseSchema):
    """
    Schema for permission information.
    """

    name: str = Field(..., max_length=100, description="Permission name identifier")
    scope: str = Field(..., max_length=100, description="Permission scope or resource")


class PermissionCreate(PermissionBase):
    """
    Schema for creating a new permission.
    """
    pass


class PermissionUpdate(PermissionBase):
    """
    Schema for updating an existing permission.
    """
    pass


class PermissionPublic(PermissionBase):
    """
    Public schema for permission information.
    """
    id: int = Field(..., description="Permission unique identifier")


class PermissionListResponse(BaseSchema):
    """
    Schema for paginated permission list.
    """
    items: List["PermissionPublic"] = Field(
        default_factory=list, description="List of permissions"
    )
    total: int = Field(..., description="Total number of permissions matching filters")


class RoleBase(BaseSchema):
    """
    Schema for role information.
    """
    name: str = Field(..., max_length=100, description="The unique name of the role")


class RoleCreate(RoleBase):
    """
    Schema for creating a new role with permissions.
    """
    permissions: List[int] = Field(
        ..., description="List of permission IDs to assign to the role"
    )


class RoleUpdate(RoleBase):
    """
    Schema for updating an existing role and its permissions.
    """
    permissions: List[int] = Field(
        ..., description="List of permission IDs to assign to the role"
    )


class RolePublic(RoleBase):
    """
    Schema for role information including assigned permissions.
    """
    id: int = Field(..., description="Role unique identifier")
    permissions: List[PermissionPublic] = Field(
        default_factory=list, description="List of assigned permissions"
    )


class RoleListResponse(BaseSchema):
    """
    Schema for paginated role list.
    """
    items: List["RolePublic"] = Field(default_factory=list, description="List of roles")
    total: int = Field(..., description="Total number of roles matching filters")


class AddressBase(BaseSchema):
    """
    Schema for address information.
    """
    address_line: str = Field(..., max_length=255, description="Primary address line")
    area: str = Field(..., max_length=100, description="Locality or area")
    state: str = Field(..., max_length=100, description="State or province")
    country: str = Field(..., max_length=100, description="Country")


class AddressPublic(AddressBase):
    """
    Schema for address information.
    """
    id: int = Field(..., description="Address unique identifier")


class AdminDetailsUpdate(BaseSchema):
    """
    Schema for updating admin profile details. All fields are optional.
    """
    name: Optional[str] = Field(None, max_length=255, description="Admin's full name")
    phone: Optional[str] = Field(
        None, max_length=20, description="Admin's phone number"
    )


class AdminDetailsPublic(BaseSchema):
    """
    Schema for admin profile details.
    """
    username: str = Field(..., description="Admin's username")
    name: Optional[str] = Field(None, max_length=255, description="Admin's full name")
    phone: Optional[str] = Field(
        None, max_length=20, description="Admin's phone number"
    )
    profile_url: Optional[str] = Field(
        None, max_length=512, description="Admin's profile picture URL"
    )

    @model_serializer
    def serialize_with_username_first(self) -> dict:
        """
        Custom serializer to ensure username appears first in serialized output.
        """
        data = self.__dict__.copy()
        reordered = {"username": data.pop("username", None)}
        reordered.update(data)
        return reordered


class CustomerDetailsUpdate(BaseSchema):
    """
    Schema for updating customer profile details. All fields are optional.
    """
    name: Optional[str] = Field(
        None, max_length=255, description="Customer's full name"
    )
    phone: Optional[str] = Field(
        None, max_length=20, description="Customer's phone number"
    )
    dob: Optional[date] = Field(None, description="Customer's date of birth")
    gender: Optional[str] = Field(None, max_length=50, description="Customer's gender")
    aadhaar_no: Optional[str] = Field(
        None, max_length=12, description="Aadhaar identification number"
    )
    license_no: Optional[str] = Field(
        None, max_length=20, description="Driving license number"
    )
    address: Optional[AddressBase] = Field(
        None, description="Customer's address details"
    )


class CustomerDetailsPublic(BaseSchema):
    """
    Schema for customer profile details.
    """
    username: str = Field(..., description="Customer's username")
    name: Optional[str] = Field(None, description="Customer's full name")
    phone: Optional[str] = Field(None, description="Customer's phone number")
    dob: Optional[date] = Field(None, description="Customer's date of birth")
    gender: Optional[str] = Field(None, description="Customer's gender")
    profile_url: Optional[str] = Field(
        None, description="Customer's profile picture URL"
    )
    aadhaar_no: Optional[str] = Field(None, description="Aadhaar identification number")
    license_no: Optional[str] = Field(None, description="Driving license number")
    aadhaar_front_url: Optional[str] = Field(
        None, description="Aadhaar card front image URL"
    )
    license_front_url: Optional[str] = Field(
        None, description="Driving license front image URL"
    )
    is_verified: bool = Field(..., description="Customer verification status")
    tag: Optional[str] = Field(None, description="Customer tag or category")
    address: Optional[AddressBase] = Field(
        None, description="Customer's address details"
    )


class UserBase(BaseSchema):
    """
    Schema for user information.
    """
    username: str = Field(..., max_length=100, description="User's unique username")
    email: EmailStr = Field(..., description="User's email address")


class UserCreate(UserBase):
    """
    Schema for public user registration.
    """
    password: str = Field(..., min_length=8, description="User's password")
    referral_code: Optional[str] = Field(
        None, description="Optional referral code from another user"
    )


class UserCreateInternal(UserCreate):
    """
    Schema for admin to create users with specific role assignment.
    """
    role_id: int = Field(..., description="Role ID to assign to the user")


class UserPublic(UserBase):
    """
    Schema for basic user information.
    """
    role: str = Field(..., description="User's role name")
    status: StatusEnum = Field(..., description="User's account status")
    referral_code: Optional[str] = Field(
        None, description="User's unique referral code"
    )
    referral_count: int = Field(0, description="Current available referral count")
    total_referrals: int = Field(0, description="Total referrals made by user")


class UserAdminPublic(UserBase):
    """
    Schema for user information in admin responses.
    """
    id: str = Field(..., description="User unique identifier")
    role: RolePublic = Field(..., description="User's role with permissions")
    status: StatusPublic = Field(..., description="User's status details")


class AdminUserUpdate(BaseSchema):
    """
    Schema for admin updating a user's role.
    """
    role_id: int = Field(..., description="New role ID to assign to the user")


class AdminUserStatusUpdate(BaseSchema):
    """
    Schema for admin updating a user's status.
    """
    status_id: int = Field(..., description="New status ID to assign to the user")


class UserProfilePublic(UserPublic):
    """
    Schema for full user profile with role-specific details.
    """
    details: Optional[Union[CustomerDetailsPublic, AdminDetailsPublic]] = Field(
        None, description="Role-specific profile details"
    )

    @model_serializer
    def remove_inner_username(self):
        """
        Custom serializer to remove duplicate username from nested details.
        """
        data = self.__dict__.copy()
        if data.get("details"):
            details = data["details"].__dict__.copy()
            details.pop("username", None)
            data["details"] = details
        return data


class ImageUrlResponse(BaseSchema):
    """
    Schema for single image upload response.
    """
    url: str = Field(..., description="Uploaded image URL")


class AadhaarImagesUploadResponse(BaseSchema):
    """
    Schema for Aadhaar card image upload response.
    """
    aadhaar_front_url: str = Field(..., description="Aadhaar card front image URL")


class LicenceImagesUploadResponse(BaseSchema):
    """
    Schema for driving license image upload response.
    """
    license_front_url: str = Field(..., description="Driving license front image URL")


class UserAdminPublicWithDetails(UserAdminPublic):
    """
    Schema for user information in admin responses with customer/admin details.
    """
    referral_code: Optional[str] = Field(None, description="User's referral code")
    referral_count: int = Field(0, description="Current available referral count")
    total_referrals: int = Field(0, description="Total referrals made by user")
    tag: Optional[str] = Field(None, description="Customer tag (ROOKIE/TRAVELER/PRO)")
    is_verified: Optional[bool] = Field(
        None, description="Customer verification status"
    )
    created_at: Optional[datetime] = Field(
        None, description="Account creation timestamp"
    )


class UserListResponse(BaseSchema):
    """
    Schema for paginated response for user list with total count.
    """
    items: List[UserAdminPublicWithDetails] = Field(..., description="List of users")
    total: int = Field(..., description="Total count of users matching filters")


class CustomerDetailsAdminView(BaseSchema):
    """
    Schema for customer details for admin viewing.
    """
    name: Optional[str] = Field(None, description="Customer's full name")
    phone: Optional[str] = Field(None, description="Customer's phone number")
    dob: Optional[date] = Field(None, description="Customer's date of birth")
    gender: Optional[str] = Field(None, description="Customer's gender")
    profile_url: Optional[str] = Field(
        None, description="Customer's profile picture URL"
    )
    aadhaar_no: Optional[str] = Field(None, description="Aadhaar identification number")
    license_no: Optional[str] = Field(None, description="Driving license number")
    aadhaar_front_url: Optional[str] = Field(
        None, description="Aadhaar card front image URL"
    )
    license_front_url: Optional[str] = Field(
        None, description="Driving license front image URL"
    )
    is_verified: bool = Field(False, description="Customer verification status")
    tag: Optional[str] = Field(None, description="Customer tag (ROOKIE/TRAVELER/PRO)")
    rookie_benefit_used: bool = Field(
        False, description="Whether rookie benefit has been used"
    )
    address: Optional[AddressPublic] = Field(
        None, description="Customer's address details"
    )


class AdminDetailsAdminView(BaseSchema):
    """
    Schema for admin details.
    """
    name: Optional[str] = Field(None, description="Admin's full name")
    phone: Optional[str] = Field(None, description="Admin's phone number")
    profile_url: Optional[str] = Field(None, description="Admin's profile picture URL")


class UserAdminFullProfile(BaseSchema):
    """
    Schema for full user profile in admin view with role-specific details.
    """
    id: str = Field(..., description="User unique identifier")
    username: str = Field(..., description="User's unique username")
    email: EmailStr = Field(..., description="User's email address")
    role: RolePublic = Field(..., description="User's role with permissions")
    status: StatusPublic = Field(..., description="User's status details")
    referral_code: Optional[str] = Field(
        None, description="User's unique referral code"
    )
    referral_count: int = Field(0, description="Current available referral count")
    total_referrals: int = Field(0, description="Total referrals made by user")
    created_at: Optional[datetime] = Field(
        None, description="Account creation timestamp"
    )
    customer_details: Optional[CustomerDetailsAdminView] = Field(
        None, description="Customer-specific details"
    )
    admin_details: Optional[AdminDetailsAdminView] = Field(
        None, description="Admin-specific details"
    )
