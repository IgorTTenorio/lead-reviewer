from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Sequence
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Message, MessageDirection


@dataclass(slots=True)
class GroupedConversation:
    client_id: str
    conversation_id: str
    product_id: str | None
    phone: str
    display_name: str | None
    messages: pd.DataFrame


def fetch_last_day_messages(db: Session, *, now: datetime | None = None) -> list[Message]:
    reference_time = _normalize_datetime(now or datetime.now(UTC))
    since = reference_time - timedelta(hours=24)

    stmt = (
        select(Message)
        .options(
            joinedload(Message.client),
            joinedload(Message.conversation),
            joinedload(Message.product),
        )
        .where(Message.message_timestamp >= since)
        .order_by(Message.message_timestamp.asc(), Message.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())



def build_dataframe(messages: Sequence[Message]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for message in messages:
        timestamp = _normalize_datetime(message.message_timestamp)
        rows.append(
            {
                "message_id": str(message.id),
                "external_message_id": message.external_message_id,
                "client_id": str(message.client_id),
                "conversation_id": str(message.conversation_id),
                "product_id": str(message.product_id) if message.product_id else None,
                "phone": message.client.phone if message.client else None,
                "display_name": message.client.display_name if message.client else None,
                "direction": message.direction.value
                if isinstance(message.direction, MessageDirection)
                else str(message.direction),
                "text": message.text,
                "timestamp": timestamp,
                "timestamp_iso": _format_timestamp(timestamp),
            }
        )

    dataframe = pd.DataFrame(
        rows,
        columns=[
            "message_id",
            "external_message_id",
            "client_id",
            "conversation_id",
            "product_id",
            "phone",
            "display_name",
            "direction",
            "text",
            "timestamp",
            "timestamp_iso",
        ],
    )

    if dataframe.empty:
        return dataframe

    dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"], utc=True)
    return dataframe.sort_values(
        by=["timestamp", "client_id", "conversation_id", "message_id"],
        ascending=True,
        kind="stable",
    ).reset_index(drop=True)



def group_conversations(dataframe: pd.DataFrame) -> list[GroupedConversation]:
    if dataframe.empty:
        return []

    sorted_dataframe = dataframe.sort_values(
        by=["timestamp", "client_id", "conversation_id", "message_id"],
        ascending=True,
        kind="stable",
    )

    groups: list[GroupedConversation] = []
    for (client_id, conversation_id), conversation_df in sorted_dataframe.groupby(
        ["client_id", "conversation_id"],
        sort=False,
        dropna=False,
    ):
        group_frame = conversation_df.reset_index(drop=True)
        first_row = group_frame.iloc[0]
        groups.append(
            GroupedConversation(
                client_id=str(client_id),
                conversation_id=str(conversation_id),
                product_id=_optional_string(first_row.get("product_id")),
                phone=_optional_string(first_row.get("phone")) or "",
                display_name=_optional_string(first_row.get("display_name")),
                messages=group_frame,
            )
        )

    return groups



def conversation_to_text(conversation: pd.DataFrame | GroupedConversation) -> str:
    dataframe = conversation.messages if isinstance(conversation, GroupedConversation) else conversation
    if dataframe.empty:
        return ""

    ordered = dataframe.sort_values(
        by=["timestamp", "message_id"],
        ascending=True,
        kind="stable",
    )
    lines: list[str] = []
    for row in ordered.itertuples(index=False):
        speaker = "CLIENT" if row.direction == MessageDirection.INBOUND.value else "COMPANY"
        message_text = row.text.strip() if isinstance(row.text, str) and row.text.strip() else "[no text content]"
        timestamp = row.timestamp
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        lines.append(f"[{_format_timestamp(_normalize_datetime(timestamp))}] {speaker}: {message_text}")

    return "\n".join(lines)



def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)



def _format_timestamp(value: datetime) -> str:
    return _normalize_datetime(value).isoformat().replace("+00:00", "Z")



def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, UUID):
        return str(value)
    if pd.isna(value):
        return None
    return str(value)
