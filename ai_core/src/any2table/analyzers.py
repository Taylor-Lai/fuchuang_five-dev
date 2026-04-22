"""Template analyzers."""

from __future__ import annotations

import re

from any2table.core.models import CanonicalDocument, Constraint, FieldSpec, TargetTableSpec, TemplateSpec

ISO_DATETIME_PATTERN = re.compile(r"(\d{4}-\d{1,2}-\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)")
CN_DATETIME_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日(\d{2}:\d{2})")
CITY_WITH_CONTEXT_PATTERN = re.compile(r"([\u4e00-\u9fff]{2,10}?市)(?:各|环境|空气|区域|监测)")
CITY_PATTERN = re.compile(r"([\u4e00-\u9fff]{2,10}?市)")
CITY_PREFIXES = ("时刻", "记录", "关于", "本表")


def _extract_exact_datetime(description: str) -> str | None:
    iso_match = ISO_DATETIME_PATTERN.search(description)
    if iso_match:
        return iso_match.group(1)

    cn_match = CN_DATETIME_PATTERN.search(description)
    if not cn_match:
        return None

    year, month, day, hm = cn_match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d} {hm}:00.0"


def _clean_city_candidate(city: str) -> str:
    cleaned = city
    changed = True
    while changed:
        changed = False
        for prefix in CITY_PREFIXES:
            if cleaned.startswith(prefix) and len(cleaned) > len(prefix):
                cleaned = cleaned[len(prefix):]
                changed = True
    return cleaned


def _extract_city(description: str) -> str | None:
    contextual_match = CITY_WITH_CONTEXT_PATTERN.search(description)
    if contextual_match:
        return _clean_city_candidate(contextual_match.group(1))

    city_match = CITY_PATTERN.search(description)
    if city_match:
        return _clean_city_candidate(city_match.group(1))
    return None


def _extract_local_constraints(table_id: str, description: str | None) -> list[Constraint]:
    if not description:
        return []

    constraints: list[Constraint] = []
    city = _extract_city(description)
    if city:
        constraints.append(
            Constraint(
                constraint_id=f"{table_id}#city",
                source="template_description",
                kind="entity",
                field="城市",
                operator="equals",
                value=city,
            )
        )

    exact_datetime = _extract_exact_datetime(description)
    if exact_datetime:
        constraints.append(
            Constraint(
                constraint_id=f"{table_id}#datetime",
                source="template_description",
                kind="exact_datetime",
                field="监测时间",
                operator="equals",
                value=exact_datetime,
            )
        )

    return constraints


class DefaultTemplateAnalyzer:
    """Infer target tables directly from parsed template tables."""

    def analyze(self, template_doc: CanonicalDocument) -> TemplateSpec:
        target_tables: list[TargetTableSpec] = []
        for index, table in enumerate(template_doc.tables):
            schema = [
                FieldSpec(
                    field_id=f"{table.table_id}#field-{header.col_index}",
                    field_name=header.name,
                    normalized_name=header.normalized_name,
                    data_type="string",
                    required=False,
                )
                for header in table.headers
            ]
            description = " ".join(table.context_before).strip() or None
            target_tables.append(
                TargetTableSpec(
                    target_table_id=table.table_id,
                    logical_name=table.name or f"table_{index}",
                    schema=schema,
                    description=description,
                    local_constraints=_extract_local_constraints(table.table_id, description),
                    capacity=max(len(table.rows) - 1, 0),
                    supports_row_insert=True,
                    anchor=table.location,
                )
            )
        return TemplateSpec(template_doc_id=template_doc.doc_id, target_tables=target_tables, write_mode="mixed")
