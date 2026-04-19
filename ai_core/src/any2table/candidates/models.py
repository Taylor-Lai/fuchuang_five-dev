"""Candidate records used between extraction and final write-back."""

from __future__ import annotations

from dataclasses import dataclass, field

from any2table.core.models import DictSerializable


@dataclass(slots=True)
class CandidateRecord(DictSerializable):
    candidate_id: str
    target_table_id: str
    row_identity: dict[str, object] = field(default_factory=dict)
    values: dict[str, object] = field(default_factory=dict)
    field_evidence: dict[str, list[str]] = field(default_factory=dict)
    confidence: float = 0.0
    source_strategy: str = "unknown"
    entity_level: str = "unknown"
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
