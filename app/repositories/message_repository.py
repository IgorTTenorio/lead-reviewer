from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Message
from app.services.conversation_assignment import ConversationAssignmentService
from app.schemas.webhook import NormalizedMessage


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db
        self.assignment_service = ConversationAssignmentService(db)

    def upsert_from_normalized(self, normalized_message: NormalizedMessage) -> tuple[Message, bool]:
        for _ in range(2):
            existing = self.get_by_external_message_id(normalized_message.external_message_id)
            if existing:
                return existing, False

            try:
                assignment = self.assignment_service.assign(normalized_message)

                message = Message(
                    conversation_id=assignment.conversation.id,
                    client_id=assignment.client.id,
                    product_id=assignment.product.id if assignment.product else None,
                    external_message_id=normalized_message.external_message_id,
                    direction=normalized_message.direction,
                    text=normalized_message.text,
                    message_timestamp=normalized_message.message_timestamp,
                    raw_payload=normalized_message.raw_payload,
                )
                self.db.add(message)
                self.db.commit()
                self.db.refresh(message)
                return message, True
            except IntegrityError:
                self.db.rollback()

        existing = self.get_by_external_message_id(normalized_message.external_message_id)
        if existing:
            return existing, False

        raise RuntimeError("message upsert failed after retry")

    def get_by_external_message_id(self, external_message_id: str) -> Message | None:
        stmt = select(Message).where(Message.external_message_id == external_message_id)
        return self.db.execute(stmt).scalar_one_or_none()
