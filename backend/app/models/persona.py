"""Persona, Post, and Schedule models for social media automation."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class PostStatus(enum.StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PostPlatform(enum.StrEnum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"


class Persona(Base):
    __tablename__ = "personas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    avatar_path = Column(String, default="")
    bio = Column(Text, default="")
    brand_colors = Column(Text, default='{"primary":"#00e5ff","secondary":"#8b5cf6"}')
    voice_description = Column(Text, default="")
    target_audience = Column(Text, default="")
    content_pillars = Column(Text, default="[]")
    tone = Column(String, default="professional")
    platform_settings = Column(Text, default="{}")
    auto_approve = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user = relationship("User", backref="personas")
    posts = relationship("Post", back_populates="persona", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="persona", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id = Column(String, ForeignKey("personas.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=True)
    campaign_id = Column(String, nullable=True, index=True)
    platform = Column(String, nullable=False, index=True)
    content_type = Column(String, default="text")
    title = Column(String, default="")
    body = Column(Text, default="")
    media_path = Column(String, default="")
    status = Column(String, default="draft", index=True)
    scheduled_at = Column(DateTime, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    error = Column(Text, default="")
    source_transcript = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_posts_user_created", "user_id", "created_at"),
        Index("ix_posts_user_status", "user_id", "status"),
    )

    persona = relationship("Persona", back_populates="posts")
    user = relationship("User", backref="posts")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id = Column(String, ForeignKey("personas.id"), nullable=False, index=True)
    platform = Column(String, nullable=False)
    day_of_week = Column(Integer, default=-1)  # 0=Mon..6=Sun, -1=daily
    time = Column(String, default="09:00")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    persona = relationship("Persona", back_populates="schedules")
