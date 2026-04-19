"""Sequential and multi-agent orchestrators."""

from __future__ import annotations

from any2table.candidates.builders import (
    build_rule_candidates,
    candidates_to_structured_records,
    infer_target_entity_level,
    structured_record_to_candidate,
)
from any2table.core.models import FileAsset, FillRunResult
from any2table.core.runtime import AgentState, GraphRuntime, LangGraphRuntime
from any2table.storage import dump_intermediate_artifacts


class SequentialOrchestrator:
    """Default deterministic orchestrator for the first project iteration."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def run(self, files: list[FileAsset]) -> FillRunResult:
        documents = [self.registry.parse(file) for file in files]

        template_doc = next((doc for doc in documents if doc.file.role == "template"), None)
        if template_doc is None:
            raise ValueError("No template document found.")

        user_request_doc = next((doc for doc in documents if doc.file.role == "user_request"), None)
        if user_request_doc is None:
            raise ValueError("No user request document found.")

        source_docs = [doc for doc in documents if doc.file.role == "source"]

        template_spec = self.registry.template_analyzer.analyze(template_doc)
        task_spec = self.registry.get_task_planner("default").plan(
            user_request_doc=user_request_doc,
            template_spec=template_spec,
            source_docs=source_docs,
        )
        evidence_pack = self.registry.get_retriever(self.registry.config.retrieval_backend).retrieve(
            task_spec=task_spec,
            template_spec=template_spec,
            source_docs=source_docs,
        )

        extractor = self.registry.get_extractor(self.registry.config.extractor_backend)
        rule_candidates = build_rule_candidates(task_spec, template_spec, evidence_pack)
        if rule_candidates:
            merged_candidates = list(rule_candidates)
        else:
            legacy_records = extractor.extract(
                task_spec=task_spec,
                template_spec=template_spec,
                evidence_pack=evidence_pack,
            )
            target_fields = list(task_spec.target_fields)
            entity_level = infer_target_entity_level(target_fields)
            merged_candidates = [
                structured_record_to_candidate(
                    record,
                    target_fields=target_fields,
                    source_strategy="legacy_rule",
                    entity_level=entity_level,
                    metadata={"builder": "legacy_extractor"},
                )
                for record in legacy_records
            ]

        records = candidates_to_structured_records(merged_candidates)
        records = self.registry.get_compute_engine("python").compute(records=records, task_spec=task_spec)

        writer_key = template_doc.doc_type if self.registry.config.writer_backend == "auto" else self.registry.config.writer_backend
        fill_result = self.registry.get_writer(writer_key).write(
            template_doc=template_doc,
            template_spec=template_spec,
            records=records,
        )
        verification_report = self.registry.get_verifier(self.registry.config.verifier_backend).verify(
            task_spec=task_spec,
            template_spec=template_spec,
            evidence_pack=evidence_pack,
            records=records,
            fill_result=fill_result,
        )

        debug = {
            "runtime": "sequential",
            "document_count": len(documents),
            "source_document_count": len(source_docs),
            "record_count": len(records),
            "evidence_count": len(evidence_pack.items),
            "rule_candidate_count": len(rule_candidates),
            "merged_candidate_count": len(merged_candidates),
        }
        if self.registry.config.enable_intermediate_dump:
            debug["intermediate"] = dump_intermediate_artifacts(
                root_dir=self.registry.config.intermediate_root,
                documents=documents,
                template_spec=template_spec,
                task_spec=task_spec,
                source_docs=source_docs,
                rule_candidates=rule_candidates,
                merged_candidates=merged_candidates,
            )

        return FillRunResult(
            fill_result=fill_result,
            verification_report=verification_report,
            debug=debug,
        )


class MultiAgentOrchestrator:
    """Multi-agent orchestrator that can run on a local graph or LangGraph backend."""

    def __init__(self, registry, runtime: GraphRuntime | LangGraphRuntime) -> None:
        self.registry = registry
        self.runtime = runtime

    def _build_state(self, files: list[FileAsset]) -> AgentState:
        documents = [self.registry.parse(file) for file in files]
        template_doc = next((doc for doc in documents if doc.file.role == "template"), None)
        user_request_doc = next((doc for doc in documents if doc.file.role == "user_request"), None)
        source_docs = [doc for doc in documents if doc.file.role == "source"]
        return AgentState(
            files=files,
            documents=documents,
            template_doc=template_doc,
            user_request_doc=user_request_doc,
            source_docs=source_docs,
        )

    def run(self, files: list[FileAsset]) -> FillRunResult:
        state = self._build_state(files)
        state = self.runtime.run(state)
        if state.fill_result is None or state.verification_report is None or state.evidence_pack is None:
            raise ValueError("Multi-agent runtime did not produce a complete fill result.")

        debug = {
            "runtime": state.runtime_backend or getattr(self.runtime, "backend_name", "unknown"),
            "document_count": len(state.documents),
            "source_document_count": len(state.source_docs),
            "record_count": len(state.records),
            "evidence_count": len(state.evidence_pack.items),
            "route_plan": list(state.route_plan),
            "selected_route": state.selected_route,
            "router_decision": state.router_decision,
            "rag_result": state.rag_result,
            "agent_messages": state.messages,
            "agent_logs": state.logs,
            "skill_runs": state.skill_runs,
            "skill_results": state.skill_results,
            "llm_runs": state.llm_runs,
            "llm_skill_execution_enabled": self.registry.config.enable_llm_skill_execution,
            "rule_candidate_count": len(state.rule_candidates),
            "agent_candidate_count": len(state.agent_candidates),
            "merged_candidate_count": len(state.merged_candidates),
            "rejected_candidate_count": len(state.rejected_candidates),
            "candidate_merge_warning_count": len(state.candidate_merge_warnings),
        }
        if self.registry.config.enable_intermediate_dump and state.template_spec is not None and state.task_spec is not None:
            debug["intermediate"] = dump_intermediate_artifacts(
                root_dir=self.registry.config.intermediate_root,
                documents=state.documents,
                template_spec=state.template_spec,
                task_spec=state.task_spec,
                source_docs=state.source_docs,
                rule_candidates=state.rule_candidates,
                agent_candidates=state.agent_candidates,
                merged_candidates=state.merged_candidates,
                rejected_candidates=state.rejected_candidates,
                candidate_merge_warnings=state.candidate_merge_warnings,
            )

        return FillRunResult(
            fill_result=state.fill_result,
            verification_report=state.verification_report,
            debug=debug,
        )
