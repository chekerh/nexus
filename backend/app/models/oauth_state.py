from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from ..core.database import Base


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    code_verifier = Column(Text, nullable=True)
    redirect_uri = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
