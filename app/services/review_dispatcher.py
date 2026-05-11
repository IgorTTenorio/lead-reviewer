from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from celery.result import AsyncResult

from worker.tasks import review_last_day_task


def enqueue_review_last_day(*, now: datetime | None = None) -> AsyncResult:
    payload = {"now_iso": _normalize_datetime(now).isoformat()} if now else {}
    return review_last_day_task.delay(**payload)


def run_review_last_day_now(*, now: datetime | None = None) -> dict[str, Any]:
    payload = {"now_iso": _normalize_datetime(now).isoformat()} if now else {}
    return review_last_day_task.apply(kwargs=payload).get()


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
