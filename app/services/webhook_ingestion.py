from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.repositories.message_repository import MessageRepository
from app.schemas.webhook import WebhookProcessResult
from app.services.evolution import normalize_evolution_payload

logger = logging.getLogger(__name__)


class WebhookIngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MessageRepository(db)

    def process_evolution_payload(self, payload: dict) -> WebhookProcessResult:
        normalization = normalize_evolution_payload(payload)
        if not normalization.should_process or normalization.message is None:
            logger.info(
                "Ignoring Evolution webhook payload",
                extra={
                    "event_name": normalization.event_name,
                    "reason": normalization.reason,
                },
            )
            return WebhookProcessResult(
                status="ignored",
                detail=normalization.reason,
                event_name=normalization.event_name,
            )

        message, created = self.repository.upsert_from_normalized(normalization.message)
        logger.info(
            "Processed Evolution webhook message",
            extra={
                "event_name": normalization.event_name,
                "external_message_id": normalization.message.external_message_id,
                "was_created": created,
                "message_id": str(message.id),
                "conversation_id": str(message.conversation_id),
            },
        )
        return WebhookProcessResult(
            status="processed" if created else "duplicate",
            duplicate=not created,
            detail=None if created else "message already stored",
            event_name=normalization.event_name,
            message_id=str(message.id),
            conversation_id=str(message.conversation_id),
        )
