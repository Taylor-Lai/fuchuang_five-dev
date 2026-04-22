"""Core component protocols."""

from __future__ import annotations

from typing import Protocol

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


class Parser(Protocol):
    def supports(self, file: FileAsset) -> bool: ...

    def parse(self, file: FileAsset) -> CanonicalDocument: ...


class TemplateAnalyzer(Protocol):
    def analyze(self, template_doc: CanonicalDocument) -> TemplateSpec: ...


class TaskPlanner(Protocol):
    def plan(
        self,
        user_request_doc: CanonicalDocument,
        template_spec: TemplateSpec,
        source_docs: list[CanonicalDocument],
    ) -> TaskSpec: ...


class Retriever(Protocol):
    def retrieve(
        self,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        source_docs: list[CanonicalDocument],
    ) -> EvidencePack: ...


class Extractor(Protocol):
    def extract(
        self,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        evidence_pack: EvidencePack,
    ) -> list[StructuredRecord]: ...


class ComputeEngine(Protocol):
    def compute(self, records: list[StructuredRecord], task_spec: TaskSpec) -> list[StructuredRecord]: ...


class Writer(Protocol):
    supported_doc_types: tuple[str, ...]

    def write(
        self,
        template_doc: CanonicalDocument,
        template_spec: TemplateSpec,
        records: list[StructuredRecord],
    ) -> FillResult: ...


class Verifier(Protocol):
    def verify(
        self,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        evidence_pack: EvidencePack,
        records: list[StructuredRecord],
        fill_result: FillResult,
    ) -> VerificationReport: ...


class AgentNode(Protocol):
    def run(self, state: dict[str, object]) -> dict[str, object]: ...
