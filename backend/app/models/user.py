"""User, Tenant, and subscription models."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from ..core.database import Base


class SubscriptionTier(enum.StrEnum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    domain = Column(String, default="")
    is_active = Column(Boolean, default=True)
    max_users = Column(Integer, default=10)
    max_storage_gb = Column(Integer, default=5)
    features = Column(String, default="{}")  # JSON feature flags
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    google_id = Column(String, default="", index=True)
    password_hash = Column(String, default="")
    password_salt = Column(String, default="")  # Per-user salt for password hashing
    display_name = Column(String, default="")
    subscription_tier = Column(SAEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    credits_used_month = Column(Integer, default=0)
    credits_limit_month = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    setup_wizard_complete = Column(Boolean, default=False)
    stripe_customer_id = Column(String, default="")
    stripe_subscription_id = Column(String, default="")
    whop_customer_id = Column(String, default="")
    whop_license_key = Column(String, default="")
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, default="")
    reset_token = Column(String, default="")
    reset_token_expires = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    dunning_count = Column(Integer, default=0)
    last_dunning_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    jobs = relationship("Job", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")
