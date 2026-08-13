"""Social media account models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    platform = Column(String, nullable=False)  # tiktok | instagram | youtube
    account_name = Column(String, nullable=False)
    auth_mode = Column(String, default="manual")
    notes = Column(String, default="")
    is_active = Column(Boolean, default=True)

    # Encrypted tokens
    oauth_refresh_token_enc = Column(Text, default="")
    instagram_user_id = Column(String, default="")
    instagram_access_token_enc = Column(Text, default="")
    tiktok_open_id = Column(String, default="")
    tiktok_refresh_token_enc = Column(Text, default="")
    tiktok_access_token_enc = Column(Text, default="")
    twitter_user_id = Column(String, default="")
    twitter_access_token_enc = Column(Text, default="")
    facebook_page_id = Column(String, default="")
    facebook_access_token_enc = Column(Text, default="")
    linkedin_user_id = Column(String, default="")
    linkedin_access_token_enc = Column(Text, default="")
    youtube_privacy_status = Column(String, default="private")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_social_accounts_user_active", "user_id", "is_active"),)

    user = relationship("User")


class AccountGroup(Base):
    __tablename__ = "account_groups"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user = relationship("User")


class GroupAccount(Base):
    __tablename__ = "group_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String, ForeignKey("account_groups.id"), nullable=False)
    account_id = Column(String, ForeignKey("social_accounts.id"), nullable=False)
