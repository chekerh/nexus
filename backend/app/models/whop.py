"""Whop license and purchase tracking models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class WhopLicense(Base):
    __tablename__ = "whop_licenses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    license_key = Column(String, unique=True, nullable=False, index=True)
    product_id = Column(String, nullable=False)
    tier = Column(String, nullable=False)
    status = Column(String, default="active")
    whop_purchase_id = Column(String, default="")
    whop_customer_id = Column(String, default="")
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user = relationship("User", backref="whop_licenses")


class WhopEvent(Base):
    __tablename__ = "whop_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String, nullable=False)
    whop_event_id = Column(String, unique=True, nullable=True)
    payload = Column(Text, default="{}")
    processed = Column(Boolean, default=False)
    error = Column(String, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
