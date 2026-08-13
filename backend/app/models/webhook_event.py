"""Webhook event tracking for idempotency."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text, UniqueConstraint

from ..core.database import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String, nullable=False)  # "stripe" or "whop"
    event_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(Text, default="{}")
    processed = Column(Boolean, default=True)
    error = Column(String, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (UniqueConstraint("source", "event_id", name="uq_webhook_event_source_id"),)
