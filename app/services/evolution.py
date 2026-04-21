from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.message import MessageDirection
from app.schemas.webhook import NormalizedMessage, WebhookNormalizationResult
from app.utils.phone import normalize_phone

MESSAGE_EVENT_NAMES = {
    "MESSAGES_UPSERT",
    "messages.upsert",
    "messages-upsert",
    "SEND_MESSAGE",
    "send-message",
}
IGNORED_JID_SUFFIXES = ("@g.us", "@broadcast")


def normalize_evolution_payload(payload: dict[str, Any]) -> WebhookNormalizationResult:
    event_name = _extract_event_name(payload)
    candidate = _extract_message_candidate(payload)

    if event_name and event_name not in MESSAGE_EVENT_NAMES:
        return WebhookNormalizationResult(
            event_name=event_name,
            should_process=False,
            reason="unsupported_event",
        )

    if candidate is None:
        return WebhookNormalizationResult(
            event_name=event_name,
            should_process=False,
            reason="no_message_candidate",
        )

    key = candidate.get("key") or {}
    remote_jid = key.get("remoteJid")
    if isinstance(remote_jid, str) and remote_jid.endswith(IGNORED_JID_SUFFIXES):
        return WebhookNormalizationResult(
            event_name=event_name,
            should_process=False,
            reason="unsupported_chat_type",
        )

    external_message_id = key.get("id")
    phone = normalize_phone(remote_jid)

    if not external_message_id or not phone:
        return WebhookNormalizationResult(
            event_name=event_name,
            should_process=False,
            reason="missing_required_fields",
        )

    normalized_message = NormalizedMessage(
        external_message_id=str(external_message_id),
        phone=phone,
        text=_extract_message_text(candidate.get("message") or {}),
        message_timestamp=_extract_timestamp(candidate),
        direction=MessageDirection.OUTBOUND if bool(key.get("fromMe")) else MessageDirection.INBOUND,
        raw_payload=payload,
        display_name=_extract_display_name(payload, candidate),
    )
    return WebhookNormalizationResult(
        event_name=event_name or "direct_message_input",
        should_process=True,
        message=normalized_message,
    )



def _extract_event_name(payload: dict[str, Any]) -> str | None:
    for key in ("event", "type", "eventName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None



def _extract_message_candidate(payload: dict[str, Any]) -> dict[str, Any] | None:
    if _looks_like_message_payload(payload):
        return payload

    data = payload.get("data")
    if isinstance(data, dict):
        if _looks_like_message_payload(data):
            return data
        records = data.get("messages")
        if isinstance(records, list):
            for item in records:
                if isinstance(item, dict) and _looks_like_message_payload(item):
                    return item

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and _looks_like_message_payload(item):
                return item

    records = payload.get("messages")
    if isinstance(records, list):
        for item in records:
            if isinstance(item, dict) and _looks_like_message_payload(item):
                return item

    return None



def _looks_like_message_payload(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("key"), dict) and isinstance(payload.get("message"), dict)



def _extract_display_name(payload: dict[str, Any], candidate: dict[str, Any]) -> str | None:
    for source in (payload, candidate):
        for key in ("pushName", "senderName", "notifyName"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None



def _extract_timestamp(candidate: dict[str, Any]) -> datetime:
    raw_timestamp = candidate.get("messageTimestamp")
    if raw_timestamp is None:
        raw_timestamp = candidate.get("message", {}).get("messageTimestamp")

    if raw_timestamp is None:
        return datetime.now(UTC)

    if isinstance(raw_timestamp, str) and raw_timestamp.isdigit():
        raw_timestamp = int(raw_timestamp)

    if isinstance(raw_timestamp, (int, float)):
        if raw_timestamp > 1_000_000_000_000:
            raw_timestamp = raw_timestamp / 1000
        return datetime.fromtimestamp(raw_timestamp, tz=UTC)

    if isinstance(raw_timestamp, str):
        iso_value = raw_timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(iso_value)

    return datetime.now(UTC)



def _extract_message_text(message_payload: dict[str, Any]) -> str | None:
    text_candidates = [
        message_payload.get("conversation"),
        (message_payload.get("extendedTextMessage") or {}).get("text"),
        (message_payload.get("imageMessage") or {}).get("caption"),
        (message_payload.get("videoMessage") or {}).get("caption"),
        (message_payload.get("documentMessage") or {}).get("caption"),
        (message_payload.get("buttonsResponseMessage") or {}).get("selectedDisplayText"),
        (message_payload.get("templateButtonReplyMessage") or {}).get("selectedDisplayText"),
        (message_payload.get("listResponseMessage") or {}).get("title"),
        (message_payload.get("reactionMessage") or {}).get("text"),
    ]

    for candidate in text_candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    return None
