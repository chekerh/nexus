"""Generic webhook idempotency and dead-letter queue."""

import json
import logging

from sqlalchemy.orm import Session

from ..models.webhook_event import WebhookEvent

logger = logging.getLogger("nexus.webhook_base")


def is_already_processed(db: Session, source: str, event_id: str) -> bool:
    """Check if a webhook event has already been processed (idempotency)."""
    if not event_id:
        return False
    return (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.source == source,
            WebhookEvent.event_id == event_id,
        )
        .first()
        is not None
    )


def mark_processed(
    db: Session,
    source: str,
    event_id: str,
    event_type: str,
    payload: dict,
    error: str = "",
) -> WebhookEvent:
    """Record a processed webhook event for idempotency."""
    event = WebhookEvent(
        source=source,
        event_id=event_id,
        event_type=event_type,
        payload=json.dumps(payload),
        processed=not bool(error),
        error=error,
    )
    db.add(event)
    db.commit()
    return event


def dead_letter(
    db: Session,
    source: str,
    event_id: str,
    event_type: str,
    payload: dict,
    error: str,
) -> WebhookEvent:
    """Record a failed webhook event to the dead-letter queue."""
    logger.error("DLQ [%s/%s]: %s — %s", source, event_type, event_id, error)
    return mark_processed(db, source, event_id, event_type, payload, error=error)
