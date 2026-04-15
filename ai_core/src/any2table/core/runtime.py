"""Runtime state and graph orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from any2table.candidates import CandidateRecord
from any2table.core.models import (
    CanonicalDocument,
    EvidencePack,
    FileAsset,
    FillResult,
    StructuredRecord,
    TaskSpec,
    TemplateSpec,
    VerificationReport,
)

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - optional dependency path
    END = None
    StateGraph = None


class GraphStatePayload(TypedDict):
    state: "AgentState"


@dataclass(slots=True)
class AgentState:
    """Shared state for graph-based orchestration."""

    files: list[FileAsset] = field(default_factory=list)
    documents: list[CanonicalDocument] = field(default_factory=list)
    template_doc: CanonicalDocument | None = None
    user_request_doc: CanonicalDocument | None = None
    source_docs: list[CanonicalDocument] = field(default_factory=list)
    task_spec: TaskSpec | None = None
    template_spec: TemplateSpec | None = None
    evidence_pack: EvidencePack | None = None
    selected_route: str = "direct"
    router_decision: dict[str, object] = field(default_factory=dict)
    rag_result: dict[str, object] = field(default_factory=dict)
    rule_candidates: list[CandidateRecord] = field(default_factory=list)
    agent_candidates: list[CandidateRecord] = field(default_factory=list)
    merged_candidates: list[CandidateRecord] = field(default_factory=list)
    rejected_candidates: list[CandidateRecord] = field(default_factory=list)
    candidate_merge_warnings: list[str] = field(default_factory=list)
    records: list[StructuredRecord] = field(default_factory=list)
    fill_result: FillResult | None = None
    verification_report: VerificationReport | None = None
    selected_writer: str | None = None
    route_plan: list[str] = field(default_factory=list)
    messages: list[dict[str, object]] = field(default_factory=list)
    logs: list[dict[str, object]] = field(default_factory=list)
    skill_runs: list[dict[str, object]] = field(default_factory=list)
    skill_results: list[dict[str, object]] = field(default_factory=list)
    llm_runs: list[dict[str, object]] = field(default_factory=list)
    retrieval_units: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    retry_count: int = 0
    runtime_backend: str | None = None

    def add_message(self, agent: str, kind: str, content: str, payload: dict[str, object] | None = None) -> None:
        message = {"agent": agent, "kind": kind, "content": content}
        if payload:
            message["payload"] = payload
        self.messages.append(message)

    def add_log(self, agent: str, event: str, payload: dict[str, object] | None = None) -> None:
        log = {"agent": agent, "event": event}
        if payload:
            log["payload"] = payload
        self.logs.append(log)

    def add_skill_run(
        self,
        agent: str,
        skill: str,
        mode: str,
        input_keys: list[str],
        prompt_preview: str,
    ) -> None:
        self.skill_runs.append(
            {
                "agent": agent,
                "skill": skill,
                "mode": mode,
                "input_keys": input_keys,
                "prompt_preview": prompt_preview,
            }
        )

    def add_skill_result(
        self,
        agent: str,
        skill: str,
        result: dict[str, object],
        model: str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "agent": agent,
            "skill": skill,
            "result": result,
        }
        if model:
            payload["model"] = model
        self.skill_results.append(payload)

    def add_llm_run(
        self,
        agent: str,
        skill: str,
        status: str,
        model: str | None = None,
        response_preview: str | None = None,
        error: str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "agent": agent,
            "skill": skill,
            "status": status,
        }
        if model:
            payload["model"] = model
        if response_preview:
            payload["response_preview"] = response_preview
        if error:
            payload["error"] = error
        self.llm_runs.append(payload)

    def clear_intermediate(self, *, max_log_entries: int = 200) -> None:
        """Release intermediate candidate lists and trim log lists to bound memory usage.

        Call this after the fill result has been written and the pipeline is complete.
        The final outputs (fill_result, verification_report, records) are retained.
        """
        self.rule_candidates = []
        self.agent_candidates = []
        self.merged_candidates = []
        self.rejected_candidates = []
        self.candidate_merge_warnings = []
        self.retrieval_units = {}
        if len(self.logs) > max_log_entries:
            self.logs = self.logs[-max_log_entries:]
        if len(self.messages) > max_log_entries:
            self.messages = self.messages[-max_log_entries:]
        if len(self.skill_runs) > max_log_entries:
            self.skill_runs = self.skill_runs[-max_log_entries:]
        if len(self.llm_runs) > max_log_entries:
            self.llm_runs = self.llm_runs[-max_log_entries:]


class GraphRuntime:
    """Small sequential graph runtime for the initial multi-agent workflow."""

    backend_name = "graph"

    def __init__(self, nodes: list[tuple[str, object]]) -> None:
        self.nodes = nodes

    def run(self, state: AgentState) -> AgentState:
        state.runtime_backend = self.backend_name
        for node_name, node in self.nodes:
            state.add_log(node_name, "start")
            state = node.run(state)
            state.add_log(node_name, "finish")
        return state


class LangGraphRuntime:
    """LangGraph-backed runtime with automatic fallback to the local graph runtime."""

    backend_name = "langgraph"

    def __init__(self, nodes: list[tuple[str, object]]) -> None:
        self.nodes = nodes

    def _build_graph(self):
        if StateGraph is None or END is None:
            return None
        graph = StateGraph(GraphStatePayload)
        for node_name, node in self.nodes:
            graph.add_node(node_name, self._wrap_node(node_name, node))
        graph.set_entry_point(self.nodes[0][0])
        for index, (node_name, _) in enumerate(self.nodes):
            next_name = END if index == len(self.nodes) - 1 else self.nodes[index + 1][0]
            graph.add_edge(node_name, next_name)
        return graph.compile()

    def _wrap_node(self, node_name: str, node: object):
        def runner(payload: GraphStatePayload) -> GraphStatePayload:
            state = payload["state"]
            state.add_log(node_name, "start")
            state = node.run(state)
            state.add_log(node_name, "finish")
            return {"state": state}

        return runner

    def run(self, state: AgentState) -> AgentState:
        graph = self._build_graph()
        if graph is None:
            state.add_log(
                "runtime",
                "langgraph_unavailable",
                {"fallback_backend": GraphRuntime.backend_name},
            )
            return GraphRuntime(self.nodes).run(state)

        result = graph.invoke({"state": state})
        final_state = result["state"]
        final_state.runtime_backend = self.backend_name
        return final_state
