"""OpenAI-compatible LLM client models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LlmResponse:
    content: str
    model: str
    provider: str
    raw: dict[str, object] = field(default_factory=dict)
