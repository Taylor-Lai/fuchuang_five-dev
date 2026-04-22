"""Execute local skills with an optional LLM backend."""

from __future__ import annotations

from any2table.skills.adapters import parse_skill_json
from any2table.skills.renderer import render_skill_prompt

SKILL_SYSTEM_PROMPT = (
    "You are executing a reusable Any2table project skill. "
    "Follow the skill instructions strictly and return a single JSON object only."
)


def execute_skill(registry, *, skill_name: str, inputs: dict[str, object]) -> tuple[dict[str, object], str]:
    skill = registry.skill_registry.get(skill_name)
    prompt = render_skill_prompt(skill, inputs)
    if registry.llm_client is None:
        raise RuntimeError("LLM client is not configured.")
    response = registry.llm_client.invoke_json(system_prompt=SKILL_SYSTEM_PROMPT, user_prompt=prompt)
    if response.content is None:
        raise RuntimeError(f"LLM returned empty content for skill '{skill_name}'. Model: {response.model}")
    return parse_skill_json(response.content), response.model
