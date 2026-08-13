"""Thumbnail and A/B test models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class Thumbnail(Base):
    __tablename__ = "thumbnails"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    clip_index = Column(Integer, nullable=False)
    variant_name = Column(String, default="")  # e.g. "hero-1", "hook-2", "cta-3"
    image_path = Column(String, default="")
    title_overlay = Column(String, default="")
    layout = Column(String, default="centered")  # centered, bottom-text, top-text, split
    score = Column(Float, default=0.0)  # AI quality score 0-10
    is_winner = Column(Boolean, default=False)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    job = relationship("Job", backref="thumbnails")
