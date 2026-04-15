"""Lightweight multi-agent nodes for the first orchestration pass."""

from __future__ import annotations

import json

from any2table.candidates.builders import (
    build_agent_candidates_from_skill_result,
    build_rule_candidates,
    candidates_to_structured_records,
    infer_target_entity_level,
    structured_record_to_candidate,
)
from any2table.core.models import VerificationCheck
from any2table.core.runtime import AgentState
from any2table.indexing.build_units import build_retrieval_units
from any2table.merging import merge_candidates
from any2table.skills.executor import execute_skill
from any2table.skills.renderer import render_skill_prompt

MAX_PARAGRAPH_COUNT = 48
MAX_PARAGRAPH_CHARS = 12000


def _source_doc_summaries(state: AgentState) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for doc in state.source_docs:
        summaries.append(
            {
                "doc_id": doc.doc_id,
                "doc_type": doc.doc_type,
                "metadata": doc.metadata,
                "table_count": len(doc.tables),
                "block_count": len(doc.blocks),
            }
        )
    return summaries


def _attach_skill(registry, state: AgentState, agent_name: str, skill_name: str, mode: str, inputs: dict[str, object]) -> None:
    if not registry.config.enable_skill_runtime or registry.skill_registry is None:
        return
    try:
        skill = registry.skill_registry.get(skill_name)
    except KeyError:
        state.add_log(agent_name, "skill_missing", {"skill": skill_name})
        return

    prompt = render_skill_prompt(skill, inputs)
    state.add_skill_run(
        agent=agent_name,
        skill=skill_name,
        mode=mode,
        input_keys=sorted(inputs.keys()),
        prompt_preview=prompt[:800],
    )
    state.add_log(agent_name, "skill_attached", {"skill": skill_name, "mode": mode})
    state.add_message(
        agent_name,
        "skill",
        f"{agent_name} attached skill {skill_name}.",
        {"skill": skill_name, "mode": mode},
    )


def _execute_skill_if_enabled(
    registry,
    state: AgentState,
    agent_name: str,
    skill_name: str,
    inputs: dict[str, object],
) -> dict[str, object] | None:
    if not registry.config.enable_llm_skill_execution:
        state.add_log(
            agent_name,
            "skill_execution_skipped",
            {"skill": skill_name, "reason": "llm_skill_execution_disabled"},
        )
        return None
    if registry.llm_client is None:
        state.add_log(
            agent_name,
            "skill_execution_skipped",
            {"skill": skill_name, "reason": "llm_client_unavailable"},
        )
        return None

    try:
        result, model = execute_skill(registry, skill_name=skill_name, inputs=inputs)
    except Exception as exc:  # pragma: no cover - network/provider dependent
        state.add_llm_run(
            agent=agent_name,
            skill=skill_name,
            status="error",
            error=str(exc),
        )
        state.add_log(
            agent_name,
            "skill_execution_failed",
            {"skill": skill_name, "error": str(exc)},
        )
        return None

    response_preview = json.dumps(result, ensure_ascii=False, default=str)[:800]
    state.add_llm_run(
        agent=agent_name,
        skill=skill_name,
        status="success",
        model=model,
        response_preview=response_preview,
    )
    state.add_skill_result(agent=agent_name, skill=skill_name, result=result, model=model)
    state.add_message(
        agent_name,
        "skill_result",
        f"{agent_name} executed skill {skill_name}.",
        {"skill": skill_name, "model": model, "result": result},
    )
    return result


def _run_skill(
    registry,
    state: AgentState,
    agent_name: str,
    skill_name: str,
    mode: str,
    inputs: dict[str, object],
) -> dict[str, object] | None:
    _attach_skill(registry, state, agent_name, skill_name, mode, inputs)
    if not registry.config.enable_skill_runtime or registry.skill_registry is None:
        return None
    return _execute_skill_if_enabled(registry, state, agent_name, skill_name, inputs)


def _skill_constraint_count(skill_result: dict[str, object]) -> int:
    constraints = skill_result.get("constraints", [])
    if isinstance(constraints, list):
        return len(constraints)
    if isinstance(constraints, dict):
        return len(constraints)
    return 0


def _paragraph_blocks_for_skill(source_doc) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    total_chars = 0
    for block in source_doc.blocks:
        text = (block.text or "").strip()
        if not text:
            continue
        if len(blocks) >= MAX_PARAGRAPH_COUNT:
            break
        if blocks and total_chars + len(text) > MAX_PARAGRAPH_CHARS:
            break
        blocks.append(
            {
                "block_id": block.block_id,
                "text": text,
            }
        )
        total_chars += len(text)
    return blocks


def _build_paragraph_skill_inputs(state: AgentState, source_doc) -> dict[str, object]:
    template_fields = []
    if state.template_spec is not None:
        for target_table in state.template_spec.target_tables:
            template_fields.extend(field.field_name for field in target_table.schema)
    return {
        "user_request_doc": state.user_request_doc.to_dict() if state.user_request_doc else {},
        "task_spec": state.task_spec.to_dict() if state.task_spec else {},
        "template_fields": template_fields,
        "source_document": {
            "doc_id": source_doc.doc_id,
            "name": source_doc.file.name,
            "doc_type": source_doc.doc_type,
            "metadata": source_doc.metadata,
            "paragraph_count": len(source_doc.blocks),
        },
        "paragraphs": _paragraph_blocks_for_skill(source_doc),
    }


def _legacy_rule_candidates(state: AgentState, records) -> list:
    target_fields = list(state.task_spec.target_fields) if state.task_spec else []
    entity_level = infer_target_entity_level(target_fields)
    return [
        structured_record_to_candidate(
            record,
            target_fields=target_fields,
            source_strategy="legacy_rule",
            entity_level=entity_level,
            metadata={"builder": "legacy_extractor"},
        )
        for record in records
    ]


class MasterAgent:
    """Central router that validates inputs and announces the execution plan."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, state: AgentState) -> AgentState:
        if state.template_doc is None:
            raise ValueError("No template document found.")
        if state.user_request_doc is None:
            raise ValueError("No user request document found.")
        if not state.source_docs:
            raise ValueError("No source documents found.")

        skill_result = _run_skill(
            self.registry,
            state,
            agent_name="master",
            skill_name="any2table-task-understanding",
            mode="planning",
            inputs={
                "user_request_doc": state.user_request_doc.to_dict(),
                "template_spec": None,
                "source_doc_summaries": _source_doc_summaries(state),
            },
        )

        state.route_plan = ["table_agent", "router_agent", "retrieval_agent", "rag_agent", "coder_agent", "verifier_agent"]
        payload = {
            "document_count": len(state.documents),
            "source_document_count": len(state.source_docs),
            "route_plan": list(state.route_plan),
        }
        if skill_result:
            payload["llm_intent"] = skill_result.get("intent")
            payload["llm_constraint_count"] = _skill_constraint_count(skill_result)
            payload["llm_task_hints"] = skill_result.get("task_hints", [])
        state.add_message(
            "master",
            "routing",
            "Master agent prepared the multi-agent route.",
            payload,
        )
        return state


class TableAgent:
    """Reads the template schema and prepares the task specification."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, state: AgentState) -> AgentState:
        template_spec = self.registry.template_analyzer.analyze(state.template_doc)
        planner = self.registry.get_task_planner("default")
        task_spec = planner.plan(
            user_request_doc=state.user_request_doc,
            template_spec=template_spec,
            source_docs=state.source_docs,
        )

        state.template_spec = template_spec
        state.task_spec = task_spec
        state.selected_writer = (
            state.template_doc.doc_type
            if self.registry.config.writer_backend == "auto"
            else self.registry.config.writer_backend
        )
        state.add_message(
            "table_agent",
            "schema",
            "Table agent analyzed the target template and prepared fill instructions.",
            {
                "target_table_count": len(template_spec.target_tables),
                "target_field_count": len(task_spec.target_fields),
                "constraint_count": len(task_spec.constraints),
                "task_policy": task_spec.task_policy,
                "writer": state.selected_writer,
            },
        )
        return state


def _should_use_rag(state: AgentState) -> tuple[bool, str]:
    """Decide whether this task warrants RAG augmentation.

    RouterAgent runs before RetrievalAgent, so evidence_pack may not be available yet.
    Rules based on task_spec and source_docs (always available at routing time):

    - 3+ source documents: increased ambiguity benefits from RAG reranking.
    - 2+ constraints: selective task benefits from RAG filtering.
    - 5+ target fields: complex schema benefits from RAG field grounding.

    If evidence_pack is available (e.g. re-routing), also check field coverage.

    Returns (use_rag, reason_string).
    """
    task_spec = state.task_spec

    if task_spec is None:
        return False, "missing_task_spec"

    # Rule 1: multiple source docs increase ambiguity
    if len(state.source_docs) >= 3:
        return True, "multiple_source_docs_benefit_from_rag_reranking"

    # Rule 2: many constraints mean the task is selective
    if len(task_spec.constraints) >= 2:
        return True, "multiple_constraints_benefit_from_rag_filtering"

    # Rule 3: many target fields — complex schema benefits from semantic grounding
    if len(task_spec.target_fields) >= 5:
        return True, "complex_schema_benefits_from_rag_field_grounding"

    # Rule 4 (optional): if evidence is already available, check field coverage
    evidence_pack = state.evidence_pack
    if evidence_pack is not None:
        target_field_count = len(task_spec.target_fields)
        if target_field_count > 0:
            covered_fields: set[str] = set()
            for item in evidence_pack.items:
                if isinstance(item.content, dict):
                    covered_fields.update(item.content.keys())
            coverage = len(covered_fields & set(task_spec.target_fields)) / target_field_count
            if coverage < 0.5:
                return True, f"low_field_coverage_{coverage:.0%}_suggests_rag_needed"

    return False, "direct_route_sufficient"


class RouterAgent:
    """Decides whether the current task should stay on the direct path or go through RAG."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, state: AgentState) -> AgentState:
        use_rag, reason = _should_use_rag(state)

        # Only activate RAG if rag_backend is not "default" (no-op).
        # This allows gradual opt-in: set rag_backend="hybrid" in AppConfig to enable.
        if use_rag and self.registry.config.rag_backend != "default":
            route = "rag"
            confidence = 0.8
        else:
            route = "direct"
            confidence = 1.0
            if use_rag:
                reason = f"rag_backend_is_default_noop; underlying_reason={reason}"

        state.selected_route = route
        state.router_decision = {
            "route": route,
            "reason": reason,
            "fallback_route": "direct",
            "confidence": confidence,
            "router_backend": self.registry.config.router_backend,
        }
        state.add_message(
            "router_agent",
            "route_decision",
            "Router agent selected the execution route.",
            dict(state.router_decision),
        )
        return state


class RetrievalAgent:
    """Collects candidate evidence with the configured retrieval backend."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, state: AgentState) -> AgentState:
        backend = self.registry.config.retrieval_backend
        evidence_pack = self.registry.get_retriever(backend).retrieve(
            task_spec=state.task_spec,
            template_spec=state.template_spec,
            source_docs=state.source_docs,
        )
        state.evidence_pack = evidence_pack
        state.retrieval_units = build_retrieval_units(state.source_docs)

        skill_result = _run_skill(
            self.registry,
            state,
            agent_name="retrieval_agent",
            skill_name="any2table-candidate-selection",
            mode="selection",
            inputs={
                "task_spec": state.task_spec.to_dict() if state.task_spec else {},
                "template_spec": state.template_spec.to_dict() if state.template_spec else {},
                "evidence_candidates": {
                    "count": len(evidence_pack.items),
                    "sample_ids": [item.evidence_id for item in evidence_pack.items[:10]],
                },
            },
        )

        llm_selection_applied = False
        llm_selected_count = 0
        if skill_result:
            proposed_selected_ids = skill_result.get("selected_evidence_ids", [])
            llm_selected_count = len(proposed_selected_ids) if isinstance(proposed_selected_ids, list) else 0
            evidence_pack.retrieval_logs.append(
                {
                    "backend": "llm_skill",
                    "skill": "any2table-candidate-selection",
                    "selection_applied": False,
                    "proposed_selected_count": llm_selected_count,
                    "need_more_retrieval": bool(skill_result.get("need_more_retrieval")),
                }
            )
            state.add_log(
                "retrieval_agent",
                "llm_selection_suggested",
                {
                    "selection_applied": False,
                    "proposed_selected_count": llm_selected_count,
                    "reason": "selection_kept_advisory_until_candidate_merger_stage",
                },
            )

        state.add_message(
            "retrieval_agent",
            "retrieval",
            "Retrieval agent collected candidate evidence.",
            {
                "backend": backend,
                "route": state.selected_route,
                "evidence_count": len(evidence_pack.items),
                "coverage": evidence_pack.coverage,
                "llm_selection_applied": llm_selection_applied,
                "llm_selected_id_count": llm_selected_count,
            },
        )
        return state


class RAGAgent:
    """Optional augmentation layer that can later dispatch to table/doc/graph RAG backends."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, state: AgentState) -> AgentState:
        if state.evidence_pack is None or state.task_spec is None or state.template_spec is None:
            raise ValueError("RAGAgent requires task spec, template spec, and evidence pack.")

        route = state.selected_route or "direct"
        rag_backend = self.registry.get_rag_backend(self.registry.config.rag_backend)
        result = rag_backend.run(
            route=route,
            task_spec=state.task_spec,
            template_spec=state.template_spec,
            source_docs=state.source_docs,
            evidence_pack=state.evidence_pack,
        )
        if result.evidence_pack is not None:
            state.evidence_pack = result.evidence_pack
        state.rag_result = result.to_dict()
        state.add_message(
            "rag_agent",
            "rag_route",
            "RAG agent evaluated the selected route.",
            dict(state.rag_result),
        )
        return state


class CoderAgent:
    """Turns evidence into structured records with rule extraction, candidate merging, and code execution."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, state: AgentState) -> AgentState:
        extractor = self.registry.get_extractor(self.registry.config.extractor_backend)
        rule_candidates = build_rule_candidates(state.task_spec, state.template_spec, state.evidence_pack)
        legacy_records = []
        if not rule_candidates:
            legacy_records = extractor.extract(
                task_spec=state.task_spec,
                template_spec=state.template_spec,
                evidence_pack=state.evidence_pack,
            )
            rule_candidates = _legacy_rule_candidates(state, legacy_records)

        agent_candidates = []
        for source_doc in state.source_docs:
            if source_doc.file.ext != "docx" or not source_doc.blocks:
                continue
            skill_inputs = _build_paragraph_skill_inputs(state, source_doc)
            if not skill_inputs["paragraphs"]:
                continue
            skill_result = _run_skill(
                self.registry,
                state,
                agent_name="coder_agent",
                skill_name="any2table-paragraph-structuring",
                mode="paragraph_extraction",
                inputs=skill_inputs,
            )
            if not skill_result:
                continue
            doc_candidates = build_agent_candidates_from_skill_result(
                task_spec=state.task_spec,
                template_spec=state.template_spec,
                source_doc=source_doc,
                skill_result=skill_result,
            )
            agent_candidates.extend(doc_candidates)
            state.add_log(
                "coder_agent",
                "paragraph_structuring_completed",
                {
                    "source_doc_id": source_doc.doc_id,
                    "paragraph_count": len(skill_inputs["paragraphs"]),
                    "candidate_count": len(doc_candidates),
                },
            )

        target_entity_level = infer_target_entity_level(list(state.task_spec.target_fields) if state.task_spec else [])
        merge_result = merge_candidates(
            rule_candidates=rule_candidates,
            agent_candidates=agent_candidates,
            target_entity_level=target_entity_level,
        )
        merged_candidates = merge_result.merged_candidates
        if not merged_candidates and legacy_records:
            merged_candidates = _legacy_rule_candidates(state, legacy_records)

        records = candidates_to_structured_records(merged_candidates)
        records = self.registry.get_compute_engine("python").compute(records=records, task_spec=state.task_spec)

        state.rule_candidates = rule_candidates
        state.agent_candidates = agent_candidates
        state.merged_candidates = merged_candidates
        state.rejected_candidates = merge_result.rejected_candidates
        state.candidate_merge_warnings = merge_result.warnings
        state.records = records

        if merge_result.warnings:
            state.add_log(
                "coder_agent",
                "candidate_merge_warnings",
                {"warnings": merge_result.warnings[:20], "warning_count": len(merge_result.warnings)},
            )

        state.add_message(
            "coder_agent",
            "record_build",
            "Coder agent converted evidence into structured records.",
            {
                "selected_route": state.selected_route,
                "rule_candidate_count": len(rule_candidates),
                "agent_candidate_count": len(agent_candidates),
                "merged_candidate_count": len(merged_candidates),
                "rejected_candidate_count": len(merge_result.rejected_candidates),
                "merge_warning_count": len(merge_result.warnings),
                "record_count": len(records),
            },
        )
        return state


class VerifierAgent:
    """Writes the final output and performs lightweight verification."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, state: AgentState) -> AgentState:
        writer = self.registry.get_writer(state.selected_writer or state.template_doc.doc_type)
        fill_result = writer.write(
            template_doc=state.template_doc,
            template_spec=state.template_spec,
            records=state.records,
        )
        verification_report = self.registry.get_verifier(self.registry.config.verifier_backend).verify(
            task_spec=state.task_spec,
            template_spec=state.template_spec,
            evidence_pack=state.evidence_pack,
            records=state.records,
            fill_result=fill_result,
        )
        state.fill_result = fill_result
        state.verification_report = verification_report

        skill_result = _run_skill(
            self.registry,
            state,
            agent_name="verifier_agent",
            skill_name="any2table-verification",
            mode="verification",
            inputs={
                "task_spec": state.task_spec.to_dict() if state.task_spec else {},
                "template_spec": state.template_spec.to_dict() if state.template_spec else {},
                "selected_records": {
                    "count": len(state.records),
                    "sample_record_ids": [record.record_id for record in state.records[:10]],
                },
                "fill_result": {
                    "output_path": fill_result.output_path,
                    "written_cell_count": len(fill_result.written_cells),
                },
            },
        )

        if skill_result:
            raw_status = str(skill_result.get("status", "warning")).lower()
            normalized_status = raw_status if raw_status in {"pass", "warning", "fail"} else "warning"
            issues = skill_result.get("issues", [])
            issue_count = len(issues) if isinstance(issues, list) else 0
            summary = str(skill_result.get("reasoning_summary", "")).strip()
            message = summary or f"LLM verification reported {issue_count} issue(s)."
            verification_report.checks.append(
                VerificationCheck(
                    name="llm_skill_review",
                    status=normalized_status,
                    message=message,
                )
            )
            if normalized_status in {"warning", "fail"} and verification_report.status == "pass":
                verification_report.status = normalized_status
            if summary:
                verification_report.summary = f"{verification_report.summary} LLM review: {summary}"

        state.add_message(
            "verifier_agent",
            "verification",
            "Verifier agent completed output generation and validation.",
            {
                "output_path": fill_result.output_path,
                "verification_status": verification_report.status,
                "llm_review_applied": bool(skill_result),
            },
        )
        return state
