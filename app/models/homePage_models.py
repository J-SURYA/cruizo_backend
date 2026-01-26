from sqlalchemy import (
    Column,
    String,
    Enum,
    Text,
    Date,
    DateTime,
    Boolean,
    Integer,
    ForeignKey,
    JSON,
    func,
)
from sqlalchemy.orm import relationship


from .base import Base
from .enums import PromotionTypeEnum


class HomePage(Base):
    """
    Homepage content model.
    """

    __tablename__ = "homepage"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    effective_from = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_modified_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_modified_by = Column(String, ForeignKey("users.id"), nullable=True)

    hero_section = Column(JSON, nullable=True)
    about_section = Column(JSON, nullable=True)
    promotions_section = Column(JSON, nullable=True)
    top_rental_section = Column(JSON, nullable=True)
    explore_cars_section = Column(JSON, nullable=True)
    reviews_section = Column(JSON, nullable=True)
    contact_section = Column(JSON, nullable=True)
    footer_section = Column(JSON, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    modified_by_user = relationship(
        "User", foreign_keys=[last_modified_by], lazy="noload"
    )
    promotions = relationship(
        "HomePagePromotion",
        back_populates="homepage",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    explore_cars_categories = relationship(
        "HomePageCarCategory",
        back_populates="homepage",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="HomePageCarCategory.id",
    )
    contact_faqs = relationship(
        "HomePageContactFAQ",
        back_populates="homepage",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="HomePageContactFAQ.order",
    )
    top_rental_associations = relationship(
        "HomePageTopRental",
        back_populates="homepage",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="HomePageTopRental.display_order",
    )
    featured_review_associations = relationship(
        "HomePageFeaturedReview",
        back_populates="homepage",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="HomePageFeaturedReview.display_order",
    )


class HomePagePromotion(Base):
    """
    Home page promotional banners / discount section.
    """

    __tablename__ = "homepage_promotions"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    title = Column(Text, nullable=False)
    subtitle = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    discount = Column(String(10), nullable=False)
    timeline = Column(Date, nullable=False)
    type = Column(Enum(PromotionTypeEnum, name="promotion_type_enum"), nullable=False)
    homepage_id = Column(
        Integer, ForeignKey("homepage.id", ondelete="CASCADE"), nullable=False
    )
    homepage = relationship("HomePage", back_populates="promotions")


class HomePageCarCategory(Base):
    """
    Home page car categories section.
    """

    __tablename__ = "homepage_car_categories"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    price_range = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    homepage_id = Column(
        Integer, ForeignKey("homepage.id", ondelete="CASCADE"), nullable=False
    )
    homepage = relationship("HomePage", back_populates="explore_cars_categories")


class HomePageContactFAQ(Base):
    """
    Home page FAQ and contact info section.
    """

    __tablename__ = "homepage_contact_faqs"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    order = Column(Integer, nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    homepage_id = Column(
        Integer, ForeignKey("homepage.id", ondelete="CASCADE"), nullable=False
    )
    homepage = relationship("HomePage", back_populates="contact_faqs")


class HomePageTopRental(Base):
    """
    Home page top rental cars section.
    """

    __tablename__ = "homepage_top_rentals"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    homepage_id = Column(
        Integer, ForeignKey("homepage.id", ondelete="CASCADE"), nullable=False
    )
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    homepage = relationship("HomePage", back_populates="top_rental_associations")
    car = relationship("Car", lazy="selectin")


class HomePageFeaturedReview(Base):
    """
    Home page featured reviews section.
    """

    __tablename__ = "homepage_featured_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    homepage_id = Column(
        Integer, ForeignKey("homepage.id", ondelete="CASCADE"), nullable=False
    )
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    homepage = relationship("HomePage", back_populates="featured_review_associations")
    review = relationship("Review", lazy="selectin")
