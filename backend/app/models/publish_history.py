from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String

from ..core.database import Base


class PublishHistory(Base):
    __tablename__ = "publish_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)
    account_id = Column(Integer, nullable=True)
    account_name = Column(String(255), nullable=True)
    clip_filename = Column(String(255), nullable=True)
    title = Column(String(500), nullable=True)
    description = Column(String(2000), nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_publish_history_user_created", "user_id", "created_at"),)
