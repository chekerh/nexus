"""Persistent job model for the pipeline queue."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="pending", index=True)  # pending | running | completed | failed | cancelled
    filename = Column(String, default="")
    video_path = Column(String, default="")
    endscreen_path = Column(String, default="")
    cta_text = Column(String, default="Link in bio to try it free.")
    source = Column(String, default="upload")  # upload | drive
    drive_url = Column(String, default="")
    target_language = Column(String, default="en")  # en | es | fr | de | etc.
    aspect_ratio = Column(
        String, default="vertical_9_16"
    )  # source | vertical_9_16 | square_1_1 | portrait_4_5 | landscape_16_9

    transcript = Column(Text, default="")
    analysis_json = Column(Text, default="")
    clips_json = Column(Text, default="")
    thinking_json = Column(Text, default="[]")
    error = Column(String, default="")

    timing_transcription = Column(Float, default=0.0)
    timing_analysis = Column(Float, default=0.0)
    timing_cutting = Column(Float, default=0.0)
    timing_total = Column(Float, default=0.0)

    # Progress tracking for SSE
    progress_stage = Column(String, default="")  # transcription, analysis, cutting, completed
    progress_percent = Column(Integer, default=0)
    progress_message = Column(String, default="")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_jobs_user_created", "user_id", "created_at"),
        Index("ix_jobs_user_status", "user_id", "status"),
    )

    user = relationship("User", back_populates="jobs")
