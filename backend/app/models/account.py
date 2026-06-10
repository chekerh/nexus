"""Social media account models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Table
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
    youtube_privacy_status = Column(String, default="private")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User")


class AccountGroup(Base):
    __tablename__ = "account_groups"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User")


class GroupAccount(Base):
    __tablename__ = "group_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String, ForeignKey("account_groups.id"), nullable=False)
    account_id = Column(String, ForeignKey("social_accounts.id"), nullable=False)
