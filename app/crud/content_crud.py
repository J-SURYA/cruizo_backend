from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sql_delete, update as sql_update
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional, Tuple, Dict, Any


from app import models


class ContentCRUD:
    """
    Class for managing content documents such as Terms, Help Centre, Privacy Policy, and FAQ.
    """
    async def get_by_id(
        self, db: AsyncSession, model: type[models.Base], obj_id: int
    ) -> Optional[models.Base]:
        """
        Retrieve any model object by its ID
        
        Args:
            db: Database session
            model: SQLAlchemy model class
            obj_id: Object unique identifier
        
        Returns:
            Model object if found, None otherwise
        """
        return await db.get(model, obj_id)


    async def get_all(self, db: AsyncSession, model: type[models.Base]) -> List[models.Base]:
        """
        Retrieve all objects of a model
        
        Args:
            db: Database session
            model: SQLAlchemy model class
        
        Returns:
            List of all model objects
        """
        result = await db.execute(select(model))
        return result.scalars().all()


    async def create(self, db: AsyncSession, db_obj: models.Base) -> models.Base:
        """
        Create a new model object
        
        Args:
            db: Database session
            db_obj: Model object to create
        
        Returns:
            Newly created model object
        """
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


    async def delete_object(self, db: AsyncSession, db_obj: models.Base) -> None:
        """
        Delete a specific object instance from the database
        
        Args:
            db: Database session
            db_obj: Model object to delete
        
        Returns:
            None
        """
        await db.delete(db_obj)
        await db.commit()


    async def update(
        self, db: AsyncSession, db_obj: models.Base, update_data: Dict[str, Any]
    ) -> models.Base:
        """
        Update a model object with new data
        
        Args:
            db: Database session
            db_obj: Model object to update
            update_data: Dictionary of field names and values to update
        
        Returns:
            Updated model object
        """
        for key, value in update_data.items():
            setattr(db_obj, key, value)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


    async def set_active_master(
        self, db: AsyncSession, model: type[models.Base], active_id: int
    ) -> None:
        """
        Set one master document as active and deactivate all others
        
        Args:
            db: Database session
            model: Master model class (TermsMaster, HelpCentreMaster, etc.)
            active_id: ID of the document to set as active
        
        Returns:
            None
        """
        await db.execute(
            sql_update(model).where(model.is_active.is_(True)).values(is_active=False)
        )
        await db.execute(
            sql_update(model).where(model.id == active_id).values(is_active=True)
        )
        await db.commit()


    async def get_terms_by_id(
        self, db: AsyncSession, terms_id: int
    ) -> Optional[models.TermsMaster]:
        """
        Retrieve terms and conditions by ID with all sections and contents
        
        Args:
            db: Database session
            terms_id: Terms document unique identifier
        
        Returns:
            TermsMaster object with sections and contents if found, None otherwise
        """
        query = (
            select(models.TermsMaster)
            .options(
                selectinload(models.TermsMaster.sections).selectinload(
                    models.TermsSection.contents
                ),
                joinedload(models.TermsMaster.modified_by_user),
            )
            .where(models.TermsMaster.id == terms_id)
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_active_terms(self, db: AsyncSession) -> Optional[models.TermsMaster]:
        """
        Retrieve the currently active terms and conditions
        
        Args:
            db: Database session
        
        Returns:
            Active TermsMaster object if found, None otherwise
        """
        query = (
            select(models.TermsMaster)
            .options(
                selectinload(models.TermsMaster.sections).selectinload(
                    models.TermsSection.contents
                ),
                joinedload(models.TermsMaster.modified_by_user),
            )
            .where(models.TermsMaster.is_active.is_(True))
            .order_by(models.TermsMaster.effective_from.desc())
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_all_terms_paginated(
        self, db: AsyncSession, skip: int, limit: int
    ) -> Tuple[List[models.TermsMaster], int]:
        """
        Retrieve paginated list of all terms and conditions documents
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (list of TermsMaster objects, total count of records)
        """
        base_query = select(models.TermsMaster).options(
            selectinload(models.TermsMaster.sections).selectinload(
                models.TermsSection.contents
            ),
            joinedload(models.TermsMaster.modified_by_user),
        )
        count_query = select(func.count()).select_from(models.TermsMaster)
        total = (await db.execute(count_query)).scalar_one()
        items_query = (
            base_query.order_by(models.TermsMaster.effective_from.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await db.execute(items_query)).scalars().unique().all()
        return items, total


    async def create_terms_with_sections(
        self, db: AsyncSession, terms_data: dict, sections_data: List[dict]
    ) -> models.TermsMaster:
        """
        Create a new terms and conditions document with sections and contents
        
        Args:
            db: Database session
            terms_data: Terms master document data
            sections_data: List of section data with nested contents
        
        Returns:
            Newly created TermsMaster object
        """
        if terms_data.get("is_active", False):
            await db.execute(
                sql_update(models.TermsMaster)
                .where(models.TermsMaster.is_active.is_(True))
                .values(is_active=False)
            )
        db_terms = models.TermsMaster(**terms_data)
        db.add(db_terms)
        await db.flush()
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.TermsSection(**section_data, terms_master_id=db_terms.id)
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.TermsContent(**content_data, section_id=db_section.id)
                db.add(db_content)
        await db.commit()
        await db.refresh(db_terms)
        return db_terms


    async def update_terms_sections(
        self, db: AsyncSession, terms_id: int, sections_data: List[dict]
    ) -> None:
        """
        Update sections and contents for an existing terms document
        
        Args:
            db: Database session
            terms_id: Terms document unique identifier
            sections_data: List of updated section data with nested contents
        
        Returns:
            None
        """
        await db.execute(
            sql_delete(models.TermsContent).where(
                models.TermsContent.section_id.in_(
                    select(models.TermsSection.id).where(
                        models.TermsSection.terms_master_id == terms_id
                    )
                )
            )
        )
        await db.execute(
            sql_delete(models.TermsSection).where(
                models.TermsSection.terms_master_id == terms_id
            )
        )
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.TermsSection(**section_data, terms_master_id=terms_id)
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.TermsContent(**content_data, section_id=db_section.id)
                db.add(db_content)


    async def update_terms(
        self, db: AsyncSession, db_terms: models.TermsMaster, update_data: dict
    ) -> models.TermsMaster:
        """
        Update terms master document with proper active status handling
        
        Args:
            db: Database session
            db_terms: Existing TermsMaster object to update
            update_data: Dictionary of fields to update
        
        Returns:
            Updated TermsMaster object
        """
        if "is_active" in update_data and update_data["is_active"]:
            await db.execute(
                sql_update(models.TermsMaster)
                .where(models.TermsMaster.is_active.is_(True))
                .values(is_active=False)
            )
        return await self.update(db, db_terms, update_data)


    async def set_active_terms(self, db: AsyncSession, terms_id: int) -> None:
        """
        Set specific terms document as active and deactivate all others
        
        Args:
            db: Database session
            terms_id: Terms document unique identifier to activate
        
        Returns:
            None
        """
        await self.set_active_master(db, models.TermsMaster, terms_id)


    async def get_help_centre_by_id(
        self, db: AsyncSession, help_id: int
    ) -> Optional[models.HelpCentreMaster]:
        """
        Retrieve help centre document by ID with all sections and contents
        
        Args:
            db: Database session
            help_id: Help centre document unique identifier
        
        Returns:
            HelpCentreMaster object with sections and contents if found, None otherwise
        """
        query = (
            select(models.HelpCentreMaster)
            .options(
                selectinload(models.HelpCentreMaster.sections).selectinload(
                    models.HelpCentreSection.contents
                ),
                joinedload(models.HelpCentreMaster.modified_by_user),
            )
            .where(models.HelpCentreMaster.id == help_id)
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_active_help_centre(self, db: AsyncSession) -> Optional[models.HelpCentreMaster]:
        """
        Retrieve the currently active help centre document
        
        Args:
            db: Database session
        
        Returns:
            Active HelpCentreMaster object if found, None otherwise
        """
        query = (
            select(models.HelpCentreMaster)
            .options(
                selectinload(models.HelpCentreMaster.sections).selectinload(
                    models.HelpCentreSection.contents
                ),
                joinedload(models.HelpCentreMaster.modified_by_user),
            )
            .where(models.HelpCentreMaster.is_active.is_(True))
            .order_by(models.HelpCentreMaster.effective_from.desc())
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_all_help_centre_paginated(
        self, db: AsyncSession, skip: int, limit: int
    ) -> Tuple[List[models.HelpCentreMaster], int]:
        """
        Retrieve paginated list of all help centre documents
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (list of HelpCentreMaster objects, total count of records)
        """
        base_query = select(models.HelpCentreMaster).options(
            selectinload(models.HelpCentreMaster.sections).selectinload(
                models.HelpCentreSection.contents
            ),
            joinedload(models.HelpCentreMaster.modified_by_user),
        )
        count_query = select(func.count()).select_from(models.HelpCentreMaster)
        total = (await db.execute(count_query)).scalar_one()
        items_query = (
            base_query.order_by(models.HelpCentreMaster.effective_from.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await db.execute(items_query)).scalars().unique().all()
        return items, total


    async def create_help_centre_with_sections(
        self, db: AsyncSession, help_data: dict, sections_data: List[dict]
    ) -> models.HelpCentreMaster:
        """
        Create a new help centre document with sections and contents
        
        Args:
            db: Database session
            help_data: Help centre master document data
            sections_data: List of section data with nested contents
        
        Returns:
            Newly created HelpCentreMaster object
        """
        if help_data.get("is_active", False):
            await db.execute(
                sql_update(models.HelpCentreMaster)
                .where(models.HelpCentreMaster.is_active.is_(True))
                .values(is_active=False)
            )
        db_help = models.HelpCentreMaster(**help_data)
        db.add(db_help)
        await db.flush()
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.HelpCentreSection(**section_data, help_master_id=db_help.id)
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.HelpCentreContent(
                    **content_data, section_id=db_section.id
                )
                db.add(db_content)
        await db.commit()
        await db.refresh(db_help)
        return db_help


    async def update_help_centre_sections(
        self, db: AsyncSession, help_id: int, sections_data: List[dict]
    ) -> None:
        """
        Update sections and contents for an existing help centre document
        
        Args:
            db: Database session
            help_id: Help centre document unique identifier
            sections_data: List of updated section data with nested contents
        
        Returns:
            None
        """
        await db.execute(
            sql_delete(models.HelpCentreContent).where(
                models.HelpCentreContent.section_id.in_(
                    select(models.HelpCentreSection.id).where(
                        models.HelpCentreSection.help_master_id == help_id
                    )
                )
            )
        )
        await db.execute(
            sql_delete(models.HelpCentreSection).where(
                models.HelpCentreSection.help_master_id == help_id
            )
        )
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.HelpCentreSection(**section_data, help_master_id=help_id)
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.HelpCentreContent(
                    **content_data, section_id=db_section.id
                )
                db.add(db_content)


    async def update_help_centre(
        self, db: AsyncSession, db_help: models.HelpCentreMaster, update_data: dict
    ) -> models.HelpCentreMaster:
        """
        Update help centre document with proper active status handling
        
        Args:
            db: Database session
            db_help: Existing HelpCentreMaster object to update
            update_data: Dictionary of fields to update
        
        Returns:
            Updated HelpCentreMaster object
        """
        if "is_active" in update_data and update_data["is_active"]:
            await db.execute(
                sql_update(models.HelpCentreMaster)
                .where(models.HelpCentreMaster.is_active.is_(True))
                .values(is_active=False)
            )
        return await self.update(db, db_help, update_data)


    async def set_active_help_centre(self, db: AsyncSession, help_id: int) -> None:
        """
        Set specific help centre document as active and deactivate all others
        
        Args:
            db: Database session
            help_id: Help centre document unique identifier to activate
        
        Returns:
            None
        """
        await self.set_active_master(db, models.HelpCentreMaster, help_id)


    async def get_privacy_policy_by_id(
        self, db: AsyncSession, privacy_id: int
    ) -> Optional[models.PrivacyPolicyMaster]:
        """
        Retrieve privacy policy document by ID with all sections and contents
        
        Args:
            db: Database session
            privacy_id: Privacy policy document unique identifier
        
        Returns:
            PrivacyPolicyMaster object with sections and contents if found, None otherwise
        """
        query = (
            select(models.PrivacyPolicyMaster)
            .options(
                selectinload(models.PrivacyPolicyMaster.sections).selectinload(
                    models.PrivacyPolicySection.contents
                ),
                joinedload(models.PrivacyPolicyMaster.modified_by_user),
            )
            .where(models.PrivacyPolicyMaster.id == privacy_id)
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_active_privacy_policy(
        self, db: AsyncSession
    ) -> Optional[models.PrivacyPolicyMaster]:
        """
        Retrieve the currently active privacy policy document
        
        Args:
            db: Database session
        
        Returns:
            Active PrivacyPolicyMaster object if found, None otherwise
        """
        query = (
            select(models.PrivacyPolicyMaster)
            .options(
                selectinload(models.PrivacyPolicyMaster.sections).selectinload(
                    models.PrivacyPolicySection.contents
                ),
                joinedload(models.PrivacyPolicyMaster.modified_by_user),
            )
            .where(models.PrivacyPolicyMaster.is_active.is_(True))
            .order_by(models.PrivacyPolicyMaster.effective_from.desc())
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_all_privacy_policy_paginated(
        self, db: AsyncSession, skip: int, limit: int
    ) -> Tuple[List[models.PrivacyPolicyMaster], int]:
        """
        Retrieve paginated list of all privacy policy documents
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (list of PrivacyPolicyMaster objects, total count of records)
        """
        base_query = select(models.PrivacyPolicyMaster).options(
            selectinload(models.PrivacyPolicyMaster.sections).selectinload(
                models.PrivacyPolicySection.contents
            ),
            joinedload(models.PrivacyPolicyMaster.modified_by_user),
        )
        count_query = select(func.count()).select_from(models.PrivacyPolicyMaster)
        total = (await db.execute(count_query)).scalar_one()
        items_query = (
            base_query.order_by(models.PrivacyPolicyMaster.effective_from.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await db.execute(items_query)).scalars().unique().all()
        return items, total


    async def create_privacy_policy_with_sections(
        self, db: AsyncSession, privacy_data: dict, sections_data: List[dict]
    ) -> models.PrivacyPolicyMaster:
        """
        Create a new privacy policy document with sections and contents
        
        Args:
            db: Database session
            privacy_data: Privacy policy master document data
            sections_data: List of section data with nested contents
        
        Returns:
            Newly created PrivacyPolicyMaster object
        """
        if privacy_data.get("is_active", False):
            await db.execute(
                sql_update(models.PrivacyPolicyMaster)
                .where(models.PrivacyPolicyMaster.is_active.is_(True))
                .values(is_active=False)
            )
        db_privacy = models.PrivacyPolicyMaster(**privacy_data)
        db.add(db_privacy)
        await db.flush()
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.PrivacyPolicySection(
                **section_data, privacy_master_id=db_privacy.id
            )
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.PrivacyPolicyContent(
                    **content_data, section_id=db_section.id
                )
                db.add(db_content)
        await db.commit()
        await db.refresh(db_privacy)
        return db_privacy


    async def update_privacy_policy_sections(
        self, db: AsyncSession, privacy_id: int, sections_data: List[dict]
    ) -> None:
        """
        Update sections and contents for an existing privacy policy document
        
        Args:
            db: Database session
            privacy_id: Privacy policy document unique identifier
            sections_data: List of updated section data with nested contents
        
        Returns:
            None
        """
        await db.execute(
            sql_delete(models.PrivacyPolicyContent).where(
                models.PrivacyPolicyContent.section_id.in_(
                    select(models.PrivacyPolicySection.id).where(
                        models.PrivacyPolicySection.privacy_master_id == privacy_id
                    )
                )
            )
        )
        await db.execute(
            sql_delete(models.PrivacyPolicySection).where(
                models.PrivacyPolicySection.privacy_master_id == privacy_id
            )
        )
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.PrivacyPolicySection(
                **section_data, privacy_master_id=privacy_id
            )
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.PrivacyPolicyContent(
                    **content_data, section_id=db_section.id
                )
                db.add(db_content)


    async def update_privacy_policy(
        self, db: AsyncSession, db_privacy: models.PrivacyPolicyMaster, update_data: dict
    ) -> models.PrivacyPolicyMaster:
        """
        Update privacy policy document with proper active status handling
        
        Args:
            db: Database session
            db_privacy: Existing PrivacyPolicyMaster object to update
            update_data: Dictionary of fields to update
        
        Returns:
            Updated PrivacyPolicyMaster object
        """
        if "is_active" in update_data and update_data["is_active"]:
            await db.execute(
                sql_update(models.PrivacyPolicyMaster)
                .where(models.PrivacyPolicyMaster.is_active.is_(True))
                .values(is_active=False)
            )
        return await self.update(db, db_privacy, update_data)


    async def set_active_privacy_policy(self, db: AsyncSession, privacy_id: int) -> None:
        """
        Set specific privacy policy document as active and deactivate all others
        
        Args:
            db: Database session
            privacy_id: Privacy policy document unique identifier to activate
        
        Returns:
            None
        """
        await self.set_active_master(db, models.PrivacyPolicyMaster, privacy_id)


    async def get_faq_by_id(self, db: AsyncSession, faq_id: int) -> Optional[models.FAQMaster]:
        """
        Retrieve FAQ document by ID with all sections and contents
        
        Args:
            db: Database session
            faq_id: FAQ document unique identifier
        
        Returns:
            FAQMaster object with sections and contents if found, None otherwise
        """
        query = (
            select(models.FAQMaster)
            .options(
                selectinload(models.FAQMaster.sections).selectinload(
                    models.FAQSection.contents
                ),
                joinedload(models.FAQMaster.modified_by_user),
            )
            .where(models.FAQMaster.id == faq_id)
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_active_faq(self, db: AsyncSession) -> Optional[models.FAQMaster]:
        """
        Retrieve the currently active FAQ document
        
        Args:
            db: Database session
        
        Returns:
            Active FAQMaster object if found, None otherwise
        """
        query = (
            select(models.FAQMaster)
            .options(
                selectinload(models.FAQMaster.sections).selectinload(
                    models.FAQSection.contents
                ),
                joinedload(models.FAQMaster.modified_by_user),
            )
            .where(models.FAQMaster.is_active.is_(True))
            .order_by(models.FAQMaster.effective_from.desc())
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_all_faq_paginated(
        self, db: AsyncSession, skip: int, limit: int
    ) -> Tuple[List[models.FAQMaster], int]:
        """
        Retrieve paginated list of all FAQ documents
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (list of FAQMaster objects, total count of records)
        """
        base_query = select(models.FAQMaster).options(
            selectinload(models.FAQMaster.sections).selectinload(
                models.FAQSection.contents
            ),
            joinedload(models.FAQMaster.modified_by_user),
        )
        count_query = select(func.count()).select_from(models.FAQMaster)
        total = (await db.execute(count_query)).scalar_one()
        items_query = (
            base_query.order_by(models.FAQMaster.effective_from.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await db.execute(items_query)).scalars().unique().all()
        return items, total


    async def create_faq_with_sections(
        self, db: AsyncSession, faq_data: dict, sections_data: List[dict]
    ) -> models.FAQMaster:
        """
        Create a new FAQ document with sections and contents
        
        Args:
            db: Database session
            faq_data: FAQ master document data
            sections_data: List of section data with nested contents
        
        Returns:
            Newly created FAQMaster object
        """
        if faq_data.get("is_active", False):
            await db.execute(
                sql_update(models.FAQMaster)
                .where(models.FAQMaster.is_active.is_(True))
                .values(is_active=False)
            )
        db_faq = models.FAQMaster(**faq_data)
        db.add(db_faq)
        await db.flush()
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.FAQSection(**section_data, faq_master_id=db_faq.id)
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.FAQContent(**content_data, section_id=db_section.id)
                db.add(db_content)
        await db.commit()
        await db.refresh(db_faq)
        return db_faq


    async def update_faq_sections(
        self, db: AsyncSession, faq_id: int, sections_data: List[dict]
    ) -> None:
        """
        Update sections and contents for an existing FAQ document
        
        Args:
            db: Database session
            faq_id: FAQ document unique identifier
            sections_data: List of updated section data with nested contents
        
        Returns:
            None
        """
        await db.execute(
            sql_delete(models.FAQContent).where(
                models.FAQContent.section_id.in_(
                    select(models.FAQSection.id).where(
                        models.FAQSection.faq_master_id == faq_id
                    )
                )
            )
        )
        await db.execute(
            sql_delete(models.FAQSection).where(models.FAQSection.faq_master_id == faq_id)
        )
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.FAQSection(**section_data, faq_master_id=faq_id)
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.FAQContent(**content_data, section_id=db_section.id)
                db.add(db_content)


    async def update_faq(
        self, db: AsyncSession, db_faq: models.FAQMaster, update_data: dict
    ) -> models.FAQMaster:
        """
        Update FAQ document with proper active status handling
        
        Args:
            db: Database session
            db_faq: Existing FAQMaster object to update
            update_data: Dictionary of fields to update
        
        Returns:
            Updated FAQMaster object
        """
        if "is_active" in update_data and update_data["is_active"]:
            await db.execute(
                sql_update(models.FAQMaster)
                .where(models.FAQMaster.is_active.is_(True))
                .values(is_active=False)
            )
        return await self.update(db, db_faq, update_data)


    async def set_active_faq(self, db: AsyncSession, faq_id: int) -> None:
        """
        Set specific FAQ document as active and deactivate all others
        
        Args:
            db: Database session
            faq_id: FAQ document unique identifier to activate
        
        Returns:
            None
        """
        await self.set_active_master(db, models.FAQMaster, faq_id)


    async def get_cars_by_ids(self, db: AsyncSession, car_ids: List[int]) -> List[models.Car]:
        """
        Get cars by their IDs
        
        Args:
            db: Database session
            car_ids: List of car IDs
        
        Returns:
            List of Car objects
        """
        if not car_ids:
            return []
        result = await db.execute(select(models.Car).where(models.Car.id.in_(car_ids)))
        return result.scalars().all()


    async def get_reviews_by_ids(
        self, db: AsyncSession, review_ids: List[int]
    ) -> List[models.Review]:
        """
        Get reviews by their IDs
        
        Args:
            db: Database session
            review_ids: List of review IDs
        
        Returns:
            List of Review objects
        """
        if not review_ids:
            return []
        result = await db.execute(
            select(models.Review).where(models.Review.id.in_(review_ids))
        )
        return result.scalars().all()


    async def get_existing_car_ids(self, db: AsyncSession, car_ids: List[int]) -> List[int]:
        """
        Get only the car IDs that exist in the database
        
        Args:
            db: Database session
            car_ids: List of car IDs to check
        
        Returns:
            List of existing car IDs
        """
        if not car_ids:
            return []
        result = await db.execute(select(models.Car.id).where(models.Car.id.in_(car_ids)))
        return [row[0] for row in result.all()]


    async def get_existing_review_ids(self, db: AsyncSession, review_ids: List[int]) -> List[int]:
        """
        Get only the review IDs that exist in the database
        
        Args:
            db: Database session
            review_ids: List of review IDs to check
        
        Returns:
            List of existing review IDs
        """
        if not review_ids:
            return []
        result = await db.execute(
            select(models.Review.id).where(models.Review.id.in_(review_ids))
        )
        return [row[0] for row in result.all()]


    async def get_homepage_by_id(
        self, db: AsyncSession, homepage_id: int
    ) -> Optional[models.HomePage]:
        """
        Retrieve homepage configuration by ID with all nested objects and related data
        
        Args:
            db: Database session
            homepage_id: Homepage configuration unique identifier
        
        Returns:
            HomePage object with all nested objects if found, None otherwise
        """
        query = (
            select(models.HomePage)
            .options(
                selectinload(models.HomePage.promotions),
                selectinload(models.HomePage.explore_cars_categories),
                selectinload(models.HomePage.contact_faqs),
                selectinload(models.HomePage.top_rental_associations)
                .selectinload(models.HomePageTopRental.car)
                .selectinload(models.Car.car_model)
                .selectinload(models.CarModel.category),
                selectinload(models.HomePage.top_rental_associations)
                .selectinload(models.HomePageTopRental.car)
                .selectinload(models.Car.car_model)
                .selectinload(models.CarModel.fuel),
                selectinload(models.HomePage.top_rental_associations)
                .selectinload(models.HomePageTopRental.car)
                .selectinload(models.Car.car_model)
                .selectinload(models.CarModel.capacity),
                selectinload(models.HomePage.top_rental_associations)
                .selectinload(models.HomePageTopRental.car)
                .selectinload(models.Car.car_model)
                .selectinload(models.CarModel.features),
                selectinload(models.HomePage.featured_review_associations)
                .selectinload(models.HomePageFeaturedReview.review)
                .selectinload(models.Review.creator),
                selectinload(models.HomePage.featured_review_associations)
                .selectinload(models.HomePageFeaturedReview.review)
                .selectinload(models.Review.car)
                .selectinload(models.Car.car_model),
                joinedload(models.HomePage.modified_by_user),
            )
            .where(models.HomePage.id == homepage_id)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()


    async def get_active_homepage(self, db: AsyncSession) -> Optional[models.HomePage]:
        """
        Retrieve the currently active homepage configuration with all related data
        
        Args:
            db: Database session
        
        Returns:
            Active HomePage object if found, None otherwise
        """
        query = (
            select(models.HomePage)
            .options(
                selectinload(models.HomePage.promotions),
                selectinload(models.HomePage.explore_cars_categories),
                selectinload(models.HomePage.contact_faqs),
                selectinload(models.HomePage.top_rental_associations)
                .selectinload(models.HomePageTopRental.car)
                .selectinload(models.Car.car_model)
                .selectinload(models.CarModel.category),
                selectinload(models.HomePage.top_rental_associations)
                .selectinload(models.HomePageTopRental.car)
                .selectinload(models.Car.car_model)
                .selectinload(models.CarModel.fuel),
                selectinload(models.HomePage.top_rental_associations)
                .selectinload(models.HomePageTopRental.car)
                .selectinload(models.Car.car_model)
                .selectinload(models.CarModel.capacity),
                selectinload(models.HomePage.top_rental_associations)
                .selectinload(models.HomePageTopRental.car)
                .selectinload(models.Car.car_model)
                .selectinload(models.CarModel.features),
                selectinload(models.HomePage.featured_review_associations)
                .selectinload(models.HomePageFeaturedReview.review)
                .selectinload(models.Review.creator),
                selectinload(models.HomePage.featured_review_associations)
                .selectinload(models.HomePageFeaturedReview.review)
                .selectinload(models.Review.car)
                .selectinload(models.Car.car_model),
                joinedload(models.HomePage.modified_by_user),
            )
            .where(models.HomePage.is_active.is_(True))
            .order_by(models.HomePage.effective_from.desc())
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()


    async def get_all_homepage_paginated(
        self, db: AsyncSession, skip: int, limit: int
    ) -> Tuple[List[models.HomePage], int]:
        """
        Retrieve paginated list of all homepage configurations with full related data
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (list of HomePage objects, total count of records)
        """
        base_query = select(models.HomePage).options(
            selectinload(models.HomePage.promotions),
            selectinload(models.HomePage.explore_cars_categories),
            selectinload(models.HomePage.contact_faqs),
            selectinload(models.HomePage.top_rental_associations)
            .selectinload(models.HomePageTopRental.car)
            .selectinload(models.Car.car_model)
            .selectinload(models.CarModel.category),
            selectinload(models.HomePage.top_rental_associations)
            .selectinload(models.HomePageTopRental.car)
            .selectinload(models.Car.car_model)
            .selectinload(models.CarModel.fuel),
            selectinload(models.HomePage.top_rental_associations)
            .selectinload(models.HomePageTopRental.car)
            .selectinload(models.Car.car_model)
            .selectinload(models.CarModel.capacity),
            selectinload(models.HomePage.top_rental_associations)
            .selectinload(models.HomePageTopRental.car)
            .selectinload(models.Car.car_model)
            .selectinload(models.CarModel.features),
            selectinload(models.HomePage.featured_review_associations)
            .selectinload(models.HomePageFeaturedReview.review)
            .selectinload(models.Review.creator),
            selectinload(models.HomePage.featured_review_associations)
            .selectinload(models.HomePageFeaturedReview.review)
            .selectinload(models.Review.car)
            .selectinload(models.Car.car_model),
            joinedload(models.HomePage.modified_by_user),
        )
        count_query = select(func.count()).select_from(models.HomePage)
        total = (await db.execute(count_query)).scalar_one()
        items_query = (
            base_query.order_by(models.HomePage.effective_from.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await db.execute(items_query)).scalars().unique().all()
        return items, total


    async def create_homepage_with_nested(
        self,
        db: AsyncSession,
        homepage_data: dict,
        promotions_data: List[dict],
        car_categories_data: List[dict],
        contact_faqs_data: List[dict],
        top_rentals_data: List[dict],
        featured_reviews_data: List[dict],
    ) -> models.HomePage:
        """
        Create a new homepage configuration with nested objects
        
        Args:
            db: Database session
            homepage_data: Homepage master data
            promotions_data: List of promotion data
            car_categories_data: List of car category data
            contact_faqs_data: List of contact FAQ data
            top_rentals_data: List of top rental data
            featured_reviews_data: List of featured review data
        
        Returns:
            Newly created HomePage object
        """
        if homepage_data.get("is_active", False):
            await db.execute(
                sql_update(models.HomePage)
                .where(models.HomePage.is_active.is_(True))
                .values(is_active=False)
            )
        db_homepage = models.HomePage(**homepage_data)
        db.add(db_homepage)
        await db.flush()
        for promotion_data in promotions_data:
            db_promotion = models.HomePagePromotion(
                **promotion_data, homepage_id=db_homepage.id
            )
            db.add(db_promotion)
        for category_data in car_categories_data:
            db_category = models.HomePageCarCategory(
                **category_data, homepage_id=db_homepage.id
            )
            db.add(db_category)
        for faq_data in contact_faqs_data:
            db_contact_faq = models.HomePageContactFAQ(
                **faq_data, homepage_id=db_homepage.id
            )
            db.add(db_contact_faq)
        for rental_data in top_rentals_data:
            db_top_rental = models.HomePageTopRental(
                **rental_data, homepage_id=db_homepage.id
            )
            db.add(db_top_rental)
        for review_data in featured_reviews_data:
            db_featured_review = models.HomePageFeaturedReview(
                **review_data, homepage_id=db_homepage.id
            )
            db.add(db_featured_review)
        await db.commit()
        await db.refresh(db_homepage)
        return db_homepage


    async def update_homepage_nested(
        self,
        db: AsyncSession,
        homepage_id: int,
        promotions_data: List[dict],
        car_categories_data: List[dict],
        contact_faqs_data: List[dict],
        top_rentals_data: List[dict],
        featured_reviews_data: List[dict],
    ) -> None:
        """
        Update nested objects for an existing homepage configuration
        
        Args:
            db: Database session
            homepage_id: Homepage configuration unique identifier
            promotions_data: List of updated promotion data
            car_categories_data: List of updated car category data
            contact_faqs_data: List of updated contact FAQ data
            top_rentals_data: List of updated top rental data
            featured_reviews_data: List of updated featured review data
        
        Returns:
            None
        """
        await db.execute(
            sql_delete(models.HomePagePromotion).where(
                models.HomePagePromotion.homepage_id == homepage_id
            )
        )
        await db.execute(
            sql_delete(models.HomePageCarCategory).where(
                models.HomePageCarCategory.homepage_id == homepage_id
            )
        )
        await db.execute(
            sql_delete(models.HomePageContactFAQ).where(
                models.HomePageContactFAQ.homepage_id == homepage_id
            )
        )
        await db.execute(
            sql_delete(models.HomePageTopRental).where(
                models.HomePageTopRental.homepage_id == homepage_id
            )
        )
        await db.execute(
            sql_delete(models.HomePageFeaturedReview).where(
                models.HomePageFeaturedReview.homepage_id == homepage_id
            )
        )
        for promotion_data in promotions_data:
            db_promotion = models.HomePagePromotion(
                **promotion_data, homepage_id=homepage_id
            )
            db.add(db_promotion)
        for category_data in car_categories_data:
            db_category = models.HomePageCarCategory(
                **category_data, homepage_id=homepage_id
            )
            db.add(db_category)
        for faq_data in contact_faqs_data:
            db_contact_faq = models.HomePageContactFAQ(**faq_data, homepage_id=homepage_id)
            db.add(db_contact_faq)
        for rental_data in top_rentals_data:
            db_top_rental = models.HomePageTopRental(**rental_data, homepage_id=homepage_id)
            db.add(db_top_rental)
        for review_data in featured_reviews_data:
            db_featured_review = models.HomePageFeaturedReview(
                **review_data, homepage_id=homepage_id
            )
            db.add(db_featured_review)


    async def update_homepage(
        self, db: AsyncSession, db_homepage: models.HomePage, update_data: dict
    ) -> models.HomePage:
        """
        Update homepage configuration with proper active status handling
        
        Args:
            db: Database session
            db_homepage: Existing HomePage object to update
            update_data: Dictionary of fields to update
        
        Returns:
            Updated HomePage object
        """
        if "is_active" in update_data and update_data["is_active"]:
            await db.execute(
                sql_update(models.HomePage)
                .where(models.HomePage.is_active.is_(True))
                .values(is_active=False)
            )
        return await self.update(db, db_homepage, update_data)


    async def set_active_homepage(self, db: AsyncSession, homepage_id: int) -> None:
        """
        Set specific homepage configuration as active and deactivate all others
        
        Args:
            db: Database session
            homepage_id: Homepage configuration unique identifier to activate
        
        Returns:
            None
        """
        await self.set_active_master(db, models.HomePage, homepage_id)


    async def get_admin_help_centre_by_id(
        self, db: AsyncSession, admin_help_id: int
    ) -> Optional[models.AdminHelpCentreMaster]:
        """
        Retrieve admin help centre document by ID with all sections and contents
        
        Args:
            db: Database session
            admin_help_id: Admin help centre document unique identifier
        
        Returns:
            AdminHelpCentreMaster object with sections and contents if found, None otherwise
        """
        query = (
            select(models.AdminHelpCentreMaster)
            .options(
                selectinload(models.AdminHelpCentreMaster.sections).selectinload(
                    models.AdminHelpCentreSection.contents
                ),
                joinedload(models.AdminHelpCentreMaster.modified_by_user),
            )
            .where(models.AdminHelpCentreMaster.id == admin_help_id)
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_active_admin_help_centre(
        self, db: AsyncSession
    ) -> Optional[models.AdminHelpCentreMaster]:
        """
        Retrieve the currently active admin help centre document
        
        Args:
            db: Database session
        
        Returns:
            Active AdminHelpCentreMaster object if found, None otherwise
        """
        query = (
            select(models.AdminHelpCentreMaster)
            .options(
                selectinload(models.AdminHelpCentreMaster.sections).selectinload(
                    models.AdminHelpCentreSection.contents
                ),
                joinedload(models.AdminHelpCentreMaster.modified_by_user),
            )
            .where(models.AdminHelpCentreMaster.is_active.is_(True))
            .order_by(models.AdminHelpCentreMaster.effective_from.desc())
        )
        return (await db.execute(query)).scalar_one_or_none()


    async def get_all_admin_help_centre_paginated(
        self, db: AsyncSession, skip: int, limit: int
    ) -> Tuple[List[models.AdminHelpCentreMaster], int]:
        """
        Retrieve paginated list of all admin help centre documents
        
        Args:
            db: Database session
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (list of AdminHelpCentreMaster objects, total count of records)
        """
        base_query = select(models.AdminHelpCentreMaster).options(
            selectinload(models.AdminHelpCentreMaster.sections).selectinload(
                models.AdminHelpCentreSection.contents
            ),
            joinedload(models.AdminHelpCentreMaster.modified_by_user),
        )
        count_query = select(func.count()).select_from(models.AdminHelpCentreMaster)
        total = (await db.execute(count_query)).scalar_one()
        items_query = (
            base_query.order_by(models.AdminHelpCentreMaster.effective_from.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await db.execute(items_query)).scalars().unique().all()
        return items, total


    async def create_admin_help_centre_with_sections(
        self, db: AsyncSession, admin_help_data: dict, sections_data: List[dict]
    ) -> models.AdminHelpCentreMaster:
        """
        Create a new admin help centre document with sections and contents
        
        Args:
            db: Database session
            admin_help_data: Admin help centre master document data
            sections_data: List of section data with nested contents
        
        Returns:
            Newly created AdminHelpCentreMaster object
        """
        if admin_help_data.get("is_active", False):
            await db.execute(
                sql_update(models.AdminHelpCentreMaster)
                .where(models.AdminHelpCentreMaster.is_active.is_(True))
                .values(is_active=False)
            )
        db_admin_help = models.AdminHelpCentreMaster(**admin_help_data)
        db.add(db_admin_help)
        await db.flush()
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.AdminHelpCentreSection(
                **section_data, admin_help_master_id=db_admin_help.id
            )
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.AdminHelpCentreContent(
                    **content_data, section_id=db_section.id
                )
                db.add(db_content)
        await db.commit()
        await db.refresh(db_admin_help)
        return db_admin_help


    async def update_admin_help_centre_sections(
        self, db: AsyncSession, admin_help_id: int, sections_data: List[dict]
    ) -> None:
        """
        Update sections and contents for an existing admin help centre document
        
        Args:
            db: Database session
            admin_help_id: Admin help centre document unique identifier
            sections_data: List of updated section data with nested contents
        
        Returns:
            None
        """
        await db.execute(
            sql_delete(models.AdminHelpCentreContent).where(
                models.AdminHelpCentreContent.section_id.in_(
                    select(models.AdminHelpCentreSection.id).where(
                        models.AdminHelpCentreSection.admin_help_master_id == admin_help_id
                    )
                )
            )
        )
        await db.execute(
            sql_delete(models.AdminHelpCentreSection).where(
                models.AdminHelpCentreSection.admin_help_master_id == admin_help_id
            )
        )
        for section_data in sections_data:
            contents_data = section_data.pop("contents", [])
            db_section = models.AdminHelpCentreSection(
                **section_data, admin_help_master_id=admin_help_id
            )
            db.add(db_section)
            await db.flush()
            for content_data in contents_data:
                db_content = models.AdminHelpCentreContent(
                    **content_data, section_id=db_section.id
                )
                db.add(db_content)


    async def update_admin_help_centre(
        self, db: AsyncSession, db_admin_help: models.AdminHelpCentreMaster, update_data: dict
    ) -> models.AdminHelpCentreMaster:
        """
        Update admin help centre document with proper active status handling
        
        Args:
            db: Database session
            db_admin_help: Existing AdminHelpCentreMaster object to update
            update_data: Dictionary of fields to update
        
        Returns:
            Updated AdminHelpCentreMaster object
        """
        if "is_active" in update_data and update_data["is_active"]:
            await db.execute(
                sql_update(models.AdminHelpCentreMaster)
                .where(models.AdminHelpCentreMaster.is_active.is_(True))
                .values(is_active=False)
            )
        return await self.update(db, db_admin_help, update_data)


    async def set_active_admin_help_centre(self, db: AsyncSession, admin_help_id: int) -> None:
        """
        Set specific admin help centre document as active and deactivate all others
        
        Args:
            db: Database session
            admin_help_id: Admin help centre document unique identifier to activate
        
        Returns:
            None
        """
        await self.set_active_master(db, models.AdminHelpCentreMaster, admin_help_id)


content_crud = ContentCRUD()
