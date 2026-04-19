"""Helpers for rendering skill instructions and runtime context."""

from __future__ import annotations

import json

from any2table.skills.models import SkillDefinition


def render_skill_prompt(skill: SkillDefinition, inputs: dict[str, object]) -> str:
    """Build a prompt-like text block from a skill bundle and runtime inputs."""
    input_payload = json.dumps(inputs, ensure_ascii=False, indent=2, default=str)
    return (
        f"# Skill: {skill.metadata.name}\n"
        f"Description: {skill.metadata.description}\n\n"
        f"{skill.body}\n\n"
        "# Runtime Inputs\n"
        f"```json\n{input_payload}\n```\n"
    )
