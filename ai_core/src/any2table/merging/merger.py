"""Merge rule and agent candidate records with entity-level safeguards."""

from __future__ import annotations

from dataclasses import dataclass, field

from any2table.candidates.builders import missing_required_row_identity_fields
from any2table.candidates.models import CandidateRecord


@dataclass(slots=True)
class CandidateMergeResult:
    merged_candidates: list[CandidateRecord] = field(default_factory=list)
    rejected_candidates: list[CandidateRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _identity_key(candidate: CandidateRecord) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for key, value in sorted(candidate.row_identity.items()):
        pairs.append((key, "" if value is None else str(value)))
    return tuple(pairs)


def _is_missing(value: object) -> bool:
    return value in (None, "")


def _candidate_rejection_reason(candidate: CandidateRecord, target_entity_level: str) -> str | None:
    if target_entity_level != "row" and candidate.entity_level not in {target_entity_level, "unknown"}:
        return f"entity level {candidate.entity_level} does not match target level {target_entity_level}"

    missing_identity_fields = missing_required_row_identity_fields(candidate.row_identity, target_entity_level)
    if missing_identity_fields:
        missing_text = ", ".join(missing_identity_fields)
        return f"missing required row identity fields: {missing_text}"

    return None


def _merge_into_base(base: CandidateRecord, incoming: CandidateRecord) -> CandidateRecord:
    values = dict(base.values)
    field_evidence = {field_name: list(evidence_ids) for field_name, evidence_ids in base.field_evidence.items()}
    notes = list(base.notes)
    metadata = dict(base.metadata)
    existing = metadata.get("merged_from")
    if not isinstance(existing, list):
        metadata["merged_from"] = [base.candidate_id]
    metadata["merged_from"].append(incoming.candidate_id)

    source_strategies = list(metadata.get("source_strategies", []))
    for strategy in (base.source_strategy, incoming.source_strategy):
        if strategy and strategy not in source_strategies:
            source_strategies.append(strategy)
    if source_strategies:
        metadata["source_strategies"] = source_strategies

    for field_name, value in incoming.values.items():
        if field_name not in values or _is_missing(values.get(field_name)):
            values[field_name] = value
            if field_name in incoming.field_evidence:
                field_evidence[field_name] = list(incoming.field_evidence[field_name])
        elif not _is_missing(value) and incoming.confidence > base.confidence:
            values[field_name] = value
            if field_name in incoming.field_evidence:
                field_evidence[field_name] = list(incoming.field_evidence[field_name])

    for note in incoming.notes:
        if note not in notes:
            notes.append(note)

    return CandidateRecord(
        candidate_id=base.candidate_id,
        target_table_id=base.target_table_id,
        row_identity=dict(base.row_identity),
        values=values,
        field_evidence=field_evidence,
        confidence=max(base.confidence, incoming.confidence),
        source_strategy="merged",
        entity_level=base.entity_level,
        notes=notes,
        metadata=metadata,
    )


def _register_merged_candidate(
    merged: list[CandidateRecord],
    merged_by_key: dict[tuple[tuple[str, str], ...], CandidateRecord],
    candidate: CandidateRecord,
) -> None:
    key = _identity_key(candidate)
    merged.append(candidate)
    if key:
        merged_by_key[key] = candidate


def merge_candidates(
    *,
    rule_candidates: list[CandidateRecord],
    agent_candidates: list[CandidateRecord],
    target_entity_level: str,
) -> CandidateMergeResult:
    merged: list[CandidateRecord] = []
    rejected: list[CandidateRecord] = []
    warnings: list[str] = []
    merged_by_key: dict[tuple[tuple[str, str], ...], CandidateRecord] = {}

    for candidate in [*rule_candidates, *agent_candidates]:
        rejection_reason = _candidate_rejection_reason(candidate, target_entity_level)
        if rejection_reason:
            rejected.append(candidate)
            warnings.append(
                f"Rejected {candidate.source_strategy} candidate {candidate.candidate_id} because {rejection_reason}."
            )
            continue

        key = _identity_key(candidate)
        if key and key in merged_by_key:
            updated = _merge_into_base(merged_by_key[key], candidate)
            index = merged.index(merged_by_key[key])
            merged[index] = updated
            merged_by_key[key] = updated
            continue

        _register_merged_candidate(merged, merged_by_key, candidate)

    return CandidateMergeResult(
        merged_candidates=merged,
        rejected_candidates=rejected,
        warnings=warnings,
    )
