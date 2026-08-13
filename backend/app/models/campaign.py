"""Campaign model — groups content with shared target platforms and schedules."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    platforms = Column(Text, default='["youtube","instagram","tiktok"]')
    persona_id = Column(String, ForeignKey("personas.id"), nullable=True)
    status = Column(String, default="draft")  # draft | active | paused | completed
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    daily_post_count = Column(
        String, default='{"youtube":1,"instagram":2,"tiktok":2,"twitter":3,"linkedin":1,"facebook":1}'
    )
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user = relationship("User", backref="campaigns")
