"""Build candidate records from rule outputs and agent skill outputs."""

from __future__ import annotations

from any2table.candidates.models import CandidateRecord
from any2table.core.models import CanonicalDocument, StructuredRecord, TaskSpec, TemplateSpec
from any2table.extractors import _extract_records_from_paragraph_evidence, _extract_records_from_row_evidence


PROVINCE_TOKENS = ("省", "自治区", "直辖市", "兵团")
CITY_TOKENS = ("市", "州", "地区")


def identity_fields_for_target_fields(
    target_fields: list[str],
    *,
    field_specs: list | None = None,
) -> list[str]:
    if field_specs:
        TEXT_LIKE = {"string", "text", "str", ""}
        for spec in field_specs:
            dt = (getattr(spec, "data_type", None) or "").lower()
            if dt in TEXT_LIKE or not dt:
                return [spec.field_name]
        return [field_specs[0].field_name]
    identity_fields = [field_name for field_name in ("国家/地区", "城市") if field_name in target_fields]
    if identity_fields:
        return identity_fields
    return target_fields[:1]


def infer_target_entity_level(target_fields: list[str]) -> str:
    if "城市" in target_fields:
        return "city"
    if "国家/地区" in target_fields:
        return "country"
    return "row"


def build_row_identity(
    values: dict[str, object],
    target_fields: list[str],
    *,
    allow_fallback: bool = True,
) -> dict[str, object]:
    identity: dict[str, object] = {}
    for field_name in identity_fields_for_target_fields(target_fields):
        if values.get(field_name) not in (None, ""):
            identity[field_name] = values[field_name]
    if identity or not allow_fallback:
        return identity
    for field_name in target_fields:
        value = values.get(field_name)
        if value not in (None, ""):
            identity[field_name] = value
            break
    return identity


def has_required_row_identity(row_identity: dict[str, object], target_entity_level: str) -> bool:
    if target_entity_level == "country":
        return row_identity.get("国家/地区") not in (None, "")
    if target_entity_level == "city":
        return row_identity.get("城市") not in (None, "")
    return bool(row_identity)


def missing_required_row_identity_fields(row_identity: dict[str, object], target_entity_level: str) -> list[str]:
    required_fields: list[str] = []
    if target_entity_level == "country":
        required_fields = ["国家/地区"]
    elif target_entity_level == "city":
        required_fields = ["城市"]
    return [field_name for field_name in required_fields if row_identity.get(field_name) in (None, "")]


def _build_candidate_row_identity(
    values: dict[str, object],
    target_fields: list[str],
    entity_level: str,
) -> dict[str, object]:
    return build_row_identity(
        values,
        target_fields,
        allow_fallback=entity_level == "row",
    )


def structured_record_to_candidate(
    record: StructuredRecord,
    *,
    target_fields: list[str],
    source_strategy: str,
    entity_level: str,
    metadata: dict[str, object] | None = None,
) -> CandidateRecord:
    row_identity = _build_candidate_row_identity(record.values, target_fields, entity_level)
    target_entity_level = infer_target_entity_level(target_fields)
    merged_metadata = dict(metadata or {})
    merged_metadata.setdefault("target_entity_level", target_entity_level)
    merged_metadata.setdefault("row_identity_complete", has_required_row_identity(row_identity, target_entity_level))
    return CandidateRecord(
        candidate_id=record.record_id,
        target_table_id=record.target_table_id,
        row_identity=row_identity,
        values={field_name: record.values.get(field_name) for field_name in target_fields},
        field_evidence={field_name: list(evidence_ids) for field_name, evidence_ids in record.field_sources.items()},
        confidence=record.confidence,
        source_strategy=source_strategy,
        entity_level=entity_level,
        notes=list(record.notes),
        metadata=merged_metadata,
    )


def build_rule_candidates(task_spec: TaskSpec, template_spec: TemplateSpec, evidence_pack) -> list[CandidateRecord]:
    candidates: list[CandidateRecord] = []
    for target_table in template_spec.target_tables:
        target_fields = [field.field_name for field in target_table.schema]
        target_entity_level = infer_target_entity_level(target_fields)
        row_records = _extract_records_from_row_evidence(target_table, task_spec, evidence_pack)
        paragraph_records = _extract_records_from_paragraph_evidence(target_table, task_spec, evidence_pack)
        for record in [*row_records, *paragraph_records]:
            candidates.append(
                structured_record_to_candidate(
                    record,
                    target_fields=target_fields,
                    source_strategy="rule",
                    entity_level=target_entity_level,
                    metadata={"builder": "rule_extractor"},
                )
            )
    return candidates


def _infer_source_entity_level(source_doc: CanonicalDocument, notes: list[str], source_paragraph_ids: list[str]) -> str:
    joined_notes = " ".join(notes)
    if any(token in joined_notes for token in PROVINCE_TOKENS):
        return "province"
    if any(token in joined_notes for token in CITY_TOKENS):
        return "city"

    block_by_id = {block.block_id: block for block in source_doc.blocks}
    for paragraph_id in source_paragraph_ids:
        block = block_by_id.get(paragraph_id)
        if block is None:
            continue
        text = block.text or ""
        if any(token in text for token in PROVINCE_TOKENS):
            return "province"
        if any(token in text for token in CITY_TOKENS):
            return "city"
    return "country" if source_doc.doc_type == "docx" else "unknown"


def _filter_values_to_schema(raw_values: dict[str, object], target_fields: list[str]) -> dict[str, object]:
    values = {field_name: None for field_name in target_fields}
    for field_name in target_fields:
        if field_name in raw_values:
            values[field_name] = raw_values[field_name]
    return values


def build_agent_candidates_from_skill_result(
    *,
    task_spec: TaskSpec,
    template_spec: TemplateSpec,
    source_doc: CanonicalDocument,
    skill_result: dict[str, object],
) -> list[CandidateRecord]:
    if not template_spec.target_tables:
        return []
    target_table = template_spec.target_tables[0]
    target_fields = [field.field_name for field in target_table.schema]
    target_entity_level = infer_target_entity_level(target_fields)
    raw_records = skill_result.get("records", [])
    if not isinstance(raw_records, list):
        return []

    candidates: list[CandidateRecord] = []
    for index, raw_candidate in enumerate(raw_records):
        if not isinstance(raw_candidate, dict):
            continue
        raw_values = raw_candidate.get("values", {})
        if not isinstance(raw_values, dict):
            continue
        values = _filter_values_to_schema(raw_values, target_fields)
        if not any(value not in (None, "") for value in values.values()):
            continue
        raw_notes = raw_candidate.get("notes", [])
        notes = [str(value) for value in raw_notes if value]
        raw_paragraph_ids = raw_candidate.get("source_paragraph_ids", [])
        source_paragraph_ids = [str(value) for value in raw_paragraph_ids if value]
        field_evidence = {
            field_name: list(source_paragraph_ids)
            for field_name, value in values.items()
            if value not in (None, "") and source_paragraph_ids
        }
        try:
            confidence = float(raw_candidate.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        source_entity_level = _infer_source_entity_level(source_doc, notes, source_paragraph_ids)
        row_identity = _build_candidate_row_identity(values, target_fields, target_entity_level)
        candidates.append(
            CandidateRecord(
                candidate_id=f"{target_table.target_table_id}#agent-{source_doc.doc_id.split('/')[-1]}-{index}",
                target_table_id=target_table.target_table_id,
                row_identity=row_identity,
                values=values,
                field_evidence=field_evidence,
                confidence=confidence,
                source_strategy="agent",
                entity_level=source_entity_level,
                notes=notes,
                metadata={
                    "builder": "agent_skill",
                    "source_doc_id": source_doc.doc_id,
                    "target_entity_level": target_entity_level,
                    "row_identity_complete": has_required_row_identity(row_identity, target_entity_level),
                    "missing_identity_fields": missing_required_row_identity_fields(row_identity, target_entity_level),
                    "source_paragraph_ids": source_paragraph_ids,
                },
            )
        )
    return candidates


def candidate_to_structured_record(candidate: CandidateRecord) -> StructuredRecord:
    return StructuredRecord(
        record_id=candidate.candidate_id,
        target_table_id=candidate.target_table_id,
        values=dict(candidate.values),
        field_sources={field_name: list(evidence_ids) for field_name, evidence_ids in candidate.field_evidence.items()},
        confidence=candidate.confidence,
        status="ready" if any(value not in (None, "") for value in candidate.values.values()) else "partial",
        notes=list(candidate.notes),
    )


def candidates_to_structured_records(candidates: list[CandidateRecord]) -> list[StructuredRecord]:
    return [candidate_to_structured_record(candidate) for candidate in candidates]
