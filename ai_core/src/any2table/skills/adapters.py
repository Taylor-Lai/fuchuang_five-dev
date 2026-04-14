"""Adapters for normalizing skill outputs."""

from __future__ import annotations

import json
import re

JSON_BLOCK_PATTERN = re.compile(r"```json\s*(?P<payload>.*?)\s*```", re.DOTALL)


def parse_skill_json(text: str) -> dict[str, object]:
    """Parse JSON output from a skill response, with fenced-block fallback."""
    match = JSON_BLOCK_PATTERN.search(text)
    payload = match.group("payload") if match else text
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Skill output is not valid JSON: {exc}. Raw payload (first 200 chars): {payload[:200]}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError("Skill output must be a JSON object.")
    return parsed
