"""Template model — saved generator presets."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")

    # Generator config
    niche = Column(String, default="")
    caption_style = Column(String, default="brain_rot")
    platform = Column(String, default="youtube")
    duration = Column(String, default="30")
    broll_mode = Column(String, default="none")
    language = Column(String, default="en")
    aspect_ratio = Column(String, default="vertical_9_16")

    is_default = Column(String, default="false")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user = relationship("User", backref="templates")
