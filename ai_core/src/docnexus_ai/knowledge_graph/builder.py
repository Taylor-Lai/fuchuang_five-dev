"""Build lightweight KG sketches from extraction outputs."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from .models import GraphEntity, GraphRelation, KnowledgeGraph

META_KEY = "_meta"
ENTITY_TYPE_HINTS = {
    "人": ("负责人", "姓名", "联系人", "教师", "作者"),
    "组织": ("单位", "学校", "公司", "机构", "部门", "团队"),
    "地点": ("地址", "地点", "城市", "省份", "国家"),
    "时间": ("日期", "时间", "年份", "月份"),
    "数值": ("金额", "预算", "数量", "人口", "gdp", "收入", "病例", "检测", "比例", "率"),
}


def _stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _infer_entity_type(field_name: str, value: object) -> str:
    normalized_name = field_name.lower()
    for entity_type, tokens in ENTITY_TYPE_HINTS.items():
        if any(token.lower() in normalized_name for token in tokens):
            return entity_type
    text = str(value)
    if re.search(r"\d{4}[-/年]\d{1,2}", text):
        return "时间"
    if re.search(r"\d", text):
        return "数值"
    return "概念"


def _field_evidence(extraction_result: dict[str, object], field_name: str) -> tuple[str | None, list[str]]:
    meta = extraction_result.get(META_KEY)
    if not isinstance(meta, dict):
        return None, []
    evidence = meta.get("evidence")
    if not isinstance(evidence, dict):
        return None, []
    item = evidence.get(field_name)
    if not isinstance(item, dict):
        return None, []
    snippet = item.get("snippet")
    chunk_id = item.get("chunk_id")
    source_ids = [f"chunk:{chunk_id}"] if chunk_id is not None else []
    return str(snippet) if snippet else None, source_ids


def _iter_extraction_fields(extraction_result: dict[str, object]) -> Iterable[tuple[str, object]]:
    for field_name, value in extraction_result.items():
        if field_name == META_KEY:
            continue
        if value is None or value == "" or value == "未找到":
            continue
        yield field_name, value


class KnowledgeGraphBuilder:
    """Construct an experimental sidecar KG without affecting the main flow."""

    def from_extraction_result(self, extraction_result: dict[str, object], *, graph_id: str = "kg_extraction_sidecar") -> KnowledgeGraph:
        entities: list[GraphEntity] = []
        relations: list[GraphRelation] = []
        document_entity = GraphEntity(
            entity_id=_stable_id("entity", graph_id, "document"),
            name="当前文档",
            entity_type="文档",
            attributes={"role": "source_document"},
        )
        entities.append(document_entity)

        for field_name, value in _iter_extraction_fields(extraction_result):
            text = _normalize_text(value)
            evidence, source_ids = _field_evidence(extraction_result, field_name)
            entity = GraphEntity(
                entity_id=_stable_id("entity", field_name, text),
                name=text,
                entity_type=_infer_entity_type(field_name, value),
                attributes={"field_name": field_name, "raw_value": value},
                source_ids=source_ids,
            )
            entities.append(entity)
            relations.append(
                GraphRelation(
                    relation_id=_stable_id("relation", document_entity.entity_id, field_name, entity.entity_id),
                    source_entity_id=document_entity.entity_id,
                    target_entity_id=entity.entity_id,
                    relation_type=f"has_field:{field_name}",
                    confidence=0.7,
                    evidence=evidence,
                    source_ids=source_ids,
                )
            )

        return KnowledgeGraph(
            graph_id=graph_id,
            entities=entities,
            relations=relations,
            metadata={
                "status": "experimental_sidecar",
                "connected_to_main_pipeline": False,
                "entity_count": len(entities),
                "relation_count": len(relations),
            },
        )

    def from_text_units(self, text_units: list[dict[str, object]], *, graph_id: str = "kg_text_sidecar") -> KnowledgeGraph:
        entities: list[GraphEntity] = []
        relations: list[GraphRelation] = []
        for index, unit in enumerate(text_units):
            text = _normalize_text(unit.get("text", ""))
            if not text:
                continue
            entity = GraphEntity(
                entity_id=_stable_id("entity", graph_id, index, text[:80]),
                name=text[:80],
                entity_type="文本片段",
                attributes={"text": text, "index": index},
                source_ids=[str(unit.get("id") or unit.get("chunk_id") or index)],
            )
            entities.append(entity)
            if index > 0 and len(entities) >= 2:
                previous = entities[-2]
                relations.append(
                    GraphRelation(
                        relation_id=_stable_id("relation", previous.entity_id, entity.entity_id, "next"),
                        source_entity_id=previous.entity_id,
                        target_entity_id=entity.entity_id,
                        relation_type="next_text_unit",
                        confidence=1.0,
                    )
                )

        return KnowledgeGraph(
            graph_id=graph_id,
            entities=entities,
            relations=relations,
            metadata={
                "status": "experimental_sidecar",
                "connected_to_main_pipeline": False,
                "entity_count": len(entities),
                "relation_count": len(relations),
            },
        )
