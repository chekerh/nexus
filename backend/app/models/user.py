"""User and subscription models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from ..core.database import Base
import enum


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, default="")
    subscription_tier = Column(SAEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    credits_used_month = Column(Integer, default=0)
    credits_limit_month = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    stripe_customer_id = Column(String, default="")
    stripe_subscription_id = Column(String, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    jobs = relationship("Job", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")
