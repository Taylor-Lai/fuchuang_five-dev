"""Lightweight knowledge graph models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class GraphEntity:
    entity_id: str
    name: str
    entity_type: str = "concept"
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, object] = field(default_factory=dict)
    source_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class GraphRelation:
    relation_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    confidence: float = 0.6
    evidence: str | None = None
    source_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class KnowledgeGraph:
    graph_id: str
    entities: list[GraphEntity] = field(default_factory=list)
    relations: list[GraphRelation] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
