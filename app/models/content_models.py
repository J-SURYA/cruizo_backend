from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    func,
)
from sqlalchemy.orm import relationship


from .base import Base


class TermsMaster(Base):
    """
    Master table for Terms & Conditions versioning.
    """

    __tablename__ = "terms_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    effective_from = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_modified_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_modified_by = Column(String, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    sections = relationship(
        "TermsSection",
        back_populates="terms_master",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="TermsSection.order",
    )
    modified_by_user = relationship(
        "User", foreign_keys=[last_modified_by], lazy="noload"
    )


class TermsSection(Base):
    """
    Terms section inside a Terms & Conditions version.
    """

    __tablename__ = "terms_section"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    terms_master_id = Column(
        Integer, ForeignKey("terms_master.id", ondelete="CASCADE"), nullable=False
    )
    terms_master = relationship("TermsMaster", back_populates="sections")
    contents = relationship(
        "TermsContent",
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="TermsContent.order",
    )


class TermsContent(Base):
    """
    Terms content blocks under a Terms & Conditions section.
    """

    __tablename__ = "terms_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    text = Column(String, nullable=True)
    qa = Column(JSON, nullable=True)
    table = Column(JSON, nullable=True)
    section_id = Column(
        Integer, ForeignKey("terms_section.id", ondelete="CASCADE"), nullable=False
    )
    section = relationship("TermsSection", back_populates="contents")


class HelpCentreMaster(Base):
    """
    Master controller for Help Centre versioning.
    """

    __tablename__ = "help_centre_master"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    effective_from = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_modified_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_modified_by = Column(String, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sections = relationship(
        "HelpCentreSection",
        back_populates="help_master",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="HelpCentreSection.order",
    )
    modified_by_user = relationship(
        "User", foreign_keys=[last_modified_by], lazy="noload"
    )


class HelpCentreSection(Base):
    """
    Help Centre section inside a Help Centre version.
    """

    __tablename__ = "help_centre_section"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    help_master_id = Column(
        Integer, ForeignKey("help_centre_master.id", ondelete="CASCADE"), nullable=False
    )
    help_master = relationship("HelpCentreMaster", back_populates="sections")
    contents = relationship(
        "HelpCentreContent",
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="HelpCentreContent.order",
    )


class HelpCentreContent(Base):
    """
    Help Centre content blocks under a Help Centre section.
    """

    __tablename__ = "help_centre_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    text = Column(String, nullable=True)
    qa = Column(JSON, nullable=True)
    table = Column(JSON, nullable=True)
    section_id = Column(
        Integer,
        ForeignKey("help_centre_section.id", ondelete="CASCADE"),
        nullable=False,
    )
    section = relationship("HelpCentreSection", back_populates="contents")


class PrivacyPolicyMaster(Base):
    """
    Master controller for Privacy Policy versioning.
    """

    __tablename__ = "privacy_policy_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    effective_from = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_modified_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_modified_by = Column(String, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sections = relationship(
        "PrivacyPolicySection",
        back_populates="privacy_master",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="PrivacyPolicySection.order",
    )
    modified_by_user = relationship(
        "User", foreign_keys=[last_modified_by], lazy="noload"
    )


class PrivacyPolicySection(Base):
    """
    Privacy Policy section inside a Privacy Policy version.
    """

    __tablename__ = "privacy_policy_section"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    privacy_master_id = Column(
        Integer,
        ForeignKey("privacy_policy_master.id", ondelete="CASCADE"),
        nullable=False,
    )
    privacy_master = relationship("PrivacyPolicyMaster", back_populates="sections")
    contents = relationship(
        "PrivacyPolicyContent",
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="PrivacyPolicyContent.order",
    )


class PrivacyPolicyContent(Base):
    """
    Privacy Policy content blocks under a Privacy Policy section.
    """

    __tablename__ = "privacy_policy_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    text = Column(String, nullable=True)
    qa = Column(JSON, nullable=True)
    table = Column(JSON, nullable=True)
    section_id = Column(
        Integer,
        ForeignKey("privacy_policy_section.id", ondelete="CASCADE"),
        nullable=False,
    )
    section = relationship("PrivacyPolicySection", back_populates="contents")


class FAQMaster(Base):
    """
    Master controller for FAQ versioning.
    """

    __tablename__ = "faq_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    effective_from = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_modified_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_modified_by = Column(String, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sections = relationship(
        "FAQSection",
        back_populates="faq_master",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="FAQSection.order",
    )
    modified_by_user = relationship(
        "User", foreign_keys=[last_modified_by], lazy="noload"
    )


class FAQSection(Base):
    """
    FAQ section inside a FAQ version.
    """

    __tablename__ = "faq_section"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    faq_master_id = Column(
        Integer, ForeignKey("faq_master.id", ondelete="CASCADE"), nullable=False
    )
    faq_master = relationship("FAQMaster", back_populates="sections")
    contents = relationship(
        "FAQContent",
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="FAQContent.order",
    )


class FAQContent(Base):
    """
    FAQ content blocks under a FAQ section.
    """

    __tablename__ = "faq_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    text = Column(String, nullable=True)
    qa = Column(JSON, nullable=True)
    table = Column(JSON, nullable=True)
    section_id = Column(
        Integer, ForeignKey("faq_section.id", ondelete="CASCADE"), nullable=False
    )

    section = relationship("FAQSection", back_populates="contents")


class AdminHelpCentreMaster(Base):
    """
    Master controller for Admin Help Centre versioning.
    """

    __tablename__ = "admin_help_centre_master"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    effective_from = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_modified_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_modified_by = Column(String, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sections = relationship(
        "AdminHelpCentreSection",
        back_populates="admin_help_master",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="AdminHelpCentreSection.order",
    )
    modified_by_user = relationship(
        "User", foreign_keys=[last_modified_by], lazy="noload"
    )


class AdminHelpCentreSection(Base):
    """
    Admin Help Centre section inside an Admin Help Centre version.
    """

    __tablename__ = "admin_help_centre_section"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    icon = Column(String, nullable=True)
    admin_help_master_id = Column(
        Integer,
        ForeignKey("admin_help_centre_master.id", ondelete="CASCADE"),
        nullable=False,
    )
    admin_help_master = relationship("AdminHelpCentreMaster", back_populates="sections")
    contents = relationship(
        "AdminHelpCentreContent",
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="AdminHelpCentreContent.order",
    )


class AdminHelpCentreContent(Base):
    """
    Admin Help Centre content blocks under an Admin Help Centre section.
    """

    __tablename__ = "admin_help_centre_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    text = Column(String, nullable=True)
    qa = Column(JSON, nullable=True)
    table = Column(JSON, nullable=True)
    section_id = Column(
        Integer,
        ForeignKey("admin_help_centre_section.id", ondelete="CASCADE"),
        nullable=False,
    )
    section = relationship("AdminHelpCentreSection", back_populates="contents")
