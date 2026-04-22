"""RAG backend abstraction for optional retrieval augmentation."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from any2table.core.models import CanonicalDocument, EvidenceItem, EvidencePack, TaskSpec, TemplateSpec

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "data",
    "table",
    "sheet",
    "value",
    "values",
    "field",
    "fields",
}


@dataclass(slots=True)
class RagResult:
    route: str = "direct"
    used_backend: str = "default"
    applied: bool = False
    evidence_pack: EvidencePack | None = None
    selected_unit_ids: list[str] = field(default_factory=list)
    supporting_units: list[str] = field(default_factory=list)
    field_evidence_map: dict[str, list[str]] = field(default_factory=dict)
    query_summary: dict[str, object] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "route": self.route,
            "used_backend": self.used_backend,
            "applied": self.applied,
            "selected_unit_ids": list(self.selected_unit_ids),
            "supporting_units": list(self.supporting_units),
            "field_evidence_map": {key: list(value) for key, value in self.field_evidence_map.items()},
            "query_summary": dict(self.query_summary),
            "notes": list(self.notes),
            "evidence_count": len(self.evidence_pack.items) if self.evidence_pack is not None else 0,
        }


class BaseRagBackend:
    """Abstract interface for future table/doc/graph RAG backends."""

    name = "base"

    def run(
        self,
        *,
        route: str,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        source_docs: list[CanonicalDocument],
        evidence_pack: EvidencePack,
    ) -> RagResult:
        raise NotImplementedError


class DefaultRagBackend(BaseRagBackend):
    """No-op RAG backend used in the first stage so the default route stays direct."""

    name = "default"

    def run(
        self,
        *,
        route: str,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        source_docs: list[CanonicalDocument],
        evidence_pack: EvidencePack,
    ) -> RagResult:
        if route == "direct":
            notes = ["Router selected direct path; skipped RAG execution."]
        else:
            notes = [
                f"Route {route} requested, but backend {self.name} is a placeholder and currently leaves evidence unchanged."
            ]
        return RagResult(
            route=route,
            used_backend=self.name,
            applied=False,
            evidence_pack=evidence_pack,
            notes=notes,
        )


@dataclass(slots=True)
class _RankedEvidence:
    item: EvidenceItem
    total_score: float
    lexical_score: float
    field_coverage_score: float
    metadata_score: float
    matched_fields: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)


class HybridRagBackend(BaseRagBackend):
    """Schema-grounded hybrid RAG that ranks evidence using lexical and metadata signals."""

    name = "hybrid"

    def run(
        self,
        *,
        route: str,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        source_docs: list[CanonicalDocument],
        evidence_pack: EvidencePack,
    ) -> RagResult:
        query_summary = self._build_query_summary(task_spec, template_spec)
        if route == "direct":
            return RagResult(
                route=route,
                used_backend=self.name,
                applied=False,
                evidence_pack=evidence_pack,
                query_summary=query_summary,
                notes=["Router selected direct path; hybrid RAG prepared query context but did not rerank evidence."],
            )

        ranked_items = [self._rank_item(item, query_summary, task_spec) for item in evidence_pack.items]
        ranked_items.sort(
            key=lambda ranked: (
                ranked.total_score,
                ranked.field_coverage_score,
                ranked.lexical_score,
                ranked.metadata_score,
            ),
            reverse=True,
        )

        selected_count = self._select_count(len(ranked_items), query_summary["field_count"])
        selected_items = ranked_items[:selected_count]
        supporting_items = ranked_items[selected_count : selected_count + min(10, max(0, len(ranked_items) - selected_count))]

        reranked_pack = EvidencePack(
            task_id=evidence_pack.task_id,
            items=[self._clone_item(entry) for entry in ranked_items],
            retrieval_logs=[*evidence_pack.retrieval_logs],
            coverage={**evidence_pack.coverage},
        )
        reranked_pack.retrieval_logs.append(
            {
                "backend": self.name,
                "route": route,
                "query_terms": query_summary["query_terms"],
                "target_fields": query_summary["target_fields"],
                "selected_count": len(selected_items),
                "supporting_count": len(supporting_items),
                "reranked_only": True,
            }
        )
        reranked_pack.coverage.update(
            {
                "rag_backend": self.name,
                "rag_selected_count": len(selected_items),
                "rag_supporting_count": len(supporting_items),
            }
        )

        field_evidence_map: dict[str, list[str]] = {field_name: [] for field_name in query_summary["target_fields"]}
        for entry in selected_items:
            matched_fields = entry.matched_fields or query_summary["target_fields"][:1]
            for field_name in matched_fields:
                field_evidence_map.setdefault(field_name, [])
                if entry.item.evidence_id not in field_evidence_map[field_name]:
                    field_evidence_map[field_name].append(entry.item.evidence_id)

        notes = [
            "Hybrid RAG reranked evidence using schema-aware lexical and metadata signals.",
            "Current backend keeps the full evidence pack and exposes selected ids for future narrowing.",
        ]
        return RagResult(
            route=route,
            used_backend=self.name,
            applied=True,
            evidence_pack=reranked_pack,
            selected_unit_ids=[entry.item.evidence_id for entry in selected_items],
            supporting_units=[entry.item.evidence_id for entry in supporting_items],
            field_evidence_map=field_evidence_map,
            query_summary=query_summary,
            notes=notes,
        )

    def _build_query_summary(self, task_spec: TaskSpec, template_spec: TemplateSpec) -> dict[str, object]:
        target_fields: list[str] = []
        query_terms: list[str] = []
        entity_terms: list[str] = []
        date_terms: list[str] = []

        for table in template_spec.target_tables:
            if table.logical_name:
                query_terms.extend(self._tokenize(table.logical_name))
            if table.description:
                query_terms.extend(self._tokenize(table.description))
            for field_spec in table.schema:
                target_fields.append(field_spec.field_name)
                query_terms.extend(self._tokenize(field_spec.field_name))
                if field_spec.normalized_name:
                    query_terms.extend(self._tokenize(field_spec.normalized_name))

        query_terms.extend(self._tokenize(" ".join(task_spec.target_fields)))
        for constraint in task_spec.constraints:
            if constraint.field:
                query_terms.extend(self._tokenize(constraint.field))
            if isinstance(constraint.value, dict):
                query_terms.extend(self._tokenize(" ".join(str(value) for value in constraint.value.values())))
            else:
                query_terms.extend(self._tokenize(str(constraint.value)))
            if constraint.kind == "entity":
                entity_terms.extend(self._tokenize(str(constraint.value)))
            if constraint.kind in {"date_range", "exact_datetime"}:
                date_terms.extend(self._tokenize(str(constraint.value)))
            if constraint.kind == "request_text":
                query_terms.extend(self._tokenize(str(constraint.value)))

        target_fields = self._dedupe_preserve_order(target_fields)
        query_terms = self._dedupe_preserve_order(query_terms)
        entity_terms = self._dedupe_preserve_order(entity_terms)
        date_terms = self._dedupe_preserve_order(date_terms)
        return {
            "query_terms": query_terms,
            "target_fields": target_fields,
            "entity_terms": entity_terms,
            "date_terms": date_terms,
            "field_count": len(target_fields),
        }

    def _rank_item(self, item: EvidenceItem, query_summary: dict[str, object], task_spec: TaskSpec) -> _RankedEvidence:
        content_text = self._item_text(item)
        item_terms = set(self._tokenize(content_text))
        query_terms = query_summary["query_terms"]
        target_fields = query_summary["target_fields"]
        entity_terms = query_summary["entity_terms"]
        date_terms = query_summary["date_terms"]

        matched_terms = [term for term in query_terms if term in item_terms or term in content_text]
        lexical_score = len(matched_terms) / max(len(query_terms), 1)

        matched_fields = self._match_fields(item, target_fields, content_text)
        field_coverage_score = len(matched_fields) / max(len(target_fields), 1)

        metadata_score = self._metadata_score(item, content_text, entity_terms, date_terms, task_spec)
        total_score = round((lexical_score * 0.45) + (field_coverage_score * 0.4) + (metadata_score * 0.15), 4)
        return _RankedEvidence(
            item=item,
            total_score=total_score,
            lexical_score=lexical_score,
            field_coverage_score=field_coverage_score,
            metadata_score=metadata_score,
            matched_fields=matched_fields,
            matched_terms=matched_terms[:12],
        )

    def _metadata_score(
        self,
        item: EvidenceItem,
        content_text: str,
        entity_terms: list[str],
        date_terms: list[str],
        task_spec: TaskSpec,
    ) -> float:
        score = 0.0
        type_weight = {
            "row": 0.35,
            "paragraph": 0.25,
            "table": 0.15,
        }
        score += type_weight.get(item.evidence_type, 0.1)

        if entity_terms and any(term in content_text for term in entity_terms):
            score += 0.35
        if date_terms and any(term in content_text for term in date_terms):
            score += 0.2
        if task_spec.allow_inference and item.evidence_type == "paragraph":
            score += 0.1
        return min(score, 1.0)

    def _match_fields(self, item: EvidenceItem, target_fields: list[str], content_text: str) -> list[str]:
        matched: list[str] = []
        content_dict = item.content if isinstance(item.content, dict) else {}
        normalized_keys = {self._normalize_text(str(key)): key for key in content_dict.keys()}
        normalized_content = self._normalize_text(content_text)
        for field_name in target_fields:
            normalized_field = self._normalize_text(field_name)
            if normalized_field in normalized_keys:
                matched.append(field_name)
                continue
            if field_name in content_text or normalized_field in normalized_content:
                matched.append(field_name)
        return self._dedupe_preserve_order(matched)

    def _item_text(self, item: EvidenceItem) -> str:
        if isinstance(item.content, dict):
            fragments = [f"{key}: {value}" for key, value in item.content.items()]
            return " | ".join(fragments).lower()
        return str(item.content).lower()

    def _clone_item(self, entry: _RankedEvidence) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=entry.item.evidence_id,
            evidence_type=entry.item.evidence_type,
            source_doc_id=entry.item.source_doc_id,
            content=entry.item.content,
            matched_fields=self._dedupe_preserve_order([*entry.item.matched_fields, *entry.matched_fields]),
            score=entry.total_score,
            location=entry.item.location,
        )

    def _select_count(self, evidence_count: int, field_count: int) -> int:
        if evidence_count <= 0:
            return 0
        base = max(field_count * 3, 8)
        return min(evidence_count, base, 24)

    def _tokenize(self, text: str) -> list[str]:
        pieces = re.findall(r"[a-z0-9_./:-]+|[\u4e00-\u9fff]{1,}", text.lower())
        tokens: list[str] = []
        for piece in pieces:
            token = piece.strip()
            if not token:
                continue
            if token in STOPWORDS:
                continue
            if len(token) == 1 and not token.isdigit():
                continue
            tokens.append(token)
        return tokens

    def _normalize_text(self, text: str) -> str:
        return "".join(text.lower().split())

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value and value not in deduped:
                deduped.append(value)
        return deduped
