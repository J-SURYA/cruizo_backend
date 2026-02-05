from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, Dict, Any

from app import models, schemas


class UserCRUD:
    """
    Class for managing user CRUD operations.
    """

    async def get_by_id(self, db: AsyncSession, user_id: str) -> Optional[models.User]:
        """
        Fetch a user by ID, including role and status.

        Args:
            db: Async database session
            user_id: User ID

        Returns:
            User object if found, else None
        """
        result = await db.execute(
            select(models.User)
            .where(models.User.id == user_id)
            .options(selectinload(models.User.role), selectinload(models.User.status))
        )
        return result.scalar_one_or_none()


    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[models.User]:
        """
        Fetch a user by username with role and status loaded.

        Args:
            db: Async DB session
            username: Username string

        Returns:
            User object if found, else None
        """
        result = await db.execute(
            select(models.User)
            .where(models.User.username == username)
            .options(selectinload(models.User.role), selectinload(models.User.status))
        )
        return result.scalar_one_or_none()


    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[models.User]:
        """
        Fetch user by email.

        Args:
            db: Async DB session
            email: Email address

        Returns:
            User if exists, else None
        """
        result = await db.execute(
            select(models.User)
            .where(models.User.email == email)
            .options(selectinload(models.User.role), selectinload(models.User.status))
        )
        return result.scalar_one_or_none()


    async def get_user_with_role_and_permissions(
        self, db: AsyncSession, user_id: str
    ) -> Optional[models.User]:
        """
        Fetch a user by ID including role, permissions, and status.

        Args:
            db: Async session
            user_id: User ID

        Returns:
            User with preloaded role permissions
        """
        result = await db.execute(
            select(models.User)
            .where(models.User.id == user_id)
            .options(
                selectinload(models.User.status),
                selectinload(models.User.role).selectinload(models.Role.permissions),
            )
        )
        return result.unique().scalar_one_or_none()


    async def get_user_with_details(
        self, db: AsyncSession, user_id: str
    ) -> Optional[models.User]:
        """
        Fetch a user and all related profile info.

        Args:
            db: Async DB session
            user_id: User ID

        Returns:
            User object with all related details loaded
        """
        result = await db.execute(
            select(models.User)
            .where(models.User.id == user_id)
            .options(
                selectinload(models.User.role),
                selectinload(models.User.status),
                selectinload(models.User.customer_details).selectinload(
                    models.CustomerDetails.address
                ),
                selectinload(models.User.customer_details).selectinload(
                    models.CustomerDetails.tag
                ),
                selectinload(models.User.admin_details),
            )
        )
        return result.scalar_one_or_none()


    async def create_user(
        self,
        db: AsyncSession,
        *,
        user_in: schemas.UserCreate,
        user_id: str,
        role_id: int,
        status_id: int,
        referral_code: Optional[str] = None
    ) -> models.User:
        """
        Create a new user entry with referral code generation and processing.

        Args:
            db: DB session
            user_in: UserCreate schema
            user_id: Assigned UUID
            role_id: Role FK
            status_id: Status FK
            referral_code: Optional referral code from another user

        Returns:
            Created User object
        """
        import random
        import string

        new_referral_code = None
        while True:
            new_referral_code = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )
            existing = await self.get_by_referral_code(db, new_referral_code)
            if not existing:
                break

        referred_by_id = None
        if referral_code:
            referrer = await self.get_by_referral_code(db, referral_code)
            if referrer:
                referred_by_id = referrer.id

        db_user = models.User(
            id=user_id,
            username=user_in.username,
            email=user_in.email,
            password=user_in.password,
            role_id=role_id,
            status_id=status_id,
            referral_code=new_referral_code,
            referred_by=referred_by_id,
            referral_count=0,
            total_referrals=0,
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user


    async def update_user(self, db: AsyncSession, db_user: models.User) -> models.User:
        """
        Update user object.

        Args:
            db: DB session
            db_user: Updated User instance

        Returns:
            Updated user instance
        """
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user


    async def get_admin_details(
        self, db: AsyncSession, user_id: str
    ) -> Optional[models.AdminDetails]:
        """
        Get admin details for a user.

        Args:
            db: DB session
            user_id: User ID

        Returns:
            AdminDetails object or None
        """
        result = await db.execute(
            select(models.AdminDetails).where(models.AdminDetails.admin_id == user_id)
        )
        return result.scalar_one_or_none()


    async def create_admin_details(
        self, db: AsyncSession, user_id: str, data: schemas.AdminDetailsUpdate, profile_url: Optional[str] = None
    ) -> models.AdminDetails:
        """
        Create admin details for a user.

        Args:
            db: DB session
            user_id: User ID
            data: Admin details schema
            profile_url: Optional profile URL to set

        Returns:
            Created AdminDetails record
        """
        db_admin = models.AdminDetails(admin_id=user_id, **data.model_dump())

        if profile_url is not None:
            db_admin.profile_url = profile_url
        
        db.add(db_admin)
        await db.commit()
        await db.refresh(db_admin)
        return db_admin


    async def update_admin_details(
        self, db: AsyncSession, db_admin: models.AdminDetails, data: schemas.AdminDetailsUpdate, profile_url: Optional[str] = None
    ) -> models.AdminDetails:
        """
        Update existing admin profile details.

        Args:
            db: DB session
            db_admin: Existing AdminDetails ORM object
            data: Update schema
            profile_url: Optional profile URL to update

        Returns:
            Updated AdminDetails object
        """
        for key, value in data.model_dump(exclude_none=True).items():
            setattr(db_admin, key, value)
        
        if profile_url is not None:
            setattr(db_admin, 'profile_url', profile_url)

        await db.commit()
        await db.refresh(db_admin)
        return db_admin


    async def create_address(
        self, db: AsyncSession, address_in: schemas.AddressBase
    ) -> models.Address:
        """
        Create a new address record.

        Args:
            db: DB session
            address_in: AddressBase schema

        Returns:
            Created Address object
        """
        db_address = models.Address(**address_in.model_dump())
        db.add(db_address)
        await db.flush()
        await db.refresh(db_address)
        return db_address


    async def update_address(
        self, db: AsyncSession, db_address: models.Address, address_in: schemas.AddressBase
    ) -> models.Address:
        """
        Update a customer's address.

        Args:
            db: DB session
            db_address: Existing Address ORM object
            address_in: Address update schema

        Returns:
            Updated Address object
        """
        for key, value in address_in.model_dump().items():
            setattr(db_address, key, value)

        await db.flush()
        await db.refresh(db_address)
        return db_address


    async def get_customer_details(
        self, db: AsyncSession, user_id: str
    ) -> Optional[models.CustomerDetails]:
        """
        Get customer details with address and tag.

        Args:
            db: DB session
            user_id: User ID

        Returns:
            CustomerDetails object or None
        """
        result = await db.execute(
            select(models.CustomerDetails)
            .where(models.CustomerDetails.customer_id == user_id)
            .options(
                selectinload(models.CustomerDetails.address),
                selectinload(models.CustomerDetails.tag),
            )
        )
        return result.scalar_one_or_none()


    async def create_customer_details(
        self, db: AsyncSession, details_in: Dict[str, Any]
    ) -> models.CustomerDetails:
        """
        Create customer details from provided dict.

        Args:
            db: DB session
            details_in: Dict containing user_id, address_id, tag_id

        Returns:
            Created CustomerDetails object
        """
        db_customer = models.CustomerDetails(**details_in)
        db.add(db_customer)

        await db.commit()
        await db.refresh(db_customer)
        await db.refresh(db_customer, attribute_names=["address", "tag"])
        return db_customer


    async def update_customer_details(
        self, db: AsyncSession, db_customer: models.CustomerDetails, details_in: Dict[str, Any]
    ) -> models.CustomerDetails:
        """
        Update customer details.

        Args:
            db: DB session
            db_customer: Existing CustomerDetails ORM object
            details_in: Dict of updated values

        Returns:
            Updated CustomerDetails object
        """
        for key, value in details_in.items():
            setattr(db_customer, key, value)

        await db.commit()
        await db.refresh(db_customer)
        await db.refresh(db_customer, attribute_names=["address", "tag"])
        return db_customer


    async def get_tag_by_name(self, db: AsyncSession, tag_name: str) -> Optional[models.Tag]:
        """
        Get a tag by name.

        Args:
            db: DB session
            tag_name: Tag name

        Returns:
            Tag object if exists else None
        """
        result = await db.execute(select(models.Tag).where(models.Tag.name == tag_name))
        return result.scalar_one_or_none()


    async def get_by_referral_code(
        self, db: AsyncSession, referral_code: str
    ) -> Optional[models.User]:
        """
        Fetch user by referral code.

        Args:
            db: Async DB session
            referral_code: Referral code string

        Returns:
            User if exists, else None
        """
        result = await db.execute(
            select(models.User)
            .where(models.User.referral_code == referral_code)
            .options(selectinload(models.User.role), selectinload(models.User.status))
        )
        return result.scalar_one_or_none()


    async def deduct_referral_count(self, db: AsyncSession, user_id: str, count: int = 3) -> bool:
        """
        Deduct referral count from user for availing delivery benefit.

        Args:
            db: DB session
            user_id: User ID
            count: Number of referrals to deduct

        Returns:
            True if deduction successful, False if insufficient count
        """
        user = await self.get_by_id(db, user_id)
        if not user or user.referral_count < count:
            return False

        user.referral_count -= count
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return True


    async def refund_referral_count(self, db: AsyncSession, user_id: str, count: int = 3) -> None:
        """
        Refund referral count to user if booking with benefit is cancelled or rejected.

        Args:
            db: DB session
            user_id: User ID
            count: Number of referrals to refund

        Returns:
            None
        """
        user = await self.get_by_id(db, user_id)
        if user:
            user.referral_count += count
            db.add(user)
            await db.commit()
            await db.refresh(user)


user_crud = UserCRUD()