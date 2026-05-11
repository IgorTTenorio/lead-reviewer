from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    wants_to_continue: bool | None
    confidence: float = Field(ge=0.0, le=1.0)
    stage: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    next_action: str
    provider: str | None = None
    model_name: str | None = None
    raw_response: dict[str, Any] | None = None

    @field_validator("stage", "summary", "next_action")
    @classmethod
    def _strip_text_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("evidence", mode="before")
    @classmethod
    def _normalize_evidence(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []
