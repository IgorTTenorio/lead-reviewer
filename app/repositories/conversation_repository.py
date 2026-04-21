from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_for_client_and_product(
        self,
        *,
        client_id: UUID,
        product_id: UUID | None,
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(
                Conversation.client_id == client_id,
                Conversation.product_id == product_id,
            )
            .order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_or_create(
        self,
        *,
        client_id: UUID,
        product_id: UUID | None,
        message_timestamp: datetime,
    ) -> Conversation:
        conversation = self.get_latest_for_client_and_product(
            client_id=client_id,
            product_id=product_id,
        )
        if conversation:
            conversation.last_message_at = self._max_timestamp(
                conversation.last_message_at,
                message_timestamp,
            )
            return conversation

        conversation = Conversation(
            client_id=client_id,
            product_id=product_id,
            status="open",
            started_at=message_timestamp,
            last_message_at=message_timestamp,
        )
        self.db.add(conversation)
        self.db.flush()
        return conversation

    @staticmethod
    def _max_timestamp(current: datetime | None, incoming: datetime) -> datetime:
        if current is None:
            return incoming
        current_normalized = ConversationRepository._normalize_datetime(current)
        incoming_normalized = ConversationRepository._normalize_datetime(incoming)
        return max(current_normalized, incoming_normalized)

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
