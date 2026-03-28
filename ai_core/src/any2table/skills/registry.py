"""Registry for loaded local skills."""

from __future__ import annotations

from pathlib import Path

from any2table.skills.loader import SkillLoader
from any2table.skills.models import SkillDefinition


class SkillRegistry:
    """Small in-memory registry for project-local skills."""

    def __init__(self, skills: list[SkillDefinition] | None = None) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        for skill in skills or []:
            self.register(skill)

    @classmethod
    def from_root(cls, root_dir: str | Path = ".claude/skills") -> "SkillRegistry":
        loader = SkillLoader(root_dir=root_dir)
        return cls(loader.load_all())

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition:
        return self._skills[name]

    def list_names(self) -> list[str]:
        return sorted(self._skills)

    def to_dict(self) -> dict[str, object]:
        return {name: skill.to_dict() for name, skill in sorted(self._skills.items())}
