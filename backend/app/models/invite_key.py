import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from ..core.database import Base


class InviteKey(Base):
    __tablename__ = "invite_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, unique=True, index=True, nullable=False)
    created_by = Column(String, nullable=False)
    max_uses = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
