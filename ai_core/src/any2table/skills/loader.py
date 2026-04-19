"""Load Anthropic-style skill bundles from the filesystem."""

from __future__ import annotations

from pathlib import Path
import re

from any2table.skills.models import SkillDefinition, SkillMetadata

FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(?P<frontmatter>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)


class SkillLoader:
    """Read local skill bundles stored under `.claude/skills`."""

    def __init__(self, root_dir: str | Path = ".claude/skills") -> None:
        self.root_dir = Path(root_dir)

    def load_all(self) -> list[SkillDefinition]:
        if not self.root_dir.exists():
            return []
        skills: list[SkillDefinition] = []
        for skill_dir in sorted(path for path in self.root_dir.iterdir() if path.is_dir()):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skills.append(self.load_skill(skill_dir))
        return skills

    def load_skill(self, skill_dir: str | Path) -> SkillDefinition:
        skill_dir = Path(skill_dir)
        skill_file = skill_dir / "SKILL.md"
        raw_text = skill_file.read_text(encoding="utf-8")
        match = FRONTMATTER_PATTERN.match(raw_text)
        if not match:
            raise ValueError(f"Skill file is missing YAML frontmatter: {skill_file}")

        metadata = self._parse_frontmatter(match.group("frontmatter"))
        files: dict[str, Path] = {}
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file() and path.name != "SKILL.md":
                files[str(path.relative_to(skill_dir))] = path
        return SkillDefinition(
            metadata=metadata,
            body=match.group("body").strip(),
            root_dir=skill_dir,
            files=files,
        )

    def _parse_frontmatter(self, text: str) -> SkillMetadata:
        values: dict[str, object] = {}
        current_list_key: str | None = None
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") and current_list_key is not None:
                values.setdefault(current_list_key, [])
                cast_list = values[current_list_key]
                if isinstance(cast_list, list):
                    cast_list.append(stripped[2:].strip().strip('"'))
                continue
            if ":" not in line:
                current_list_key = None
                continue
            key, raw_value = line.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value:
                values[key] = raw_value.strip('"')
                current_list_key = None
            else:
                values[key] = []
                current_list_key = key

        if "name" not in values or "description" not in values:
            raise ValueError("Skill frontmatter must include `name` and `description`.")

        return SkillMetadata(
            name=str(values["name"]),
            description=str(values["description"]),
            version=str(values.get("version", "0.1.0")),
            tags=[str(item) for item in values.get("tags", [])],
            inputs=[str(item) for item in values.get("inputs", [])],
            outputs=[str(item) for item in values.get("outputs", [])],
        )
