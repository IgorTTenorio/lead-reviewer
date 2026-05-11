from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Protocol

import httpx

from app.schemas.ai import ConversationAnalysis


@dataclass(slots=True)
class ProviderResult:
    content: str
    provider: str
    model_name: str | None = None
    raw_response: dict[str, Any] | None = None


class AIProvider(Protocol):
    provider_name: str
    model_name: str | None

    def analyze(self, *, prompt: str, conversation_text: str) -> ProviderResult:
        ...


class MockIntentProvider:
    provider_name = "mock"

    def __init__(self, model_name: str = "keyword-heuristic-v1"):
        self.model_name = model_name

    def analyze(self, *, prompt: str, conversation_text: str) -> ProviderResult:
        del prompt

        lowered = conversation_text.lower()
        positive_patterns = [
            r"\bi want to continue\b",
            r"\bi want to buy\b",
            r"\blet's proceed\b",
            r"\bplease send (?:the )?payment\b",
            r"\bhow do i pay\b",
            r"\bi'll take it\b",
            r"\byes, send me pricing\b",
            r"\bcontinue with the purchase\b",
        ]
        negative_patterns = [
            r"\bnot interested\b",
            r"\bdon't want\b",
            r"\bdo not want\b",
            r"\bstop messaging me\b",
            r"\bno thanks\b",
            r"\bremove me\b",
            r"\bnot now\b",
            r"\bi changed my mind\b",
            r"\bi won't buy\b",
        ]
        uncertain_patterns = [
            r"\bmaybe\b",
            r"\bi'll think about it\b",
            r"\bnot sure\b",
            r"\blater\b",
            r"\bcan you send more details\b",
            r"\bhow much\b",
            r"\bwhat is the price\b",
            r"\bwhat are the options\b",
        ]

        positive_matches = _collect_matches(lowered, positive_patterns)
        negative_matches = _collect_matches(lowered, negative_patterns)
        uncertain_matches = _collect_matches(lowered, uncertain_patterns)

        if positive_matches and not negative_matches:
            payload = {
                "wants_to_continue": True,
                "confidence": 0.9 if len(positive_matches) > 1 else 0.82,
                "stage": "purchase_intent",
                "summary": "The customer shows clear intent to continue the purchase.",
                "evidence": positive_matches[:3],
                "next_action": "Follow up with checkout details or the next transactional step.",
            }
        elif negative_matches and not positive_matches:
            payload = {
                "wants_to_continue": False,
                "confidence": 0.9 if len(negative_matches) > 1 else 0.84,
                "stage": "rejected",
                "summary": "The customer explicitly indicates they do not want to proceed.",
                "evidence": negative_matches[:3],
                "next_action": "Stop sales follow-up and only respond if the customer re-engages.",
            }
        else:
            evidence = (positive_matches + uncertain_matches + negative_matches)[:3]
            payload = {
                "wants_to_continue": None,
                "confidence": 0.55,
                "stage": "uncertain",
                "summary": "The conversation does not provide a clear yes or no about continuing the purchase.",
                "evidence": evidence,
                "next_action": "Send a clarifying follow-up question about whether the customer wants to continue.",
            }

        return ProviderResult(
            content=json.dumps(payload),
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response={"mock": payload},
        )


class OpenAICompatibleProvider:
    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model_name: str,
        timeout_seconds: float,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def analyze(self, *, prompt: str, conversation_text: str) -> ProviderResult:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            response_payload = response.json()

        content = _extract_openai_compatible_content(response_payload)
        return ProviderResult(
            content=content,
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response=response_payload,
        )


SYSTEM_PROMPT = dedent(
    """
    You analyze sales conversations and determine whether the customer wants to continue a purchase.
    Return only valid JSON.
    """
).strip()


JSON_SCHEMA_DESCRIPTION = dedent(
    """
    Return a JSON object with exactly these keys:
    - wants_to_continue: true, false, or null
    - confidence: number between 0 and 1
    - stage: short string describing the purchase stage
    - summary: concise summary of the customer's intent
    - evidence: array of short evidence snippets from the conversation
    - next_action: recommended next sales action
    """
).strip()


CLASSIFICATION_RULES = dedent(
    """
    Classification rules:
    - clear buying signals -> wants_to_continue = true
    - clear rejection or explicit refusal -> wants_to_continue = false
    - uncertainty, mixed signals, or missing evidence -> wants_to_continue = null
    - confidence must reflect how explicit the customer's intent is
    """
).strip()


def build_analysis_prompt(conversation_text: str) -> str:
    return dedent(
        f"""
        Analyze the following WhatsApp conversation.

        {JSON_SCHEMA_DESCRIPTION}

        {CLASSIFICATION_RULES}

        Conversation:
        {conversation_text}
        """
    ).strip()


class AIService:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or build_ai_provider()

    def analyze_conversation(self, conversation_text: str) -> ConversationAnalysis:
        prompt = build_analysis_prompt(conversation_text)
        provider_result = self.provider.analyze(prompt=prompt, conversation_text=conversation_text)
        payload = _parse_json_content(provider_result.content)
        analysis = ConversationAnalysis.model_validate(payload)
        analysis.provider = provider_result.provider
        analysis.model_name = provider_result.model_name
        analysis.raw_response = provider_result.raw_response
        return analysis



def analyze_conversation(conversation_text: str, provider: AIProvider | None = None) -> ConversationAnalysis:
    service = AIService(provider=provider)
    return service.analyze_conversation(conversation_text)



def build_ai_provider() -> AIProvider:
    provider_name = os.getenv("AI_PROVIDER", "mock").strip().lower()

    if provider_name == "mock":
        model_name = os.getenv("AI_MODEL", "keyword-heuristic-v1")
        return MockIntentProvider(model_name=model_name)

    if provider_name in {"openai_compatible", "http_json"}:
        base_url = os.getenv("AI_BASE_URL")
        model_name = os.getenv("AI_MODEL")
        timeout_seconds = float(os.getenv("AI_TIMEOUT_SECONDS", "30"))
        if not base_url or not model_name:
            raise ValueError("AI_BASE_URL and AI_MODEL are required for openai_compatible provider")
        return OpenAICompatibleProvider(
            base_url=base_url,
            api_key=os.getenv("AI_API_KEY"),
            model_name=model_name,
            timeout_seconds=timeout_seconds,
        )

    raise ValueError(f"Unsupported AI_PROVIDER: {provider_name}")



def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        fenced_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if not fenced_match:
            raise ValueError("Provider response did not contain valid JSON") from None
        parsed = json.loads(fenced_match.group(1))

    if not isinstance(parsed, dict):
        raise ValueError("Provider response JSON must be an object")
    return parsed



def _extract_openai_compatible_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            if text_parts:
                return "\n".join(text_parts)

    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    raise ValueError("Unable to extract model content from provider response")



def _collect_matches(text: str, patterns: list[str]) -> list[str]:
    matches: list[str] = []
    for line in text.splitlines():
        normalized_line = line.strip()
        if not normalized_line:
            continue
        for pattern in patterns:
            if re.search(pattern, normalized_line):
                if normalized_line not in matches:
                    matches.append(normalized_line)
                break
    return matches
