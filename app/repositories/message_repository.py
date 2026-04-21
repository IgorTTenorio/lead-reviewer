from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Client, Conversation, Message
from app.schemas.webhook import NormalizedMessage


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_from_normalized(self, normalized_message: NormalizedMessage) -> tuple[Message, bool]:
        for _ in range(2):
            existing = self.get_by_external_message_id(normalized_message.external_message_id)
            if existing:
                return existing, False

            try:
                client = self._get_or_create_client(
                    phone=normalized_message.phone,
                    display_name=normalized_message.display_name,
                )
                conversation = self._get_or_create_conversation(
                    client_id=client.id,
                    message_timestamp=normalized_message.message_timestamp,
                )

                message = Message(
                    conversation_id=conversation.id,
                    client_id=client.id,
                    product_id=None,
                    external_message_id=normalized_message.external_message_id,
                    direction=normalized_message.direction,
                    text=normalized_message.text,
                    message_timestamp=normalized_message.message_timestamp,
                    raw_payload=normalized_message.raw_payload,
                )
                self.db.add(message)
                conversation.last_message_at = self._max_timestamp(
                    conversation.last_message_at,
                    normalized_message.message_timestamp,
                )
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

    def _get_or_create_client(self, phone: str, display_name: str | None) -> Client:
        stmt = select(Client).where(Client.phone == phone)
        client = self.db.execute(stmt).scalar_one_or_none()
        if client:
            if display_name and not client.display_name:
                client.display_name = display_name
            return client

        client = Client(phone=phone, display_name=display_name)
        self.db.add(client)
        self.db.flush()
        return client

    def _get_or_create_conversation(self, client_id: UUID, message_timestamp: datetime) -> Conversation:
        stmt = (
            select(Conversation)
            .where(Conversation.client_id == client_id, Conversation.product_id.is_(None))
            .order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc())
            .limit(1)
        )
        conversation = self.db.execute(stmt).scalar_one_or_none()
        if conversation:
            if conversation.last_message_at is None:
                conversation.last_message_at = message_timestamp
            return conversation

        conversation = Conversation(
            client_id=client_id,
            product_id=None,
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
        return max(current, incoming)
