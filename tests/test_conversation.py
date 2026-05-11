from __future__ import annotations

from datetime import UTC, datetime

from app.pipelines.conversation_dataframe import (
    build_dataframe,
    conversation_to_text,
    fetch_last_day_messages,
    group_conversations,
)
from app.repositories.message_repository import MessageRepository
from app.schemas.webhook import NormalizedMessage


def test_conversation_grouping_builds_chronological_text(db_session) -> None:
    repository = MessageRepository(db_session)
    reference_now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)

    messages = [
        NormalizedMessage(
            external_message_id="conv-a-1",
            phone="15550002222",
            text="Hi, I want to buy.",
            message_timestamp=datetime(2026, 4, 24, 8, 0, tzinfo=UTC),
            direction="inbound",
            raw_payload={"seed": "conv-a-1"},
            display_name="Buyer One",
            product_external_id=None,
        ),
        NormalizedMessage(
            external_message_id="conv-a-2",
            phone="15550002222",
            text="Sure, I can help with that.",
            message_timestamp=datetime(2026, 4, 24, 8, 5, tzinfo=UTC),
            direction="outbound",
            raw_payload={"seed": "conv-a-2"},
            display_name="Buyer One",
            product_external_id=None,
        ),
        NormalizedMessage(
            external_message_id="conv-b-1",
            phone="15550003333",
            text="Interested in sku-99.",
            message_timestamp=datetime(2026, 4, 24, 9, 0, tzinfo=UTC),
            direction="inbound",
            raw_payload={"seed": "conv-b-1"},
            display_name="Buyer Two",
            product_external_id="sku-99",
        ),
    ]

    for item in messages:
        repository.upsert_from_normalized(item)

    last_day_messages = fetch_last_day_messages(db_session, now=reference_now)
    dataframe = build_dataframe(last_day_messages)
    grouped = group_conversations(dataframe)

    assert dataframe["external_message_id"].tolist() == ["conv-a-1", "conv-a-2", "conv-b-1"]
    assert len(grouped) == 2
    assert grouped[0].phone == "15550002222"
    assert grouped[1].phone == "15550003333"
    assert len(grouped[0].messages) == 2
    assert len(grouped[1].messages) == 1

    assert conversation_to_text(grouped[0]) == (
        "[2026-04-24T08:00:00Z] CLIENT: Hi, I want to buy.\n"
        "[2026-04-24T08:05:00Z] COMPANY: Sure, I can help with that."
    )
    assert conversation_to_text(grouped[1].messages) == (
        "[2026-04-24T09:00:00Z] CLIENT: Interested in sku-99."
    )
