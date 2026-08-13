"""Rate limit tracking model."""

from sqlalchemy import Column, DateTime, Index, String

from ..core.database import Base


class RateLimitEntry(Base):
    __tablename__ = "rate_limit_entries"

    id = Column(String, primary_key=True)
    ip = Column(String, index=True, nullable=False)
    path = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (Index("ix_rate_limit_ip_expires_at", "ip", "expires_at"),)
