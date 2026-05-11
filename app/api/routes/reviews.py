from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, status

from app.services.review_dispatcher import enqueue_review_last_day

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/last-day", status_code=status.HTTP_202_ACCEPTED)
def queue_last_day_review() -> dict[str, str]:
    async_result = enqueue_review_last_day(now=datetime.now(UTC))
    return {
        "status": "queued",
        "task_id": async_result.id,
    }
