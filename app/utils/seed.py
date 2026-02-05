import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
import pandas as pd
import json
from dateutil import parser
import random
import string


from app.core.config import settings
from app.auth.security import get_password_hash
from app.utils.id_utils import generate_prefixed_id
from app import models
from app.services.embedding_services import embedding_service
from app.utils.seed_data import (
    STATUSES,
    TAGS,
    CATEGORIES,
    FUEL_TYPES,
    CAPACITIES,
    COLORS,
    FEATURES,
    PERMISSIONS,
    CAR_MODELS_DATA,
    CARS_DATA,
    SAMPLE_USERS,
    HOMEPAGE_DATA,
    TERMS_DATA,
    HELPCENTRE_DATA,
    PRIVACY_POLICY_DATA,
    FAQ_DATA,
    ADMIN_HELPCENTRE_DATA,
)
from app.models.enums import PaymentMethod, PaymentType, StatusEnum, Tags, RoleName
from app.crud import content_crud


BOOKINGS_CSV = "app/utils/seed_data/bookings.csv"
PAYMENTS_CSV = "app/utils/seed_data/payments.csv"
REVIEWS_CSV = "app/utils/seed_data/reviews.csv"
LOCATION_CSV = "app/utils/seed_data/locations.csv"


def dt(v):
    return parser.parse(v) if pd.notna(v) else None


logger = logging.getLogger(__name__)


# -----------------------------
# GENERIC SEEDER HELPER
# -----------------------------
async def _seed_model(
    db: AsyncSession, model: type[models.Base], data: list, name_attr: str
):
    """
    Generic seeder for simple lookup tables.

    Args:
        db (AsyncSession): Active DB session.
        model (type[models.Base]): SQLAlchemy model class.
        data (list): List of values to seed.
        name_attr (str): Attribute name in the model to check/insert.

    Returns:
        None
    """
    existing = await db.execute(select(getattr(model, name_attr)))
    existing_items = set(existing.scalars().all())

    for item in data:
        if item not in existing_items:
            db.add(model(**{name_attr: item}))

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Error seeding {model.__name__}: {e}")


async def seed_statuses(db: AsyncSession):
    """
    Seeds the statuses.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        dict: A mapping of status names to Status model instances.
    """
    logger.info("Seeding statuses...")
    existing = await db.execute(select(models.Status))
    status_map = {s.name: s for s in existing.scalars().all()}

    for status_name in STATUSES:
        if status_name not in status_map:
            try:
                new_status = models.Status(name=status_name)
                db.add(new_status)
                await db.commit()
                await db.refresh(new_status)
                status_map[status_name] = new_status
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to seed status {status_name}: {e}")

    return status_map


async def seed_lookups(db: AsyncSession):
    """ 
    Seeds lookup tables like Tags, Categories, Fuel Types, Capacities, Colors, and Features.
    
    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding lookups...")
    await _seed_model(db, models.Tag, TAGS, "name")
    await _seed_model(db, models.Category, CATEGORIES, "category_name")
    await _seed_model(db, models.Fuel, FUEL_TYPES, "fuel_name")
    await _seed_model(db, models.Capacity, CAPACITIES, "capacity_value")
    await _seed_model(db, models.Color, COLORS, "color_name")
    await _seed_model(db, models.Feature, FEATURES, "feature_name")


async def seed_permissions(db: AsyncSession):
    """
    Seeds permissions.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        dict: A mapping of "name:scope" to Permission model instances.
    """
    logger.info("Seeding permissions...")

    existing = await db.execute(select(models.Permission))
    perm_map = {f"{p.name}:{p.scope}": p for p in existing.scalars().all()}

    for role, perms in PERMISSIONS.items():
        for name, scope in perms:
            key = f"{name}:{scope}"
            if key not in perm_map:
                try:
                    p = models.Permission(name=name, scope=scope)
                    db.add(p)
                    await db.commit()
                    await db.refresh(p)
                    perm_map[key] = p
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Failed to seed permission {key}: {e}")

    return perm_map


async def seed_roles(db: AsyncSession, perm_map: dict):
    """ 
    Seeds roles and assigns permissions.

    Args:
        db (AsyncSession): Active DB session.
        perm_map (dict): A mapping of "name:scope" to Permission model instances.

    Returns:
        tuple: Created Role model instances for Admin, Customer, and System.
    """
    logger.info("Seeding roles...")

    async def get_or_create(role_enum, perm_keys):
        res = await db.execute(
            select(models.Role)
            .options(selectinload(models.Role.permissions))
            .where(models.Role.name == role_enum)
        )
        role = res.scalar_one_or_none()

        perms = [perm_map[k] for k in perm_keys if k in perm_map]

        if not role:
            role = models.Role(name=role_enum)
            role.permissions = perms
            db.add(role)
            await db.commit()
        else:
            role.permissions = perms
            await db.commit()

        return role

    admin_role = await get_or_create(
        RoleName.ADMIN, [f"{n}:{s}" for n, s in PERMISSIONS["ADMIN"]]
    )
    customer_role = await get_or_create(
        RoleName.CUSTOMER, [f"{n}:{s}" for n, s in PERMISSIONS["CUSTOMER"]]
    )
    system_role = await get_or_create(RoleName.SYSTEM, [])

    return admin_role, customer_role, system_role


async def seed_core_users(db: AsyncSession, admin_role, system_role, active_status):
    """
    Seeds core users: system user and super admin.

    Args:
        db (AsyncSession): Active DB session.
        admin_role (models.Role): Admin role instance.
        system_role (models.Role): System role instance.
        active_status (models.Status): Active status instance.

    Returns:
        None
    """
    logger.info("Seeding system and admin users...")

    res = await db.execute(
        select(models.User).where(models.User.role_id == system_role.id)
    )
    if not res.scalar_one_or_none():
        try:
            import random
            import string

            sys_id = await generate_prefixed_id(db, "U")

            # Generate unique referral code
            referral_code = None
            while True:
                referral_code = "".join(
                    random.choices(string.ascii_uppercase + string.digits, k=8)
                )
                existing = await db.execute(
                    select(models.User).where(
                        models.User.referral_code == referral_code
                    )
                )
                if not existing.scalar_one_or_none():
                    break

            user = models.User(
                id=sys_id,
                username="system",
                email="system@internal.app",
                password=get_password_hash("#SYSTEM_USER"),
                role_id=system_role.id,
                status_id=active_status.id,
                referral_code=referral_code,
                referral_count=0,
                total_referrals=0,
                created_at=dt("2025-11-01 01:00:00+05:30"),
            )
            db.add(user)

            system_details = models.AdminDetails(
                admin_id=sys_id,
                name="SYSTEM",
                phone=f"0000000000",
                profile_url="assets/images/profile.png",
            )

            db.add(system_details)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating system user: {e}")

    # Super Admin
    res = await db.execute(
        select(models.User).where(models.User.email == settings.SUPER_ADMIN_EMAIL)
    )
    if not res.scalar_one_or_none():
        try:
            import random
            import string

            admin_id = await generate_prefixed_id(db, "U")

            # Generate unique referral code
            referral_code = None
            while True:
                referral_code = "".join(
                    random.choices(string.ascii_uppercase + string.digits, k=8)
                )
                existing = await db.execute(
                    select(models.User).where(
                        models.User.referral_code == referral_code
                    )
                )
                if not existing.scalar_one_or_none():
                    break

            admin = models.User(
                id=admin_id,
                username=settings.SUPER_ADMIN_USERNAME,
                email=settings.SUPER_ADMIN_EMAIL,
                password=get_password_hash(settings.SUPER_ADMIN_PASSWORD),
                role_id=admin_role.id,
                status_id=active_status.id,
                referral_code=referral_code,
                referral_count=0,
                total_referrals=0,
                created_at=dt("2025-11-01 01:00:00+05:30"),
            )
            db.add(admin)

            admin_details = models.AdminDetails(
                admin_id=admin.id,
                name=settings.SUPER_ADMIN_NAME,
                phone=f"1000000000",
                profile_url="assets/images/profile.png",
            )
            db.add(admin_details)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating super admin: {e}")


async def seed_sample_customers(db: AsyncSession, customer_role, active_status):
    """
    Seeds sample customer users.

    Args:
        db (AsyncSession): Active DB session.
        customer_role (models.Role): Customer role instance.
        active_status (models.Status): Active status instance.

    Returns:
        None
    """
    logger.info("Seeding sample customers...")

    res = await db.execute(select(models.Tag).where(models.Tag.name == Tags.TRAVELER))
    traveler_tag = res.scalar_one()

    user1_id = "U0003"

    for idx, user_data in enumerate(SAMPLE_USERS, start=1):
        if len(user_data) == 4:
            uname, email, pwd, has_details = user_data
        else:
            uname, email, pwd = user_data
            has_details = True 
        
        res = await db.execute(select(models.User).where(models.User.email == email))
        if res.scalar_one_or_none():
            continue

        try:
            user_id = await generate_prefixed_id(db, "U")

            # Generate unique referral code
            referral_code = None
            while True:
                referral_code = "".join(
                    random.choices(string.ascii_uppercase + string.digits, k=8)
                )
                existing = await db.execute(
                    select(models.User).where(
                        models.User.referral_code == referral_code
                    )
                )
                if not existing.scalar_one_or_none():
                    break

            # Users 3, 4, 5 (indices 3, 4, 5) are referred by user1
            referred_by_id = user1_id if idx >= 3 and idx <= 5 and user1_id else None

            user_obj = models.User(
                id=user_id,
                username=uname,
                email=email,
                password=get_password_hash(pwd),
                role_id=customer_role.id,
                status_id=active_status.id,
                referral_code=referral_code,
                referred_by=referred_by_id,
                referral_count=0,
                total_referrals=3 if user_id == user1_id else 0,
                created_at=dt("2025-11-01 01:00:00+05:30"),
            )

            db.add(user_obj)
            await db.commit()
            await db.refresh(user_obj)

            # Only create customer details if has_details is True
            if has_details:
                cust_details = models.CustomerDetails(
                    customer_id=user_obj.id,
                    name=uname,
                    phone=f"987654321{idx}",
                    dob="2000-01-01",
                    gender="Male",
                    profile_url="assets/images/profile.png",
                    aadhaar_no=f"12341234123{idx}",
                    license_no=f"DL12345678{idx}",
                    aadhaar_front_url="assets/images/aadhaar_front.png",
                    license_front_url="assets/images/license_front.png",
                    is_verified=True,
                    tag_id=traveler_tag.id,
                    rookie_benefit_used=True,
                    address=models.Address(
                        address_line="Sample Street",
                        area="Sample Area",
                        state="Tamil Nadu",
                        country="India",
                    ),
                )

                db.add(cust_details)
                await db.commit()

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to seed customer {uname}: {e}")


async def seed_car_models(db: AsyncSession):
    """
    Seeds car models.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding car models...")

    for model_data in CAR_MODELS_DATA:
        # Check if car model already exists
        res = await db.execute(
            select(models.CarModel).where(
                models.CarModel.brand == model_data["brand"],
                models.CarModel.model == model_data["model"],
            )
        )

        if res.scalar_one_or_none():
            continue

        # Get category
        res = await db.execute(
            select(models.Category).where(
                models.Category.category_name == model_data["category"]
            )
        )
        category = res.scalar_one()

        # Get fuel type
        res = await db.execute(
            select(models.Fuel).where(models.Fuel.fuel_name == model_data["fuel"])
        )
        fuel = res.scalar_one()

        # Get capacity
        res = await db.execute(
            select(models.Capacity).where(
                models.Capacity.capacity_value == model_data["capacity"]
            )
        )
        capacity = res.scalar_one()

        # Get or create features
        features = []
        for feature_name in model_data["features"]:
            res = await db.execute(
                select(models.Feature).where(
                    models.Feature.feature_name == feature_name
                )
            )
            feature = res.scalar_one_or_none()
            if feature:
                features.append(feature)

        # Create car model
        try:
            car_model = models.CarModel(
                brand=model_data["brand"],
                model=model_data["model"],
                category_id=category.id,
                fuel_id=fuel.id,
                capacity_id=capacity.id,
                transmission_type=model_data["transmission_type"],
                mileage=model_data["mileage"],
                rental_per_hr=model_data["rental_per_hr"],
                dynamic_rental_price=model_data["dynamic_rental_price"],
                kilometer_limit_per_hr=model_data["kilometer_limit_per_hr"],
                features=features,
            )

            db.add(car_model)
            await db.commit()
            await db.refresh(car_model)

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Error seeding car model {model_data['brand']} {model_data['model']}: {e}"
            )


async def seed_individual_cars(db: AsyncSession):
    """
    Seeds individual cars.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding individual cars...")

    # Get required lookup data
    res = await db.execute(
        select(models.User).where(models.User.username == settings.SUPER_ADMIN_USERNAME)
    )
    admin_user = res.scalar_one()

    res = await db.execute(
        select(models.Status).where(models.Status.name == StatusEnum.ACTIVE)
    )
    active_status = res.scalar_one()

    res = await db.execute(
        select(models.Status).where(models.Status.name == StatusEnum.INACTIVE)
    )
    inactive_status = res.scalar_one()

    for car_data in CARS_DATA:
        # Check if car already exists
        res = await db.execute(
            select(models.Car).where(models.Car.car_no == car_data["car_no"])
        )
        existing_car = res.scalar_one_or_none()

        if existing_car:
            continue

        # Get car model
        res = await db.execute(
            select(models.CarModel).where(
                models.CarModel.brand == car_data["car_model"]["brand"],
                models.CarModel.model == car_data["car_model"]["model"],
            )
        )
        car_model = res.scalar_one()

        # Get color
        res = await db.execute(
            select(models.Color).where(models.Color.color_name == car_data["color"])
        )
        color = res.scalar_one()

        # Get status
        status = (
            active_status
            if car_data["status"] == StatusEnum.ACTIVE
            else inactive_status
        )

        # Create individual car
        try:
            car = models.Car(
                car_no=car_data["car_no"],
                car_model_id=car_model.id,
                color_id=color.id,
                manufacture_year=car_data["manufacture_year"],
                image_urls=car_data["image_urls"],
                last_serviced_date=datetime.fromisoformat(
                    car_data["last_serviced_date"].replace("Z", "+00:00")
                ),
                service_frequency_months=3,
                insured_till=datetime.fromisoformat(
                    car_data["insured_till"].replace("Z", "+00:00")
                ),
                pollution_expiry=datetime.fromisoformat(
                    car_data["pollution_expiry"].replace("Z", "+00:00")
                ),
                status_id=status.id,
                created_by=admin_user.id,
            )

            db.add(car)
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error seeding car {car_data['car_no']}: {e}")


async def seed_completed_bookings_from_csv(db: AsyncSession):
    """
    Seeds completed bookings from CSV files.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding completed bookings from CSV...")

    bookings_df = pd.read_csv(BOOKINGS_CSV)
    payments_df = pd.read_csv(PAYMENTS_CSV)
    reviews_df = pd.read_csv(REVIEWS_CSV)
    locations_df = pd.read_csv(LOCATION_CSV)

    for _, row in locations_df.iterrows():
        try:

            location = models.Location(
                longitude=row["longitude"],
                latitude=row["latitude"],
                address=row["address"] if pd.notna(row["address"]) else None,
            )
            db.add(location)
            await db.flush()
        except Exception as e:
            await db.rollback()
            logger.error(f"Location row failed → {e}")
            raise

    for _, row in bookings_df.iterrows():
        try:
            booking = models.Booking(
                car_id=row["car_id"],
                start_date=dt(row["start_date"]),
                end_date=dt(row["end_date"]),
                delivery_id=row["delivery_id"],
                pickup_id=row["pickup_id"],
                booking_status_id=row["booking_status_id"],
                payment_status_id=row["payment_status_id"],
                booked_by=row["booked_by"],
                remarks=row["remarks"],
                return_requested_at=(
                    dt(row["return_requested_at"])
                    if pd.notna(row["return_requested_at"])
                    else None
                ),
                delivery_video_url=(
                    row["delivery_video_url"]
                    if pd.notna(row["delivery_video_url"])
                    else None
                ),
                delivery_otp=(
                    str(int(row["delivery_otp"]))
                    if pd.notna(row["delivery_otp"])
                    else None
                ),
                delivery_otp_generated_at=(
                    dt(row["delivery_otp_generated_at"])
                    if pd.notna(row["delivery_otp_generated_at"])
                    else None
                ),
                delivery_otp_verified=(
                    row["delivery_otp_verified"]
                    if pd.notna(row["delivery_otp_verified"])
                    else False
                ),
                delivery_otp_verified_at=(
                    dt(row["delivery_otp_verified_at"])
                    if pd.notna(row["delivery_otp_verified_at"])
                    else None
                ),
                start_kilometers=(
                    row["start_kilometers"]
                    if pd.notna(row["start_kilometers"])
                    else None
                ),
                pickup_video_url=(
                    row["pickup_video_url"]
                    if pd.notna(row["pickup_video_url"])
                    else None
                ),
                pickup_otp=(
                    str(int(row["pickup_otp"])) if pd.notna(row["pickup_otp"]) else None
                ),
                pickup_otp_generated_at=(
                    dt(row["pickup_otp_generated_at"])
                    if pd.notna(row["pickup_otp_generated_at"])
                    else None
                ),
                pickup_otp_verified=(
                    row["pickup_otp_verified"]
                    if pd.notna(row["pickup_otp_verified"])
                    else False
                ),
                pickup_otp_verified_at=(
                    dt(row["pickup_otp_verified_at"])
                    if pd.notna(row["pickup_otp_verified_at"])
                    else None
                ),
                end_kilometers=(
                    row["end_kilometers"] if pd.notna(row["end_kilometers"]) else None
                ),
                cancelled_at=(
                    dt(row["cancelled_at"]) if pd.notna(row["cancelled_at"]) else None
                ),
                cancelled_by=(
                    row["cancelled_by"] if pd.notna(row["cancelled_by"]) else None
                ),
                cancellation_reason=(
                    row["cancellation_reason"]
                    if pd.notna(row["cancellation_reason"])
                    else None
                ),
                referral_benefit=row["referral_benefit"],
                created_at=dt(row["created_at"]),
                payment_summary=json.loads(row["payment_summary"]),
            )

            db.add(booking)
            await db.flush()

        except Exception as e:
            await db.rollback()
            logger.error(f"Booking row failed → {e}")
            raise

    for _, row in payments_df.iterrows():
        try:
            db.add(
                models.Payment(
                    booking_id=row["booking_id"],
                    amount_inr=row["amount_inr"],
                    payment_method=PaymentMethod[row["payment_method"]],
                    payment_type=PaymentType[row["payment_type"]],
                    status_id=row["status_id"],
                    transaction_id=row["transaction_id"],
                    razorpay_order_id=row["razorpay_order_id"],
                    razorpay_payment_id=row["razorpay_payment_id"],
                    razorpay_signature=row["razorpay_signature"],
                    remarks=row["remarks"],
                    created_at=dt(row["created_at"]),
                )
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Payment row failed → {e}")
            raise

    for _, row in reviews_df.iterrows():
        try:
            db.add(
                models.Review(
                    booking_id=row["booking_id"],
                    car_id=row["car_id"],
                    rating=row["rating"],
                    remarks=row["remarks"],
                    created_by=row["created_by"],
                    created_at=dt(row["created_at"]),
                )
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Review row failed → {e}")
            raise

    await db.commit()


async def seed_terms(db: AsyncSession):
    """
    Seeds terms.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding terms and conditions...")

    # Check if terms already exists
    existing_terms = await content_crud.get_active_terms(db)
    if existing_terms:
        logger.info("Active terms already exists, skipping...")
        return

    try:
        # Get admin user for last_modified_by
        res = await db.execute(
            select(models.User).where(
                models.User.username == settings.SUPER_ADMIN_USERNAME
            )
        )
        admin_user = res.scalar_one()

        # Prepare terms data
        terms_data = TERMS_DATA.copy()
        terms_data["last_modified_by"] = admin_user.id
        terms_data["effective_from"] = datetime.now(timezone.utc)
        sections_data = terms_data.pop("sections", [])

        # Create terms with sections
        await content_crud.create_terms_with_sections(db, terms_data, sections_data)

    except Exception as e:
        logger.error(f"Error seeding terms: {e}")
        await db.rollback()


async def seed_help_centre(db: AsyncSession):
    """
    Seeds help centre.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding help centre...")

    # Check if help centre already exists
    existing_help = await content_crud.get_active_help_centre(db)
    if existing_help:
        logger.info("Active help centre already exists, skipping...")
        return

    try:
        # Get admin user for last_modified_by
        res = await db.execute(
            select(models.User).where(
                models.User.username == settings.SUPER_ADMIN_USERNAME
            )
        )
        admin_user = res.scalar_one()

        # Prepare help centre data
        help_data = HELPCENTRE_DATA.copy()
        help_data["last_modified_by"] = admin_user.id
        help_data["effective_from"] = datetime.now(timezone.utc)
        sections_data = help_data.pop("sections", [])

        # Create help centre with sections
        await content_crud.create_help_centre_with_sections(
            db, help_data, sections_data
        )

    except Exception as e:
        logger.error(f"Error seeding help centre: {e}")
        await db.rollback()


async def seed_privacy_policy(db: AsyncSession):
    """
    Seeds privacy policy.
    
    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding privacy policy...")

    # Check if privacy policy already exists
    existing_privacy = await content_crud.get_active_privacy_policy(db)
    if existing_privacy:
        logger.info("Active privacy policy already exists, skipping...")
        return

    try:
        # Get admin user for last_modified_by
        res = await db.execute(
            select(models.User).where(
                models.User.username == settings.SUPER_ADMIN_USERNAME
            )
        )
        admin_user = res.scalar_one()

        # Prepare privacy policy data
        privacy_data = PRIVACY_POLICY_DATA.copy()
        privacy_data["last_modified_by"] = admin_user.id
        privacy_data["effective_from"] = datetime.now(timezone.utc)
        sections_data = privacy_data.pop("sections", [])

        # Create privacy policy with sections
        await content_crud.create_privacy_policy_with_sections(
            db, privacy_data, sections_data
        )

    except Exception as e:
        logger.error(f"Error seeding privacy policy: {e}")
        await db.rollback()


async def seed_faq(db: AsyncSession):
    """
    Seeds FAQ.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding FAQ...")

    # Check if FAQ already exists
    existing_faq = await content_crud.get_active_faq(db)
    if existing_faq:
        logger.info("Active FAQ already exists, skipping...")
        return

    try:
        # Get admin user for last_modified_by
        res = await db.execute(
            select(models.User).where(
                models.User.username == settings.SUPER_ADMIN_USERNAME
            )
        )
        admin_user = res.scalar_one()

        # Prepare FAQ data
        faq_data = FAQ_DATA.copy()
        faq_data["last_modified_by"] = admin_user.id
        faq_data["effective_from"] = datetime.now(timezone.utc)
        sections_data = faq_data.pop("sections", [])

        # Create FAQ with sections
        await content_crud.create_faq_with_sections(db, faq_data, sections_data)

    except Exception as e:
        logger.error(f"Error seeding FAQ: {e}")
        await db.rollback()


async def seed_admin_help_centre(db: AsyncSession):
    """
    Seeds admin help centre.
    
    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding admin help centre...")

    # Check if admin help centre already exists
    existing_admin_help = await content_crud.get_active_admin_help_centre(db)
    if existing_admin_help:
        logger.info("Active admin help centre already exists, skipping...")
        return

    try:
        # Get admin user for last_modified_by
        res = await db.execute(
            select(models.User).where(
                models.User.username == settings.SUPER_ADMIN_USERNAME
            )
        )
        admin_user = res.scalar_one()

        # Prepare admin help centre data
        admin_help_data = ADMIN_HELPCENTRE_DATA.copy()
        admin_help_data["last_modified_by"] = admin_user.id
        admin_help_data["effective_from"] = datetime.now(timezone.utc)
        sections_data = admin_help_data.pop("sections", [])

        # Create admin help centre with sections
        await content_crud.create_admin_help_centre_with_sections(
            db, admin_help_data, sections_data
        )

    except Exception as e:
        logger.error(f"Error seeding admin help centre: {e}")
        await db.rollback()


async def seed_homepage(db: AsyncSession):
    """
    Seeds homepage content.
    
    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Seeding homepage content...")

    try:
        # Check if homepage already exists
        res = await db.execute(select(models.HomePage))
        existing_homepage = res.scalar_one_or_none()

        if existing_homepage:
            logger.info("Homepage already exists, skipping...")
            return

        # Get admin user
        res = await db.execute(
            select(models.User).where(
                models.User.username == settings.SUPER_ADMIN_USERNAME
            )
        )
        admin_user = res.scalar_one()

        # Get active status
        res = await db.execute(
            select(models.Status).where(models.Status.name == StatusEnum.ACTIVE)
        )
        active_status = res.scalar_one()

        # Create homepage main object
        homepage = models.HomePage(
            is_active=HOMEPAGE_DATA["is_active"],
            hero_section=HOMEPAGE_DATA["hero_section"],
            about_section=HOMEPAGE_DATA["about_section"],
            promotions_section=HOMEPAGE_DATA["promotions_section"],
            top_rental_section=HOMEPAGE_DATA["top_rental_section"],
            explore_cars_section=HOMEPAGE_DATA["explore_cars_section"],
            reviews_section=HOMEPAGE_DATA["reviews_section"],
            contact_section=HOMEPAGE_DATA["contact_section"],
            footer_section=HOMEPAGE_DATA["footer_section"],
            last_modified_by=admin_user.id,
        )

        db.add(homepage)
        await db.flush()  # Generate homepage.id before adding children

        # Promotions
        for promo_data in HOMEPAGE_DATA["promotions"]:
            promotion = models.HomePagePromotion(homepage_id=homepage.id, **promo_data)
            db.add(promotion)

        # Top Rentals
        for rental_data in HOMEPAGE_DATA["top_rentals"]:
            rental = models.HomePageTopRental(homepage_id=homepage.id, **rental_data)
            db.add(rental)

        # Explore Cars Categories
        for cat_data in HOMEPAGE_DATA["explore_cars_categories"]:
            cat = models.HomePageCarCategory(homepage_id=homepage.id, **cat_data)
            db.add(cat)

        # Featured Reviews
        for review_data in HOMEPAGE_DATA["featured_reviews"]:
            review = models.HomePageFeaturedReview(
                homepage_id=homepage.id, **review_data
            )
            db.add(review)

        # Contact FAQs
        for faq_data in HOMEPAGE_DATA["contact_faqs"]:
            faq = models.HomePageContactFAQ(homepage_id=homepage.id, **faq_data)
            db.add(faq)

        await db.commit()

    except Exception as e:
        await db.rollback()
        logger.error(f"Error seeding homepage content: {e}")


async def seed_data(db: AsyncSession):
    """
    Main function to seed all necessary data into the database.

    Args:
        db (AsyncSession): Active DB session.

    Returns:
        None
    """
    logger.info("Starting system seeding...")

    # Seed basic data
    await seed_statuses(db)
    await seed_lookups(db)

    # Seed permissions and roles
    perm_map = await seed_permissions(db)
    admin_role, customer_role, system_role = await seed_roles(db, perm_map)

    # Get ACTIVE status
    res = await db.execute(
        select(models.Status).where(models.Status.name == StatusEnum.ACTIVE)
    )
    active_status = res.scalar_one()

    # Seed users
    await seed_core_users(db, admin_role, system_role, active_status)
    await seed_sample_customers(db, customer_role, active_status)

    # Seed cars
    await seed_car_models(db)
    await seed_individual_cars(db)

    # Small delay to ensure all data is committed
    await asyncio.sleep(0.1)

    # Seed completed bookings with payments and reviews
    await seed_completed_bookings_from_csv(db)

    # Seed content pages
    await seed_terms(db)
    await seed_help_centre(db)
    await seed_privacy_policy(db)
    await seed_faq(db)
    await seed_admin_help_centre(db)

    # Seed homepage
    await seed_homepage(db)

    await embedding_service.embed_all_cars(db)
    await embedding_service.embed_all_documents(db)

    logger.info("Seeding completed successfully!")
