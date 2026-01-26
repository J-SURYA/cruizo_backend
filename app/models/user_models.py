from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    Boolean,
    DateTime,
    Date,
    func,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship


from .base import Base, TimestampMixin


class Role(Base):
    """
    Table representing user roles (admin, customer, support).
    """

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    users = relationship("User", back_populates="role")
    permissions = relationship(
        "Permission", secondary="role_permissions", back_populates="roles"
    )


class Permission(Base):
    """
    Table representing permissions assigned to roles.
    """

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    scope = Column(String(100), nullable=False)
    roles = relationship(
        "Role", secondary="role_permissions", back_populates="permissions"
    )

    __table_args__ = (
        UniqueConstraint("name", "scope", name="uq_permission_name_scope"),
    )


class RolePermission(Base):
    """
    Association table linking roles to permissions.
    """

    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    permission_id = Column(
        Integer, ForeignKey("permissions.id"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )


class Address(Base):
    """
    Stores user address information.
    """

    __tablename__ = "address"

    id = Column(Integer, primary_key=True, autoincrement=True)
    address_line = Column(String(255), nullable=False)
    area = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    customer_details = relationship(
        "CustomerDetails", back_populates="address", uselist=False
    )


class Tag(Base):
    """
    Tags assigned to customers.
    """

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, default="ROOKIE")
    customer_details = relationship("CustomerDetails", back_populates="tag")


class User(Base, TimestampMixin):
    """
    Table to store all user information.
    """

    __tablename__ = "users"

    id = Column(String(255), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("status.id"), nullable=False, index=True)

    referral_code = Column(String(20), unique=True, nullable=True)
    referred_by = Column(String(255), ForeignKey("users.id"), nullable=True)
    referral_count = Column(Integer, nullable=False, default=0)
    total_referrals = Column(Integer, nullable=False, default=0)

    role = relationship("Role", back_populates="users", lazy="selectin")
    status = relationship("Status", back_populates="users", lazy="selectin")

    referred_users = relationship(
        "User",
        back_populates="referrer",
        foreign_keys=[referred_by],
        lazy="selectin",
    )
    referrer = relationship(
        "User",
        back_populates="referred_users",
        remote_side=[id],
        foreign_keys=[referred_by],
        lazy="selectin",
    )
    customer_details = relationship(
        "CustomerDetails",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    admin_details = relationship(
        "AdminDetails",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    created_cars = relationship(
        "Car",
        back_populates="creator",
        foreign_keys="[Car.created_by]",
        lazy="selectin",
    )
    bookings = relationship(
        "Booking",
        back_populates="booker",
        foreign_keys="[Booking.booked_by]",
        lazy="selectin",
    )
    reviews = relationship(
        "Review",
        back_populates="creator",
        foreign_keys="[Review.created_by]",
        lazy="selectin",
    )
    sent_notifications = relationship(
        "Notification",
        back_populates="sender",
        foreign_keys="[Notification.sender_id]",
        lazy="selectin",
    )
    received_notifications = relationship(
        "Notification",
        back_populates="receiver",
        foreign_keys="[Notification.receiver_id]",
        lazy="selectin",
    )
    responded_queries = relationship(
        "Query",
        back_populates="responder",
        foreign_keys="[Query.responded_by]",
        lazy="selectin",
    )


class CustomerDetails(Base):
    """
    Additional customer profile fields.
    """

    __tablename__ = "customer_details"

    customer_id = Column(String(255), ForeignKey("users.id"), primary_key=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(10), unique=True, nullable=True)
    dob = Column(Date, nullable=True)
    gender = Column(String(50), nullable=True)
    profile_url = Column(String(512), nullable=True)
    address_id = Column(Integer, ForeignKey("address.id"), nullable=True, unique=True)
    aadhaar_no = Column(String(12), unique=True, nullable=True)
    license_no = Column(String(20), unique=True, nullable=True)
    license_front_url = Column(String(512), nullable=True)
    aadhaar_front_url = Column(String(512), nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False, index=True)
    rookie_benefit_used = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="customer_details", lazy="selectin")
    address = relationship(
        "Address", back_populates="customer_details", lazy="selectin"
    )
    tag = relationship("Tag", back_populates="customer_details", lazy="selectin")


class AdminDetails(Base):
    """
    Additional admin profile fields.
    """

    __tablename__ = "admin_details"

    admin_id = Column(String(255), ForeignKey("users.id"), primary_key=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(10), unique=True, nullable=True)
    profile_url = Column(String(512), nullable=True)
    user = relationship("User", back_populates="admin_details", lazy="selectin")


class UserSession(Base):
    """
    Tracks user sessions for JWT refresh tokens.
    """

    __tablename__ = "user_sessions"

    jti = Column(String(255), primary_key=True, doc="JWT ID")
    user_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    refresh_token = Column(String(512), unique=True, nullable=False)
    is_revoked = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    device_info = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user = relationship("User", back_populates="sessions", lazy="selectin")


class RevokedToken(Base):
    """
    Tracks revoked JWT tokens.
    """

    __tablename__ = "revoked_tokens"

    jti = Column(String(255), primary_key=True, doc="JWT ID")
    revoked_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
