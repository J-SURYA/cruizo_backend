from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    Enum,
    Numeric,
    Index,
    UniqueConstraint,
    DateTime,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship


from .base import Base, TimestampMixin
from .enums import TransmissionType


class Category(Base):
    """
    Lookup table for car categories (e.g., SUV, Sedan).
    """

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(100), unique=True, nullable=False)
    car_models = relationship("CarModel", back_populates="category", lazy="selectin")


class Fuel(Base):
    """
    Lookup table for fuel types (e.g., Petrol, Diesel, Electric).
    """

    __tablename__ = "fuels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fuel_name = Column(String(50), unique=True, nullable=False)
    car_models = relationship("CarModel", back_populates="fuel", lazy="selectin")


class Capacity(Base):
    """
    Lookup table for engine capacities (e.g., 1000cc, 1500cc).
    """

    __tablename__ = "capacities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    capacity_value = Column(Integer, unique=True, nullable=False)
    car_models = relationship("CarModel", back_populates="capacity", lazy="selectin")


class Color(Base):
    """
    Lookup table for car colors.
    """

    __tablename__ = "colors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    color_name = Column(String(50), unique=True, nullable=False)
    cars = relationship("Car", back_populates="color", lazy="selectin")


class Feature(Base):
    """
    Lookup table for car features (e.g., Sunroof, Bluetooth).
    """

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_name = Column(String(255), unique=True, nullable=False)
    car_models = relationship(
        "CarModel",
        secondary="car_model_features",
        back_populates="features",
        lazy="selectin",
    )


class CarModelFeature(Base):
    """
    Association table between CarModel and Feature.
    """

    __tablename__ = "car_model_features"

    car_model_id = Column(Integer, ForeignKey("car_models.id"), primary_key=True)
    feature_id = Column(Integer, ForeignKey("features.id"), primary_key=True)

    __table_args__ = (
        UniqueConstraint("car_model_id", "feature_id", name="uq_car_model_feature"),
    )


class CarModel(Base, TimestampMixin):
    """
    Car model details.
    """

    __tablename__ = "car_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    fuel_id = Column(Integer, ForeignKey("fuels.id"), nullable=False)
    capacity_id = Column(Integer, ForeignKey("capacities.id"), nullable=False)

    transmission_type = Column(
        Enum(TransmissionType, name="transmission_type_enum"), nullable=False
    )

    mileage = Column(Integer, nullable=False)
    rental_per_hr = Column(Numeric(10, 2), nullable=False)
    dynamic_rental_price = Column(Numeric(10, 2), nullable=False)
    kilometer_limit_per_hr = Column(Integer, default=50, nullable=False)

    category = relationship("Category", back_populates="car_models", lazy="selectin")
    fuel = relationship("Fuel", back_populates="car_models", lazy="selectin")
    capacity = relationship("Capacity", back_populates="car_models", lazy="selectin")
    features = relationship(
        "Feature",
        secondary="car_model_features",
        back_populates="car_models",
        lazy="selectin",
    )
    cars = relationship(
        "Car", back_populates="car_model", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (Index("ix_car_models_brand_model", "brand", "model"),)


class Car(Base, TimestampMixin):
    """
    Car details.
    """

    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    car_no = Column(String(20), unique=True, nullable=False)

    car_model_id = Column(Integer, ForeignKey("car_models.id"), nullable=False)
    color_id = Column(Integer, ForeignKey("colors.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("status.id"), nullable=False)
    created_by = Column(String(255), ForeignKey("users.id"), nullable=False)

    manufacture_year = Column(Integer, nullable=False)
    image_urls = Column(ARRAY(String(512)), nullable=False)

    last_serviced_date = Column(DateTime(timezone=True), nullable=True)
    service_frequency_months = Column(Integer, default=3, nullable=False)

    insured_till = Column(DateTime(timezone=True), nullable=True)
    pollution_expiry = Column(DateTime(timezone=True), nullable=True)

    car_model = relationship("CarModel", back_populates="cars", lazy="selectin")
    color = relationship("Color", back_populates="cars", lazy="selectin")
    status = relationship("Status", back_populates="cars", lazy="selectin")
    creator = relationship(
        "User",
        back_populates="created_cars",
        foreign_keys=[created_by],
        lazy="selectin",
    )
    bookings = relationship(
        "Booking", back_populates="car", cascade="all, delete-orphan", lazy="selectin"
    )
    reviews = relationship(
        "Review", back_populates="car", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("car_model_id", "color_id", name="uq_car_model_color"),
        Index("ix_cars_car_model_id", "car_model_id"),
        Index("ix_cars_status_id", "status_id"),
    )
