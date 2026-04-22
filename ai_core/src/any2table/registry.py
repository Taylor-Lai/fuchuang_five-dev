"""Runtime component registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from any2table.config import AppConfig
from any2table.core.models import CanonicalDocument, FileAsset
from any2table.core.protocols import (
    ComputeEngine,
    Extractor,
    Parser,
    Retriever,
    TaskPlanner,
    TemplateAnalyzer,
    Verifier,
    Writer,
)
from any2table.skills.registry import SkillRegistry


@dataclass
class ComponentRegistry:
    parsers: list[Parser] = field(default_factory=list)
    template_analyzer: TemplateAnalyzer | None = None
    task_planners: dict[str, TaskPlanner] = field(default_factory=dict)
    retrievers: dict[str, Retriever] = field(default_factory=dict)
    rag_backends: dict[str, object] = field(default_factory=dict)
    extractors: dict[str, Extractor] = field(default_factory=dict)
    compute_engines: dict[str, ComputeEngine] = field(default_factory=dict)
    writers: dict[str, Writer] = field(default_factory=dict)
    verifiers: dict[str, Verifier] = field(default_factory=dict)
    config: AppConfig = field(default_factory=AppConfig)
    skill_registry: SkillRegistry | None = None
    llm_client: object | None = None

    def register_parser(self, parser: Parser) -> None:
        self.parsers.append(parser)

    def register_template_analyzer(self, analyzer: TemplateAnalyzer) -> None:
        self.template_analyzer = analyzer

    def register_task_planner(self, name: str, planner: TaskPlanner) -> None:
        self.task_planners[name] = planner

    def register_retriever(self, name: str, retriever: Retriever) -> None:
        self.retrievers[name] = retriever

    def register_rag_backend(self, name: str, rag_backend: object) -> None:
        self.rag_backends[name] = rag_backend

    def register_extractor(self, name: str, extractor: Extractor) -> None:
        self.extractors[name] = extractor

    def register_compute_engine(self, name: str, compute_engine: ComputeEngine) -> None:
        self.compute_engines[name] = compute_engine

    def register_writer(self, name: str, writer: Writer) -> None:
        self.writers[name] = writer

    def register_verifier(self, name: str, verifier: Verifier) -> None:
        self.verifiers[name] = verifier

    def parse(self, file: FileAsset) -> CanonicalDocument:
        for parser in self.parsers:
            if parser.supports(file):
                return parser.parse(file)
        raise ValueError(f"No parser registered for file: {file.path}")

    def get_task_planner(self, name: str) -> TaskPlanner:
        return self.task_planners[name]

    def get_retriever(self, name: str) -> Retriever:
        return self.retrievers[name]

    def get_rag_backend(self, name: str) -> object:
        return self.rag_backends[name]

    def get_extractor(self, name: str) -> Extractor:
        return self.extractors[name]

    def get_compute_engine(self, name: str) -> ComputeEngine:
        return self.compute_engines[name]

    def get_writer(self, name: str) -> Writer:
        return self.writers[name]

    def get_verifier(self, name: str) -> Verifier:
        return self.verifiers[name]
