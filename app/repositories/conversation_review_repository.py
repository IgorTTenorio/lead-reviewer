from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConversationReview
from app.schemas.ai import ConversationAnalysis


class ConversationReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_window(
        self,
        *,
        conversation_id: UUID,
        window_started_at: datetime,
        window_ended_at: datetime,
    ) -> ConversationReview | None:
        stmt = select(ConversationReview).where(
            ConversationReview.conversation_id == conversation_id,
            ConversationReview.window_started_at == window_started_at,
            ConversationReview.window_ended_at == window_ended_at,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        *,
        conversation_id: UUID,
        window_started_at: datetime,
        window_ended_at: datetime,
        analysis: ConversationAnalysis,
    ) -> tuple[ConversationReview, bool]:
        review = self.get_by_window(
            conversation_id=conversation_id,
            window_started_at=window_started_at,
            window_ended_at=window_ended_at,
        )
        created = review is None

        if review is None:
            review = ConversationReview(
                conversation_id=conversation_id,
                window_started_at=window_started_at,
                window_ended_at=window_ended_at,
            )
            self.db.add(review)

        review.wants_to_continue = analysis.wants_to_continue
        review.confidence = analysis.confidence
        review.stage = analysis.stage
        review.summary = analysis.summary
        review.evidence = analysis.evidence
        review.next_action = analysis.next_action
        review.model_provider = analysis.provider
        review.model_name = analysis.model_name
        review.raw_response = analysis.raw_response
        self.db.flush()
        return review, created
