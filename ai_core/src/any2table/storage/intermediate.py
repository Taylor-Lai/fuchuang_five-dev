"""Intermediate artifact dumping for parsed documents and schema outputs."""

from __future__ import annotations

import json
from pathlib import Path

from any2table.candidates import CandidateRecord
from any2table.core.models import CanonicalDocument, TaskSpec, TemplateSpec
from any2table.indexing import build_retrieval_units


INVALID_FILENAME_CHARS = '<>:"/\\|?*'



def _safe_name(value: str) -> str:
    translated = ''.join('_' if char in INVALID_FILENAME_CHARS else char for char in value)
    translated = translated.replace('\n', '_').replace('\r', '_').strip().strip('.')
    return translated or 'unnamed'



def _task_id_from_documents(documents: list[CanonicalDocument]) -> str:
    if not documents:
        return 'empty-task'
    parents = {str(Path(doc.file.path).resolve().parent) for doc in documents}
    if len(parents) == 1:
        return _safe_name(Path(next(iter(parents))).name)
    return _safe_name(Path(documents[0].file.path).resolve().parent.name)



def build_fill_plan(task_spec: TaskSpec, template_spec: TemplateSpec, source_docs: list[CanonicalDocument]) -> dict[str, object]:
    target_table = template_spec.target_tables[0] if template_spec.target_tables else None
    target_fields = list(task_spec.target_fields)
    row_identity_fields: list[str] = []
    for candidate in ("国家/地区", "城市"):
        if candidate in target_fields:
            row_identity_fields.append(candidate)
    if not row_identity_fields and target_fields:
        row_identity_fields.append(target_fields[0])

    target_entity_level = 'row'
    if '国家/地区' in target_fields:
        target_entity_level = 'country'
    elif '城市' in target_fields:
        target_entity_level = 'city'

    source_strategies: dict[str, str] = {}
    source_types = {doc.doc_type for doc in source_docs}
    if 'xlsx' in source_types:
        source_strategies['xlsx'] = 'rule_first'
    if 'docx' in source_types:
        source_strategies['docx'] = 'agent_first'
    if 'txt' in source_types:
        source_strategies['txt'] = 'rule_or_agent_context'

    hard_constraints: dict[str, object] = {}
    soft_hints: list[str] = []
    for constraint in task_spec.constraints:
        if constraint.kind == 'date_range':
            hard_constraints['date_range'] = constraint.value
        elif constraint.kind == 'exact_datetime':
            hard_constraints['exact_datetime'] = constraint.value
        elif constraint.kind == 'request_text':
            soft_hints.append(str(constraint.value))
        else:
            hard_constraints[constraint.constraint_id] = constraint.to_dict()

    if target_table and target_table.description:
        soft_hints.append(target_table.description)

    return {
        'task_id': task_spec.task_id,
        'target_table_id': target_table.target_table_id if target_table else None,
        'target_fields': target_fields,
        'row_identity_fields': row_identity_fields,
        'target_entity_level': target_entity_level,
        'task_policy': task_spec.task_policy,
        'hard_constraints': hard_constraints,
        'soft_hints': soft_hints,
        'source_strategies': source_strategies,
    }



def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')



def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = '\n'.join(json.dumps(row, ensure_ascii=False, default=str) for row in rows)
    path.write_text(content, encoding='utf-8')



def _serialize_candidates(candidates: list[CandidateRecord]) -> list[dict[str, object]]:
    return [candidate.to_dict() for candidate in candidates]



def dump_intermediate_artifacts(
    *,
    root_dir: str,
    documents: list[CanonicalDocument],
    template_spec: TemplateSpec,
    task_spec: TaskSpec,
    source_docs: list[CanonicalDocument],
    rule_candidates: list[CandidateRecord] | None = None,
    agent_candidates: list[CandidateRecord] | None = None,
    merged_candidates: list[CandidateRecord] | None = None,
    rejected_candidates: list[CandidateRecord] | None = None,
    candidate_merge_warnings: list[str] | None = None,
) -> dict[str, object]:
    task_id = _task_id_from_documents(documents)
    task_root = Path(root_dir) / task_id
    parsed_dir = task_root / 'parsed'
    retrieval_dir = task_root / 'retrieval'
    schema_dir = task_root / 'schema'
    candidates_dir = task_root / 'candidates'

    parsed_paths: list[str] = []
    retrieval_paths: list[str] = []

    units_by_doc = build_retrieval_units(documents)
    for doc in documents:
        doc_stem = _safe_name(Path(doc.file.name).stem)
        parsed_path = parsed_dir / f'{doc_stem}.canonical.json'
        retrieval_path = retrieval_dir / f'{doc_stem}.jsonl'
        _write_json(parsed_path, doc.to_dict())
        _write_jsonl(retrieval_path, units_by_doc.get(doc.doc_id, []))
        parsed_paths.append(str(parsed_path))
        retrieval_paths.append(str(retrieval_path))

    template_spec_path = schema_dir / 'template_spec.json'
    task_spec_path = schema_dir / 'task_spec.json'
    fill_plan_path = schema_dir / 'fill_plan.json'

    _write_json(template_spec_path, template_spec.to_dict())
    _write_json(task_spec_path, task_spec.to_dict())
    _write_json(fill_plan_path, build_fill_plan(task_spec, template_spec, source_docs))

    candidate_paths: dict[str, str] = {}
    if rule_candidates is not None:
        path = candidates_dir / 'rule_candidates.json'
        _write_json(path, _serialize_candidates(rule_candidates))
        candidate_paths['rule_candidates'] = str(path)
    if agent_candidates is not None:
        path = candidates_dir / 'agent_candidates.json'
        _write_json(path, _serialize_candidates(agent_candidates))
        candidate_paths['agent_candidates'] = str(path)
    if merged_candidates is not None:
        path = candidates_dir / 'merged_candidates.json'
        _write_json(path, _serialize_candidates(merged_candidates))
        candidate_paths['merged_candidates'] = str(path)
    if rejected_candidates is not None:
        path = candidates_dir / 'rejected_candidates.json'
        _write_json(path, _serialize_candidates(rejected_candidates))
        candidate_paths['rejected_candidates'] = str(path)
    if candidate_merge_warnings is not None:
        path = candidates_dir / 'merge_warnings.json'
        _write_json(path, list(candidate_merge_warnings))
        candidate_paths['merge_warnings'] = str(path)

    return {
        'task_id': task_id,
        'task_root': str(task_root),
        'parsed_paths': parsed_paths,
        'retrieval_paths': retrieval_paths,
        'schema_paths': {
            'template_spec': str(template_spec_path),
            'task_spec': str(task_spec_path),
            'fill_plan': str(fill_plan_path),
        },
        'candidate_paths': candidate_paths,
    }
