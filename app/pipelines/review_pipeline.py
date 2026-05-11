from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.pipelines.conversation_dataframe import (
    build_dataframe,
    conversation_to_text,
    fetch_last_day_messages,
    group_conversations,
)
from app.repositories.conversation_review_repository import ConversationReviewRepository
from app.schemas.ai import ConversationAnalysis
from app.services.ai_service import AIService


@dataclass(slots=True)
class ReviewRunItem:
    conversation_id: str
    created: bool
    wants_to_continue: bool | None
    confidence: float
    stage: str


@dataclass(slots=True)
class ReviewRunResult:
    window_started_at: datetime
    window_ended_at: datetime
    processed_conversations: int
    created_reviews: int
    updated_reviews: int
    items: list[ReviewRunItem]


class ReviewPipeline:
    def __init__(self, db: Session, ai_service: AIService | None = None):
        self.db = db
        self.ai_service = ai_service or AIService()
        self.reviews = ConversationReviewRepository(db)

    def review_last_day(self, *, now: datetime | None = None) -> ReviewRunResult:
        window_ended_at = _normalize_datetime(now or datetime.now(UTC))
        window_started_at = window_ended_at - timedelta(hours=24)

        messages = fetch_last_day_messages(self.db, now=window_ended_at)
        dataframe = build_dataframe(messages)
        grouped_conversations = group_conversations(dataframe)

        items: list[ReviewRunItem] = []
        created_reviews = 0
        updated_reviews = 0

        for group in grouped_conversations:
            conversation_text = conversation_to_text(group)
            analysis = self.ai_service.analyze_conversation(conversation_text)
            review, created = self.reviews.upsert(
                conversation_id=UUID(group.conversation_id),
                window_started_at=window_started_at,
                window_ended_at=window_ended_at,
                analysis=analysis,
            )
            if created:
                created_reviews += 1
            else:
                updated_reviews += 1

            items.append(
                ReviewRunItem(
                    conversation_id=str(review.conversation_id),
                    created=created,
                    wants_to_continue=analysis.wants_to_continue,
                    confidence=analysis.confidence,
                    stage=analysis.stage,
                )
            )

        self.db.commit()
        return ReviewRunResult(
            window_started_at=window_started_at,
            window_ended_at=window_ended_at,
            processed_conversations=len(grouped_conversations),
            created_reviews=created_reviews,
            updated_reviews=updated_reviews,
            items=items,
        )



def review_last_day(
    db: Session,
    *,
    now: datetime | None = None,
    ai_service: AIService | None = None,
) -> ReviewRunResult:
    pipeline = ReviewPipeline(db=db, ai_service=ai_service)
    return pipeline.review_last_day(now=now)



def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
