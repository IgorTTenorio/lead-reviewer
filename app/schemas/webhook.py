from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.message import MessageDirection


class NormalizedMessage(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    external_message_id: str
    phone: str
    text: str | None
    message_timestamp: datetime
    direction: MessageDirection
    raw_payload: dict[str, Any]
    display_name: str | None = None
    product_external_id: str | None = None


class WebhookNormalizationResult(BaseModel):
    event_name: str | None = None
    should_process: bool = False
    message: NormalizedMessage | None = None
    reason: str | None = None


class WebhookProcessResult(BaseModel):
    status: str
    message_id: str | None = None
    conversation_id: str | None = None
    duplicate: bool = False
    detail: str | None = None
    event_name: str | None = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
