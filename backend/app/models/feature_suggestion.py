"""Feature Suggestion model for self-improvement dashboard."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum

from ..core.database import Base


class SuggestionCategory(enum.StrEnum):
    FEATURE = "feature"
    UI = "ui"
    BUGFIX = "bugfix"
    OPTIMIZATION = "optimization"
    SECURITY = "security"


class SuggestionStatus(enum.StrEnum):
    NEW = "new"
    IN_REVIEW = "in_review"
    IMPLEMENTED = "implemented"
    DISMISSED = "dismissed"


class SuggestionEffort(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FeatureSuggestion(Base):
    __tablename__ = "feature_suggestions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    category = Column(SAEnum(SuggestionCategory), nullable=False, default=SuggestionCategory.FEATURE)
    description = Column(Text, nullable=False)
    effort = Column(SAEnum(SuggestionEffort), nullable=False, default=SuggestionEffort.MEDIUM)
    files = Column(Text, default="[]")  # JSON array of file paths
    status = Column(SAEnum(SuggestionStatus), nullable=False, default=SuggestionStatus.NEW)
    votes = Column(Integer, default=0)
    source = Column(String(50), default="ollama")  # ollama, manual, user_feedback
    ollama_model = Column(String(100), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    reviewed_at = Column(DateTime, nullable=True)
    implemented_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_feature_suggestions_status", "status"),
        Index("ix_feature_suggestions_category", "category"),
        Index("ix_feature_suggestions_created_at", "created_at"),
    )

    def to_dict(self):
        import json

        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value if self.category else None,
            "description": self.description,
            "effort": self.effort.value if self.effort else None,
            "files": json.loads(self.files) if self.files else [],
            "status": self.status.value if self.status else None,
            "votes": self.votes,
            "source": self.source,
            "ollama_model": self.ollama_model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "implemented_at": self.implemented_at.isoformat() if self.implemented_at else None,
        }
