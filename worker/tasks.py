from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from app.db.session import get_session_factory
from app.pipelines.review_pipeline import review_last_day
from worker.main import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.review_last_day", bind=True)
def review_last_day_task(self, now_iso: str | None = None) -> dict[str, Any]:
    del self
    now = _parse_datetime(now_iso) if now_iso else None
    session_factory = get_session_factory()
    session = session_factory()
    try:
        result = review_last_day(session, now=now)
        payload = {
            "window_started_at": result.window_started_at.isoformat(),
            "window_ended_at": result.window_ended_at.isoformat(),
            "processed_conversations": result.processed_conversations,
            "created_reviews": result.created_reviews,
            "updated_reviews": result.updated_reviews,
            "items": [asdict(item) for item in result.items],
        }
        logger.info(
            "Completed asynchronous review pipeline run",
            extra={
                "processed_conversations": result.processed_conversations,
                "created_reviews": result.created_reviews,
                "updated_reviews": result.updated_reviews,
            },
        )
        return payload
    except Exception:
        session.rollback()
        logger.exception("Review pipeline task failed")
        raise
    finally:
        session.close()



def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
