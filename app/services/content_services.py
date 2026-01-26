from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import sqlalchemy.exc


from app import models, schemas
from app.crud import content_crud
from app.utils.exception_utils import NotFoundException


class ContentService:
    """
    Service layer for content management operations including terms, help centre, privacy policy, FAQ, and homepage content management.
    """
    async def get_terms(self, db: AsyncSession, terms_id: int) -> models.TermsMaster:
        """
        Retrieve specific terms and conditions document by ID.

        Args:
            db: Database session
            terms_id: Terms document unique identifier

        Returns:
            TermsMaster object with all sections and contents
        """
        db_terms = await content_crud.get_terms_by_id(db, terms_id)
        if not db_terms:
            raise NotFoundException("Terms not found")
        return db_terms


    async def get_active_terms(self, db: AsyncSession) -> Optional[models.TermsMaster]:
        """
        Retrieve the currently active terms and conditions.

        Args:
            db: Database session

        Returns:
            Active TermsMaster object if found
        """
        db_terms = await content_crud.get_active_terms(db)
        if not db_terms:
            raise NotFoundException("No active terms found")
        return db_terms


    async def list_terms(
        self, db: AsyncSession, skip: int, limit: int
    ) -> schemas.PaginatedTermsResponse:
        """
        Retrieve paginated list of all terms and conditions documents.

        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            Paginated response containing terms documents
        """
        items, total = await content_crud.get_all_terms_paginated(db, skip, limit)
        return schemas.PaginatedTermsResponse(total=total, items=items)


    async def create_terms(
        self,
        db: AsyncSession,
        terms_in: schemas.TermsMasterCreate,
        creator: models.User,
    ) -> models.TermsMaster:
        """
        Create a new terms and conditions document.

        Args:
            db: Database session
            terms_in: Terms creation data including sections and contents
            creator: User creating the terms document

        Returns:
            Newly created TermsMaster object with all relationships loaded
        """
        terms_data = terms_in.model_dump()
        terms_data["last_modified_by"] = creator.id
        sections_data = terms_data.pop("sections", [])

        db_terms = await content_crud.create_terms_with_sections(
            db, terms_data, sections_data
        )

        return await content_crud.get_terms_by_id(db, db_terms.id)


    async def update_terms(
        self, db: AsyncSession, terms_id: int, terms_in: schemas.TermsMasterUpdate
    ) -> models.TermsMaster:
        """
        Update an existing terms and conditions document.

        Args:
            db: Database session
            terms_id: Terms document unique identifier to update
            terms_in: Updated terms data

        Returns:
            Updated TermsMaster object with all relationships loaded
        """
        db_terms = await content_crud.get_terms_by_id(db, terms_id)
        if not db_terms:
            raise NotFoundException("Terms not found")

        update_data = terms_in.model_dump(exclude_unset=True)

        if "sections" in update_data:
            sections_data = update_data.pop("sections")
            await content_crud.update_terms_sections(db, terms_id, sections_data)

        if update_data:
            await content_crud.update_terms(db, db_terms, update_data)

        return await content_crud.get_terms_by_id(db, terms_id)


    async def delete_terms(self, db: AsyncSession, terms_id: int) -> None:
        """
        Delete a terms and conditions document.

        Args:
            db: Database session
            terms_id: Terms document unique identifier to delete

        Returns:
            None
        """
        db_terms = await content_crud.get_by_id(db, models.TermsMaster, terms_id)
        if not db_terms:
            raise NotFoundException("Terms not found")
        await content_crud.delete_object(db, db_terms)


    async def set_active_terms(
        self, db: AsyncSession, terms_id: int
    ) -> models.TermsMaster:
        """
        Set specific terms document as active and deactivate all others.

        Args:
            db: Database session
            terms_id: Terms document unique identifier to activate

        Returns:
            Activated TermsMaster object
        """
        db_terms = await content_crud.get_by_id(db, models.TermsMaster, terms_id)
        if not db_terms:
            raise NotFoundException("Terms not found")

        await content_crud.set_active_terms(db, terms_id)
        return await content_crud.get_terms_by_id(db, terms_id)


    async def get_help_centre(
        self, db: AsyncSession, help_id: int
    ) -> models.HelpCentreMaster:
        """
        Retrieve specific help centre document by ID.

        Args:
            db: Database session
            help_id: Help centre document unique identifier

        Returns:
            HelpCentreMaster object with all sections and contents
        """
        db_help = await content_crud.get_help_centre_by_id(db, help_id)
        if not db_help:
            raise NotFoundException("Help centre not found")
        return db_help


    async def get_active_help_centre(
        self, db: AsyncSession
    ) -> Optional[models.HelpCentreMaster]:
        """
        Retrieve the currently active help centre document.

        Args:
            db: Database session

        Returns:
            Active HelpCentreMaster object if found
        """
        db_help = await content_crud.get_active_help_centre(db)
        if not db_help:
            raise NotFoundException("No active help centre found")
        return db_help


    async def list_help_centre(
        self, db: AsyncSession, skip: int, limit: int
    ) -> schemas.PaginatedHelpCentreResponse:
        """
        Retrieve paginated list of all help centre documents.

        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            Paginated response containing help centre documents
        """
        items, total = await content_crud.get_all_help_centre_paginated(db, skip, limit)
        return schemas.PaginatedHelpCentreResponse(total=total, items=items)


    async def create_help_centre(
        self,
        db: AsyncSession,
        help_in: schemas.HelpCentreMasterCreate,
        creator: models.User,
    ) -> models.HelpCentreMaster:
        """
        Create a new help centre document.

        Args:
            db: Database session
            help_in: Help centre creation data including sections and contents
            creator: User creating the help centre document

        Returns:
            Newly created HelpCentreMaster object with all relationships loaded
        """
        help_data = help_in.model_dump()
        help_data["last_modified_by"] = creator.id
        sections_data = help_data.pop("sections", [])

        db_help = await content_crud.create_help_centre_with_sections(
            db, help_data, sections_data
        )
        return await content_crud.get_help_centre_by_id(db, db_help.id)


    async def update_help_centre(
        self, db: AsyncSession, help_id: int, help_in: schemas.HelpCentreMasterUpdate
    ) -> models.HelpCentreMaster:
        """
        Update an existing help centre document.

        Args:
            db: Database session
            help_id: Help centre document unique identifier to update
            help_in: Updated help centre data

        Returns:
            Updated HelpCentreMaster object with all relationships loaded
        """
        db_help = await content_crud.get_help_centre_by_id(db, help_id)
        if not db_help:
            raise NotFoundException("Help centre not found")

        update_data = help_in.model_dump(exclude_unset=True)

        if "sections" in update_data:
            sections_data = update_data.pop("sections")
            await content_crud.update_help_centre_sections(db, help_id, sections_data)

        if update_data:
            await content_crud.update_help_centre(db, db_help, update_data)

        return await content_crud.get_help_centre_by_id(db, help_id)


    async def delete_help_centre(self, db: AsyncSession, help_id: int) -> None:
        """
        Delete a help centre document.

        Args:
            db: Database session
            help_id: Help centre document unique identifier to delete

        Returns:
            None
        """
        db_help = await content_crud.get_by_id(db, models.HelpCentreMaster, help_id)
        if not db_help:
            raise NotFoundException("Help centre not found")
        await content_crud.delete_object(db, db_help)


    async def set_active_help_centre(
        self, db: AsyncSession, help_id: int
    ) -> models.HelpCentreMaster:
        """
        Set specific help centre document as active and deactivate all others.

        Args:
            db: Database session
            help_id: Help centre document unique identifier to activate

        Returns:
            Activated HelpCentreMaster object
        """
        db_help = await content_crud.get_by_id(db, models.HelpCentreMaster, help_id)
        if not db_help:
            raise NotFoundException("Help centre not found")

        await content_crud.set_active_help_centre(db, help_id)
        return await content_crud.get_help_centre_by_id(db, help_id)


    async def get_privacy_policy(
        self, db: AsyncSession, privacy_id: int
    ) -> models.PrivacyPolicyMaster:
        """
        Retrieve specific privacy policy document by ID.

        Args:
            db: Database session
            privacy_id: Privacy policy document unique identifier

        Returns:
            PrivacyPolicyMaster object with all sections and contents
        """
        db_privacy = await content_crud.get_privacy_policy_by_id(db, privacy_id)
        if not db_privacy:
            raise NotFoundException("Privacy policy not found")
        return db_privacy


    async def get_active_privacy_policy(
        self, db: AsyncSession
    ) -> Optional[models.PrivacyPolicyMaster]:
        """
        Retrieve the currently active privacy policy document.

        Args:
            db: Database session

        Returns:
            Active PrivacyPolicyMaster object if found
        """
        db_privacy = await content_crud.get_active_privacy_policy(db)
        if not db_privacy:
            raise NotFoundException("No active privacy policy found")
        return db_privacy


    async def list_privacy_policy(
        self, db: AsyncSession, skip: int, limit: int
    ) -> schemas.PaginatedPrivacyPolicyResponse:
        """
        Retrieve paginated list of all privacy policy documents.

        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            Paginated response containing privacy policy documents
        """
        items, total = await content_crud.get_all_privacy_policy_paginated(
            db, skip, limit
        )
        return schemas.PaginatedPrivacyPolicyResponse(total=total, items=items)


    async def create_privacy_policy(
        self,
        db: AsyncSession,
        privacy_in: schemas.PrivacyPolicyMasterCreate,
        creator: models.User,
    ) -> models.PrivacyPolicyMaster:
        """
        Create a new privacy policy document.

        Args:
            db: Database session
            privacy_in: Privacy policy creation data including sections and contents
            creator: User creating the privacy policy document

        Returns:
            Newly created PrivacyPolicyMaster object with all relationships loaded
        """
        privacy_data = privacy_in.model_dump()
        privacy_data["last_modified_by"] = creator.id
        sections_data = privacy_data.pop("sections", [])

        db_privacy = await content_crud.create_privacy_policy_with_sections(
            db, privacy_data, sections_data
        )
        return await content_crud.get_privacy_policy_by_id(db, db_privacy.id)


    async def update_privacy_policy(
        self,
        db: AsyncSession,
        privacy_id: int,
        privacy_in: schemas.PrivacyPolicyMasterUpdate,
    ) -> models.PrivacyPolicyMaster:
        """
        Update an existing privacy policy document.

        Args:
            db: Database session
            privacy_id: Privacy policy document unique identifier to update
            privacy_in: Updated privacy policy data

        Returns:
            Updated PrivacyPolicyMaster object with all relationships loaded
        """
        db_privacy = await content_crud.get_privacy_policy_by_id(db, privacy_id)
        if not db_privacy:
            raise NotFoundException("Privacy policy not found")

        update_data = privacy_in.model_dump(exclude_unset=True)

        if "sections" in update_data:
            sections_data = update_data.pop("sections")
            await content_crud.update_privacy_policy_sections(
                db, privacy_id, sections_data
            )

        if update_data:
            await content_crud.update_privacy_policy(db, db_privacy, update_data)

        return await content_crud.get_privacy_policy_by_id(db, privacy_id)


    async def delete_privacy_policy(self, db: AsyncSession, privacy_id: int) -> None:
        """
        Delete a privacy policy document.

        Args:
            db: Database session
            privacy_id: Privacy policy document unique identifier to delete

        Returns:
            None
        """
        db_privacy = await content_crud.get_by_id(
            db, models.PrivacyPolicyMaster, privacy_id
        )
        if not db_privacy:
            raise NotFoundException("Privacy policy not found")
        await content_crud.delete_object(db, db_privacy)


    async def set_active_privacy_policy(
        self, db: AsyncSession, privacy_id: int
    ) -> models.PrivacyPolicyMaster:
        """
        Set specific privacy policy document as active and deactivate all others.

        Args:
            db: Database session
            privacy_id: Privacy policy document unique identifier to activate

        Returns:
            Activated PrivacyPolicyMaster object
        """
        db_privacy = await content_crud.get_by_id(
            db, models.PrivacyPolicyMaster, privacy_id
        )
        if not db_privacy:
            raise NotFoundException("Privacy policy not found")

        await content_crud.set_active_privacy_policy(db, privacy_id)
        return await content_crud.get_privacy_policy_by_id(db, privacy_id)


    async def get_faq(self, db: AsyncSession, faq_id: int) -> models.FAQMaster:
        """
        Retrieve specific FAQ document by ID.

        Args:
            db: Database session
            faq_id: FAQ document unique identifier

        Returns:
            FAQMaster object with all sections and contents
        """
        db_faq = await content_crud.get_faq_by_id(db, faq_id)
        if not db_faq:
            raise NotFoundException("FAQ not found")
        return db_faq


    async def get_active_faq(self, db: AsyncSession) -> Optional[models.FAQMaster]:
        """
        Retrieve the currently active FAQ document.

        Args:
            db: Database session

        Returns:
            Active FAQMaster object if found
        """
        db_faq = await content_crud.get_active_faq(db)
        if not db_faq:
            raise NotFoundException("No active FAQ found")
        return db_faq


    async def list_faq(
        self, db: AsyncSession, skip: int, limit: int
    ) -> schemas.PaginatedFAQResponse:
        """
        Retrieve paginated list of all FAQ documents.

        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            Paginated response containing FAQ documents
        """
        items, total = await content_crud.get_all_faq_paginated(db, skip, limit)
        return schemas.PaginatedFAQResponse(total=total, items=items)


    async def create_faq(
        self, db: AsyncSession, faq_in: schemas.FAQMasterCreate, creator: models.User
    ) -> models.FAQMaster:
        """
        Create a new FAQ document.

        Args:
            db: Database session
            faq_in: FAQ creation data including sections and contents
            creator: User creating the FAQ document

        Returns:
            Newly created FAQMaster object with all relationships loaded
        """
        faq_data = faq_in.model_dump()
        faq_data["last_modified_by"] = creator.id
        sections_data = faq_data.pop("sections", [])

        db_faq = await content_crud.create_faq_with_sections(
            db, faq_data, sections_data
        )
        return await content_crud.get_faq_by_id(db, db_faq.id)


    async def update_faq(
        self, db: AsyncSession, faq_id: int, faq_in: schemas.FAQMasterUpdate
    ) -> models.FAQMaster:
        """
        Update an existing FAQ document.

        Args:
            db: Database session
            faq_id: FAQ document unique identifier to update
            faq_in: Updated FAQ data

        Returns:
            Updated FAQMaster object with all relationships loaded
        """
        db_faq = await content_crud.get_faq_by_id(db, faq_id)
        if not db_faq:
            raise NotFoundException("FAQ not found")

        update_data = faq_in.model_dump(exclude_unset=True)

        if "sections" in update_data:
            sections_data = update_data.pop("sections")
            await content_crud.update_faq_sections(db, faq_id, sections_data)

        if update_data:
            await content_crud.update_faq(db, db_faq, update_data)

        return await content_crud.get_faq_by_id(db, faq_id)


    async def delete_faq(self, db: AsyncSession, faq_id: int) -> None:
        """
        Delete a FAQ document.

        Args:
            db: Database session
            faq_id: FAQ document unique identifier to delete

        Returns:
            None
        """
        db_faq = await content_crud.get_by_id(db, models.FAQMaster, faq_id)
        if not db_faq:
            raise NotFoundException("FAQ not found")
        await content_crud.delete_object(db, db_faq)


    async def set_active_faq(self, db: AsyncSession, faq_id: int) -> models.FAQMaster:
        """
        Set specific FAQ document as active and deactivate all others.

        Args:
            db: Database session
            faq_id: FAQ document unique identifier to activate

        Returns:
            Activated FAQMaster object
        """
        db_faq = await content_crud.get_by_id(db, models.FAQMaster, faq_id)
        if not db_faq:
            raise NotFoundException("FAQ not found")

        await content_crud.set_active_faq(db, faq_id)
        return await content_crud.get_faq_by_id(db, faq_id)


    async def _convert_homepage_to_public(
        self, db_homepage: models.HomePage
    ) -> schemas.HomePagePublic:
        """
        Convert database homepage model to public schema with proper data mapping.

        Args:
            db_homepage: Database homepage model

        Returns:
            HomePagePublic schema with all data properly mapped
        """
        top_rentals = []
        for association in db_homepage.top_rental_associations:
            car = association.car
            if not car:
                continue
            top_rentals.append(
                schemas.HomePageTopRentalPublic(
                    id=association.id,
                    car_id=association.car_id,
                    display_order=association.display_order,
                    car=schemas.HomePageCarEssential(
                        id=car.id,
                        car_no=car.car_no,
                        brand=car.car_model.brand,
                        model=car.car_model.model,
                        color=car.color.color_name if car.color else "Unknown",
                        mileage=car.car_model.mileage,
                        rental_per_hr=float(car.car_model.rental_per_hr),
                        manufacture_year=car.manufacture_year,
                        image_url=car.image_urls,
                        transmission_type=car.car_model.transmission_type.value,
                        category_name=(
                            car.car_model.category.category_name
                            if car.car_model and car.car_model.category
                            else None
                        ),
                        fuel_name=(
                            car.car_model.fuel.fuel_name
                            if car.car_model and car.car_model.fuel
                            else None
                        ),
                        capacity_value=(
                            car.car_model.capacity.capacity_value
                            if car.car_model and car.car_model.capacity
                            else None
                        ),
                        feature_names=(
                            [feature.feature_name for feature in car.car_model.features]
                            if car.car_model
                            else []
                        ),
                    ),
                )
            )

        featured_reviews = []
        for association in db_homepage.featured_review_associations:
            review = association.review
            if not review:
                continue
            featured_reviews.append(
                schemas.HomePageFeaturedReviewPublic(
                    id=association.id,
                    review_id=association.review_id,
                    display_order=association.display_order,
                    review=schemas.HomePageReviewEssential(
                        id=review.id,
                        rating=review.rating,
                        remarks=review.remarks,
                        created_at=review.created_at,
                        reviewer_name=(
                            review.creator.username if review.creator else None
                        ),
                        reviewer_email=review.creator.email if review.creator else None,
                        car_brand=(
                            review.car.car_model.brand
                            if review.car and review.car.car_model
                            else None
                        ),
                        car_model=(
                            review.car.car_model.model
                            if review.car and review.car.car_model
                            else None
                        ),
                    ),
                )
            )

        promotions = [
            schemas.HomePagePromotionPublic.model_validate(promo)
            for promo in db_homepage.promotions
        ]
        explore_cars_categories = [
            schemas.HomePageCarCategoryPublic.model_validate(cat)
            for cat in db_homepage.explore_cars_categories
        ]
        contact_faqs = [
            schemas.HomePageContactFAQPublic.model_validate(faq)
            for faq in db_homepage.contact_faqs
        ]

        return schemas.HomePagePublic(
            id=db_homepage.id,
            is_active=db_homepage.is_active,
            effective_from=db_homepage.effective_from,
            last_modified_at=db_homepage.last_modified_at,
            last_modified_by=db_homepage.last_modified_by,
            hero_section=db_homepage.hero_section,
            about_section=db_homepage.about_section,
            promotions_section=db_homepage.promotions_section,
            promotions=promotions,
            top_rental_section=db_homepage.top_rental_section,
            top_rentals=top_rentals,
            explore_cars_section=db_homepage.explore_cars_section,
            explore_cars_categories=explore_cars_categories,
            reviews_section=db_homepage.reviews_section,
            featured_reviews=featured_reviews,
            contact_section=db_homepage.contact_section,
            contact_faqs=contact_faqs,
            footer_section=db_homepage.footer_section,
            modified_by_user=(
                schemas.ContentUserPublic.model_validate(db_homepage.modified_by_user)
                if db_homepage.modified_by_user
                else None
            ),
        )

    async def get_homepage(
        self, db: AsyncSession, homepage_id: int
    ) -> schemas.HomePagePublic:
        """
        Retrieve specific homepage configuration by ID.
        """
        db_homepage = await content_crud.get_homepage_by_id(db, homepage_id)
        if not db_homepage:
            raise NotFoundException("Homepage not found")

        return await self._convert_homepage_to_public(db_homepage)

    async def get_active_homepage(self, db: AsyncSession) -> schemas.HomePagePublic:
        """
        Retrieve the currently active homepage configuration.
        """
        db_homepage = await content_crud.get_active_homepage(db)
        if not db_homepage:
            raise NotFoundException("No active homepage found")

        return await self._convert_homepage_to_public(db_homepage)

    async def list_homepage(
        self, db: AsyncSession, skip: int, limit: int
    ) -> schemas.PaginatedHomePageResponse:
        """
        Retrieve paginated list of all homepage configurations.

        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            Paginated response containing homepage configurations
        """
        items, total = await content_crud.get_all_homepage_paginated(db, skip, limit)

        converted_items = []
        for item in items:
            converted_items.append(await self._convert_homepage_to_public(item))

        return schemas.PaginatedHomePageResponse(total=total, items=converted_items)


    async def create_homepage(
        self,
        db: AsyncSession,
        homepage_in: schemas.HomePageCreate,
        creator: models.User,
    ) -> schemas.HomePagePublic:
        """
        Create a new homepage configuration with validation.

        Args:
            db: Database session
            homepage_in: Homepage creation data with nested objects
            creator: User creating the homepage configuration

        Returns:
            Newly created HomePagePublic schema with all data properly mapped
        """
        if homepage_in.top_rentals:
            car_ids = []
            for rental in homepage_in.top_rentals:
                if isinstance(rental, dict):
                    car_ids.append(rental.get("car_id"))
                else:
                    car_ids.append(rental.car_id)
            existing_car_ids = await content_crud.get_existing_car_ids(db, car_ids)
            self._validate_all_ids_exist(car_ids, existing_car_ids, "Car")

        if homepage_in.featured_reviews:
            review_ids = []
            for review in homepage_in.featured_reviews:
                if isinstance(review, dict):
                    review_ids.append(review.get("review_id"))
                else:
                    review_ids.append(review.review_id)
            existing_review_ids = await content_crud.get_existing_review_ids(
                db, review_ids
            )
            self._validate_all_ids_exist(review_ids, existing_review_ids, "Review")

        homepage_data = homepage_in.model_dump()
        homepage_data["last_modified_by"] = creator.id

        promotions_data = homepage_data.pop("promotions", [])
        car_categories_data = homepage_data.pop("explore_cars_categories", [])
        contact_faqs_data = homepage_data.pop("contact_faqs", [])
        top_rentals_data = homepage_data.pop("top_rentals", [])
        featured_reviews_data = homepage_data.pop("featured_reviews", [])

        try:
            db_homepage = await content_crud.create_homepage_with_nested(
                db,
                homepage_data,
                promotions_data,
                car_categories_data,
                contact_faqs_data,
                top_rentals_data,
                featured_reviews_data,
            )
            full_homepage = await content_crud.get_homepage_by_id(db, db_homepage.id)
            return await self._convert_homepage_to_public(full_homepage)

        except sqlalchemy.exc.IntegrityError:
            await db.rollback()
            raise NotFoundException("Invalid car or review IDs provided")


    async def update_homepage(
        self, db: AsyncSession, homepage_id: int, homepage_in: schemas.HomePageUpdate
    ) -> schemas.HomePagePublic:
        """
        Update an existing homepage configuration with validation.

        Args:
            db: Database session
            homepage_id: Homepage configuration unique identifier to update
            homepage_in: Updated homepage data

        Returns:
            Updated HomePagePublic schema with all data properly mapped
        """
        db_homepage = await content_crud.get_homepage_by_id(db, homepage_id)
        if not db_homepage:
            raise NotFoundException("Homepage not found")

        update_data = homepage_in.model_dump(exclude_unset=True)

        if "top_rentals" in update_data and update_data["top_rentals"] is not None:
            car_ids = []
            for rental in update_data["top_rentals"]:
                if isinstance(rental, dict):
                    car_ids.append(rental.get("car_id"))
                else:
                    car_ids.append(rental.car_id)
            existing_car_ids = await content_crud.get_existing_car_ids(db, car_ids)
            self._validate_all_ids_exist(car_ids, existing_car_ids, "Car")

        if (
            "featured_reviews" in update_data
            and update_data["featured_reviews"] is not None
        ):
            review_ids = []
            for review in update_data["featured_reviews"]:
                if isinstance(review, dict):
                    review_ids.append(review.get("review_id"))
                else:
                    review_ids.append(review.review_id)
            existing_review_ids = await content_crud.get_existing_review_ids(
                db, review_ids
            )
            self._validate_all_ids_exist(review_ids, existing_review_ids, "Review")

        promotions_data = update_data.pop("promotions", None)
        car_categories_data = update_data.pop("explore_cars_categories", None)
        contact_faqs_data = update_data.pop("contact_faqs", None)
        top_rentals_data = update_data.pop("top_rentals", None)
        featured_reviews_data = update_data.pop("featured_reviews", None)

        if any(
            [
                promotions_data is not None,
                car_categories_data is not None,
                contact_faqs_data is not None,
                top_rentals_data is not None,
                featured_reviews_data is not None,
            ]
        ):
            await content_crud.update_homepage_nested(
                db,
                homepage_id,
                promotions_data or [],
                car_categories_data or [],
                contact_faqs_data or [],
                top_rentals_data or [],
                featured_reviews_data or [],
            )

        if update_data:
            await content_crud.update_homepage(db, db_homepage, update_data)

        updated_homepage = await content_crud.get_homepage_by_id(db, homepage_id)
        return await self._convert_homepage_to_public(updated_homepage)


    def _validate_all_ids_exist(
        self, requested_ids: List[int], existing_ids: List[int], entity_name: str
    ) -> None:
        """
        Validate that all requested IDs exist.

        Args:
            requested_ids: List of requested entity IDs
            existing_ids: List of existing entity IDs
            entity_name: Name of the entity type for error messages

        Returns:
            None
        """
        if len(existing_ids) != len(requested_ids):
            invalid_ids = set(requested_ids) - set(existing_ids)
            raise NotFoundException(f"{entity_name} IDs not found: {invalid_ids}")


    async def delete_homepage(self, db: AsyncSession, homepage_id: int) -> None:
        """
        Delete a homepage configuration.

        Args:
            db: Database session
            homepage_id: Homepage configuration unique identifier to delete

        Returns:
            None
        """
        db_homepage = await content_crud.get_by_id(db, models.HomePage, homepage_id)
        if not db_homepage:
            raise NotFoundException("Homepage not found")
        await content_crud.delete_object(db, db_homepage)


    async def set_active_homepage(
        self, db: AsyncSession, homepage_id: int
    ) -> schemas.HomePagePublic:
        """
        Set specific homepage configuration as active and deactivate all others.

        Args:
            db: Database session
            homepage_id: Homepage configuration unique identifier to activate

        Returns:
            Activated HomePage object
        """
        db_homepage = await content_crud.get_by_id(db, models.HomePage, homepage_id)
        if not db_homepage:
            raise NotFoundException("Homepage not found")

        await content_crud.set_active_homepage(db, homepage_id)

        activated_homepage = await content_crud.get_homepage_by_id(db, homepage_id)
        return await self._convert_homepage_to_public(activated_homepage)


    async def get_admin_help_centre(
        self, db: AsyncSession, admin_help_id: int
    ) -> models.AdminHelpCentreMaster:
        """
        Retrieve specific admin help centre document by ID.

        Args:
            db: Database session
            admin_help_id: Admin help centre document unique identifier

        Returns:
            AdminHelpCentreMaster object with all sections and contents
        """
        db_admin_help = await content_crud.get_admin_help_centre_by_id(
            db, admin_help_id
        )
        if not db_admin_help:
            raise NotFoundException("Admin Help Centre not found")
        return db_admin_help


    async def get_active_admin_help_centre(
        self, db: AsyncSession
    ) -> Optional[models.AdminHelpCentreMaster]:
        """
        Retrieve the currently active admin help centre document.

        Args:
            db: Database session

        Returns:
            Active AdminHelpCentreMaster object if found
        """
        db_admin_help = await content_crud.get_active_admin_help_centre(db)
        if not db_admin_help:
            raise NotFoundException("No active admin help centre found")
        return db_admin_help


    async def list_admin_help_centre(
        self, db: AsyncSession, skip: int, limit: int
    ) -> schemas.PaginatedAdminHelpCentreResponse:
        """
        Retrieve paginated list of all admin help centre documents.

        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            Paginated response containing admin help centre documents
        """
        items, total = await content_crud.get_all_admin_help_centre_paginated(
            db, skip, limit
        )
        return schemas.PaginatedAdminHelpCentreResponse(total=total, items=items)


    async def create_admin_help_centre(
        self,
        db: AsyncSession,
        admin_help_in: schemas.AdminHelpCentreMasterCreate,
        creator: models.User,
    ) -> models.AdminHelpCentreMaster:
        """
        Create a new admin help centre document.

        Args:
            db: Database session
            admin_help_in: Admin help centre creation data including sections and contents
            creator: User creating the admin help centre document

        Returns:
            Newly created AdminHelpCentreMaster object with all relationships loaded
        """
        admin_help_data = admin_help_in.model_dump()
        admin_help_data["last_modified_by"] = creator.id
        sections_data = admin_help_data.pop("sections", [])

        db_admin_help = await content_crud.create_admin_help_centre_with_sections(
            db, admin_help_data, sections_data
        )

        return await content_crud.get_admin_help_centre_by_id(db, db_admin_help.id)


    async def update_admin_help_centre(
        self,
        db: AsyncSession,
        admin_help_id: int,
        admin_help_in: schemas.AdminHelpCentreMasterUpdate,
    ) -> models.AdminHelpCentreMaster:
        """
        Update an existing admin help centre document.

        Args:
            db: Database session
            admin_help_id: Admin help centre document unique identifier to update
            admin_help_in: Updated admin help centre data

        Returns:
            Updated AdminHelpCentreMaster object with all relationships loaded
        """
        db_admin_help = await content_crud.get_admin_help_centre_by_id(
            db, admin_help_id
        )
        if not db_admin_help:
            raise NotFoundException("Admin Help Centre not found")

        update_data = admin_help_in.model_dump(exclude_unset=True)

        if "sections" in update_data:
            sections_data = update_data.pop("sections")
            await content_crud.update_admin_help_centre_sections(
                db, admin_help_id, sections_data
            )

        if update_data:
            await content_crud.update_admin_help_centre(db, db_admin_help, update_data)

        return await content_crud.get_admin_help_centre_by_id(db, admin_help_id)


    async def delete_admin_help_centre(
        self, db: AsyncSession, admin_help_id: int
    ) -> None:
        """
        Delete an admin help centre document.

        Args:
            db: Database session
            admin_help_id: Admin help centre document unique identifier to delete

        Returns:
            None
        """
        db_admin_help = await content_crud.get_by_id(
            db, models.AdminHelpCentreMaster, admin_help_id
        )
        if not db_admin_help:
            raise NotFoundException("Admin Help Centre not found")
        await content_crud.delete_object(db, db_admin_help)


    async def set_active_admin_help_centre(
        self, db: AsyncSession, admin_help_id: int
    ) -> models.AdminHelpCentreMaster:
        """
        Set specific admin help centre document as active and deactivate all others.

        Args:
            db: Database session
            admin_help_id: Admin help centre document unique identifier to activate

        Returns:
            Activated AdminHelpCentreMaster object
        """
        db_admin_help = await content_crud.get_by_id(
            db, models.AdminHelpCentreMaster, admin_help_id
        )
        if not db_admin_help:
            raise NotFoundException("Admin Help Centre not found")

        await content_crud.set_active_admin_help_centre(db, admin_help_id)

        return await content_crud.get_admin_help_centre_by_id(db, admin_help_id)


content_service = ContentService()
