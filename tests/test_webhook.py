from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.models import Client, Conversation, Message
from app.repositories.message_repository import MessageRepository
from app.schemas.webhook import NormalizedMessage
from app.services.evolution import normalize_evolution_payload


def test_message_normalization_extracts_expected_fields() -> None:
    payload = {
        "event": "MESSAGES_UPSERT",
        "data": {
            "key": {
                "remoteJid": "15551234567@s.whatsapp.net",
                "fromMe": False,
                "id": "wamid-123",
            },
            "pushName": "Taylor",
            "message": {
                "extendedTextMessage": {
                    "text": "I want to continue with the purchase.",
                }
            },
            "messageTimestamp": "1777010400",
            "productId": "sku-123",
        },
    }

    result = normalize_evolution_payload(payload)

    assert result.should_process is True
    assert result.event_name == "MESSAGES_UPSERT"
    assert result.reason is None
    assert result.message is not None
    assert result.message.external_message_id == "wamid-123"
    assert result.message.phone == "15551234567"
    assert result.message.text == "I want to continue with the purchase."
    assert result.message.direction == "inbound"
    assert result.message.display_name == "Taylor"
    assert result.message.product_external_id == "sku-123"
    assert result.message.message_timestamp == datetime(2026, 4, 24, 6, 0, tzinfo=UTC)



def test_idempotent_insert_stores_message_only_once(db_session) -> None:
    repository = MessageRepository(db_session)
    normalized = NormalizedMessage(
        external_message_id="duplicate-message-1",
        phone="15550001111",
        text="Please send pricing.",
        message_timestamp=datetime(2026, 4, 24, 11, 0, tzinfo=UTC),
        direction="inbound",
        raw_payload={"seed": "duplicate-message-1"},
        display_name="Jordan",
        product_external_id=None,
    )

    first_message, first_created = repository.upsert_from_normalized(normalized)
    second_message, second_created = repository.upsert_from_normalized(normalized)

    assert first_created is True
    assert second_created is False
    assert second_message.id == first_message.id

    assert db_session.scalar(select(func.count()).select_from(Client)) == 1
    assert db_session.scalar(select(func.count()).select_from(Conversation)) == 1
    assert db_session.scalar(select(func.count()).select_from(Message)) == 1
