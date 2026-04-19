"""Data models for local agent skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SkillMetadata:
    name: str
    description: str
    version: str = "0.1.0"
    tags: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SkillDefinition:
    metadata: SkillMetadata
    body: str
    root_dir: Path
    files: dict[str, Path] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.metadata.name

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "version": self.metadata.version,
            "tags": list(self.metadata.tags),
            "inputs": list(self.metadata.inputs),
            "outputs": list(self.metadata.outputs),
            "root_dir": str(self.root_dir),
            "files": {name: str(path) for name, path in self.files.items()},
        }
