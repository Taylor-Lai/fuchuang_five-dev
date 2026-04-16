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


def validate_structuring_skill_output(result: dict) -> tuple[bool, str]:
    """Validate paragraph-structuring and table-row-extraction skill output structure."""
    if "records" not in result:
        return False, "Skill output missing 'records' field"
    if not isinstance(result["records"], list):
        return False, f"'records' must be a list, got {type(result['records']).__name__}"
    for i, record in enumerate(result["records"]):
        if not isinstance(record, dict):
            return False, f"records[{i}] must be a dict"
        if "values" not in record or not isinstance(record["values"], dict):
            return False, f"records[{i}] missing 'values' dict"
    return True, ""
