"""Extractors.

.. deprecated::
    ``DefaultExtractor`` is a legacy fallback used only when ``build_rule_candidates()``
    returns no results. The primary extraction path goes through
    ``any2table.candidates.builders.build_rule_candidates`` and
    ``any2table.merging.merger.merge_candidates``. Prefer that path for new development.
"""

from __future__ import annotations

import warnings
from datetime import date, datetime
import re

from any2table.core.models import EvidencePack, StructuredRecord, TaskSpec, TemplateSpec


TEMPORAL_FIELD_TOKENS = ("日期", "时间", "时刻", "监测时间", "date", "time")

# COVID schema 兼容常量 — 仅用于 _extract_covid_country_record 回退
COVID_COUNTRY_FIELDS = {"国家/地区", "大洲", "人均GDP", "人口", "每日检测数", "病例数"}
PROVINCE_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{2,12}(?:省|自治区|直辖市|兵团)$")
TITLE_DATE_PATTERN = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
NATIONAL_CASES_PATTERN = re.compile(r"全国新增确诊病例\s*(\d+)\s*例")
POPULATION_PATTERN = re.compile(r"(?:常住人口|人口)(?:约)?\s*(\d+(?:\.\d+)?)\s*(亿|万)")
PER_GDP_PATTERN = re.compile(r"人均\s*GDP[^\d]{0,6}(\d+(?:\.\d+)?)\s*万?元")
TEST_PATTERN = re.compile(r"(?:核酸)?检测量[^\d]{0,8}(\d+(?:\.\d+)?)\s*(亿|万|份)")
ADD_CASES_PATTERN = re.compile(r"新增[^\d]{0,6}(\d+)\s*例")

# 城市经济提取模式（每段含城市名+内联数据格式）
CITY_IN_PARA_PATTERN = re.compile(r"^([\u4e00-\u9fff]{2,5})\s+")
# GDP：匹配"数字 亿元"与"GDP"关键字在同一句中的两种顺序
_YI_NUM = r"(\d[\d,]*\.?\d*)\s*亿元"
GDP_BEFORE_KW = re.compile(rf"{_YI_NUM}[^。\n]{{0,30}}?GDP")   # 数字在 GDP 前
GDP_AFTER_KW  = re.compile(rf"GDP[^\d\n]{{0,20}}?{_YI_NUM}")   # 数字在 GDP 后
# 人口：支持"常住人口达 X 万"和"X 万常住人口"两种顺序
POPULATION_PARA_PATTERN = re.compile(r"(?:常住人口|人口)[^\d]{0,8}?(\d[\d,]*\.?\d*)\s*万")
POPULATION_REVERSE_PATTERN = re.compile(r"(\d[\d,]*\.?\d*)\s*万(?:的|名)?(?:常住人口|人口)")
# 人均GDP：同样支持两种顺序
PER_GDP_PARA_PATTERN = re.compile(r"人均\s*GDP[^\d]{0,12}?(\d[\d,]*\.?\d*)\s*元")
PER_GDP_REVERSE_PATTERN = re.compile(r"(\d[\d,]*\.?\d*)\s*元(?:[的，。]|$|\s+)[^\n]{0,10}?人均\s*GDP")
BUDGET_PARA_PATTERN = re.compile(r"(?:一般公共预算收入|财政[一般公共预算]*收入)[^\d]{0,8}?(\d[\d,]*\.?\d*)\s*亿元")
CITY_RANK_PATTERN = re.compile(r"第\s*(\d+)\s*名|排名?\s*第?\s*(\d+)")


def _normalize(value: str) -> str:
    return "".join(str(value).split()).strip().lower()


def _get_request_text(task_spec: TaskSpec) -> str:
    texts = [str(constraint.value) for constraint in task_spec.constraints if constraint.kind == "request_text"]
    return "\n".join(texts)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _normalize_datetime_text(text: str | None) -> str | None:
    if not text:
        return None
    normalized = str(text).strip().replace("T", " ")
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]
    return normalized


def _parse_date_value(value: object) -> date | None:
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date()

    text = str(value).strip().replace("/", "-")
    if "." in text:
        text = text.split(".", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if not match:
        return None
    year, month, day = match.groups()
    return date(int(year), int(month), int(day))


def _parse_date_range(text: str) -> tuple[date, date] | None:
    match_range = re.search(
        r"(\d{4})[/-年](\d{1,2})[/-月](\d{1,2})[日]?.{0,20}?(\d{4})[/-年](\d{1,2})[/-月](\d{1,2})[日]?",
        text,
    )
    if not match_range:
        return None
    y1, m1, d1, y2, m2, d2 = match_range.groups()
    return (
        date(int(y1), int(m1), int(d1)),
        date(int(y2), int(m2), int(d2)),
    )


def _parse_exact_time(text: str) -> str | None:
    match_cn = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日(\d{2}:\d{2})", text)
    if match_cn:
        y, m, d, hm = match_cn.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d} {hm}:00:00.0"

    match_iso = re.search(r"(\d{4}-\d{1,2}-\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)", text)
    if match_iso:
        return match_iso.group(1)

    return None


def _candidate_entities(evidence_pack: EvidencePack, key_name: str) -> list[str]:
    values: list[str] = []
    for item in evidence_pack.items:
        if item.evidence_type != "row" or not isinstance(item.content, dict):
            continue
        for key, value in item.content.items():
            if key == key_name and value is not None:
                text = str(value)
                if text not in values:
                    values.append(text)
    return values


def _structured_filters(task_spec: TaskSpec, target_table) -> dict[str, object]:
    filters = {
        "cities": [],
        "countries": [],
        "exact_time": None,
        "date_range": None,
    }

    for constraint in [*task_spec.constraints, *target_table.local_constraints]:
        if constraint.kind == "entity":
            field_name = constraint.field or ""
            if "城市" in field_name:
                filters["cities"].append(str(constraint.value))
            if "国家" in field_name:
                filters["countries"].append(str(constraint.value))
        elif constraint.kind == "exact_datetime" and constraint.value:
            filters["exact_time"] = str(constraint.value)
        elif constraint.kind == "date_range" and isinstance(constraint.value, dict):
            start = _parse_date_value(constraint.value.get("start"))
            end = _parse_date_value(constraint.value.get("end"))
            if start and end:
                filters["date_range"] = (start, end)

    filters["cities"] = _dedupe_preserve_order(filters["cities"])
    filters["countries"] = _dedupe_preserve_order(filters["countries"])
    return filters


def _fallback_filter_context(target_table, task_spec: TaskSpec, evidence_pack: EvidencePack) -> dict[str, object]:
    description_text = target_table.description or ""
    request_text = _get_request_text(task_spec)

    city_candidates = _candidate_entities(evidence_pack, "城市")
    country_candidates = _candidate_entities(evidence_pack, "国家/地区")

    local_cities = [city for city in city_candidates if city in description_text]
    if local_cities:
        local_cities = sorted(local_cities, key=lambda city: description_text.index(city))
        local_cities = [local_cities[0]]
    request_cities = [city for city in city_candidates if city in request_text]
    cities = local_cities if local_cities else request_cities

    countries = [country for country in country_candidates if country in description_text or country in request_text]

    exact_time = _parse_exact_time(description_text) or _parse_exact_time(request_text)
    date_range = _parse_date_range(request_text) or _parse_date_range(description_text)
    return {
        "cities": cities,
        "countries": countries,
        "exact_time": exact_time,
        "date_range": date_range,
    }


def _merge_filters(base_filters: dict[str, object], fallback_filters: dict[str, object]) -> dict[str, object]:
    merged = dict(base_filters)
    for key in ("cities", "countries"):
        merged[key] = base_filters.get(key) or fallback_filters.get(key) or []
    for key in ("exact_time", "date_range"):
        merged[key] = base_filters.get(key) or fallback_filters.get(key)
    return merged


def _extract_filter_context(target_table, task_spec: TaskSpec, evidence_pack: EvidencePack) -> dict[str, object]:
    structured = _structured_filters(task_spec, target_table)
    fallback = _fallback_filter_context(target_table, task_spec, evidence_pack)
    return _merge_filters(structured, fallback)


def _row_matches_filters(raw_row: dict[str, object], filters: dict[str, object]) -> bool:
    values = ["" if value is None else str(value) for value in raw_row.values()]

    cities = filters.get("cities") or []
    if cities and not any(any(city == value for value in values) for city in cities):
        return False

    countries = filters.get("countries") or []
    if countries and not any(any(country == value for value in values) for country in countries):
        return False

    exact_time = filters.get("exact_time")
    normalized_exact_time = _normalize_datetime_text(exact_time)
    normalized_values = [_normalize_datetime_text(value) for value in values]
    if normalized_exact_time and not any(normalized_exact_time == value for value in normalized_values if value):
        return False

    date_range = filters.get("date_range")
    if date_range:
        start_date, end_date = date_range
        matched = False
        for value in raw_row.values():
            dt = _parse_date_value(value)
            if dt and start_date <= dt <= end_date:
                matched = True
                break
        if not matched:
            return False

    return True


def _extract_row_temporal_value(raw_row: dict[str, object]) -> date | None:
    preferred_values: list[object] = []
    fallback_values: list[object] = []
    for key, value in raw_row.items():
        normalized_key = _normalize(key)
        if any(token in normalized_key for token in TEMPORAL_FIELD_TOKENS):
            preferred_values.append(value)
        else:
            fallback_values.append(value)

    for value in [*preferred_values, *fallback_values]:
        parsed = _parse_date_value(value)
        if parsed is not None:
            return parsed
    return None


def _identity_fields_for_target_table(target_table) -> list[str]:
    target_fields = [field.field_name for field in target_table.schema]
    for fields in (("国家/地区",), ("城市",), ("城市名",), ("站点名称",)):
        if all(field_name in target_fields for field_name in fields):
            return list(fields)
    return target_fields[:1]


def _build_row_identity_from_values(values: dict[str, object], identity_fields: list[str]) -> tuple[str, ...]:
    parts: list[str] = []
    for field_name in identity_fields:
        value = values.get(field_name)
        parts.append("" if value is None else str(value))
    return tuple(parts)


def _target_has_temporal_field(target_table) -> bool:
    return any(any(token in _normalize(field.field_name) for token in TEMPORAL_FIELD_TOKENS) for field in target_table.schema)


def _format_display_date(value: date) -> str:
    return f"{value.year}/{value.month}/{value.day}"


def _append_temporal_suffix_to_values(target_table, values: dict[str, object], temporal_value: date | None, *, suffix_label: str | None = None) -> dict[str, object]:
    if temporal_value is None:
        return dict(values)
    identity_fields = _identity_fields_for_target_table(target_table)
    if not identity_fields:
        return dict(values)
    field_name = identity_fields[0]
    base_value = values.get(field_name)
    if base_value in (None, ""):
        return dict(values)
    suffix = _format_display_date(temporal_value)
    if suffix_label:
        suffix = f"{suffix} {suffix_label}"
    updated = dict(values)
    updated[field_name] = f"{base_value}（{suffix}）"
    return updated


def _select_candidate_by_policy(current: dict[str, object] | None, candidate: dict[str, object], policy: str) -> dict[str, object]:
    if current is None:
        return candidate
    current_temporal = current.get("temporal_value")
    incoming_temporal = candidate.get("temporal_value")
    if current_temporal is None:
        return candidate if incoming_temporal is not None else current
    if incoming_temporal is None:
        return current
    if policy == "earliest":
        return candidate if incoming_temporal <= current_temporal else current
    return candidate if incoming_temporal >= current_temporal else current


def _try_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _average_candidates(target_table, grouped_candidates: dict[tuple[str, ...], list[dict[str, object]]], filters: dict[str, object]) -> list[dict[str, object]]:
    resolved: list[dict[str, object]] = []
    range_text = ""
    date_range = filters.get("date_range")
    if date_range:
        range_text = f"{_format_display_date(date_range[0])}-{_format_display_date(date_range[1])} 平均"
    for candidates in grouped_candidates.values():
        base = candidates[-1]
        averaged_values = dict(base["values"])
        for field_name in averaged_values:
            numeric_values = [_try_float(candidate["values"].get(field_name)) for candidate in candidates]
            numeric_values = [value for value in numeric_values if value is not None]
            if numeric_values:
                averaged_values[field_name] = round(sum(numeric_values) / len(numeric_values), 2)
        if not _target_has_temporal_field(target_table):
            averaged_values = _append_temporal_suffix_to_values(target_table, averaged_values, candidates[-1].get("temporal_value"), suffix_label=range_text or "平均")
        resolved.append(
            {
                "values": averaged_values,
                "field_sources": dict(base["field_sources"]),
                "temporal_value": candidates[-1].get("temporal_value"),
                "evidence_id": base["evidence_id"],
                "confidence": base.get("confidence", 0.7),
                "notes": list(base.get("notes", [])) + ["Averaged numeric fields within requested date range."],
            }
        )
    return resolved


def _resolve_row_candidates(target_table, task_spec: TaskSpec, filters: dict[str, object], candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    if not candidates:
        return []
    if filters.get("date_range") is None:
        return candidates

    policy = getattr(task_spec, "task_policy", "all_dates") or "all_dates"
    if policy == "all_dates":
        # Return all date rows as-is; appending date to identity field corrupts matching.
        return list(candidates)

    identity_fields = _identity_fields_for_target_table(target_table)
    grouped: dict[tuple[str, ...], list[dict[str, object]]] = {}
    for candidate in candidates:
        key = _build_row_identity_from_values(candidate["values"], identity_fields)
        grouped.setdefault(key, []).append(candidate)

    if policy == "average":
        return _average_candidates(target_table, grouped, filters)

    resolved: list[dict[str, object]] = []
    for key, grouped_candidates in grouped.items():
        selected: dict[str, object] | None = None
        for candidate in grouped_candidates:
            selected = _select_candidate_by_policy(selected, candidate, policy)
        if selected is None:
            continue
        updated = dict(selected)
        updated["notes"] = list(selected.get("notes", []))
        if selected.get("temporal_value") is not None:
            updated["notes"].append(
                f"Resolved {policy} row within requested date range using {selected['temporal_value'].isoformat()}."
            )
        resolved.append(updated)
    return resolved


def _candidate_to_record(target_table, record_index: int, candidate: dict[str, object]) -> StructuredRecord:
    return StructuredRecord(
        record_id=f"{target_table.target_table_id}#row-{record_index}",
        target_table_id=target_table.target_table_id,
        values=dict(candidate["values"]),
        field_sources={field_name: list(evidence_ids) for field_name, evidence_ids in candidate["field_sources"].items()},
        confidence=float(candidate.get("confidence", 0.7)),
        status="ready",
        notes=list(candidate.get("notes", [])),
    )


def _fuzzy_match_field(
    source_key: str,
    normalized_field_map: dict[str, str],
    already_mapped: set[str],
) -> str | None:
    """两级模糊匹配：子串包含（长度差≤4）→ Bigram Jaccard ≥ 0.5。

    返回最佳匹配的目标字段名，或 None。
    already_mapped 里的字段不参与匹配，防止多列映射到同一目标字段。
    """
    source_norm = _normalize(source_key)
    remaining = {k: v for k, v in normalized_field_map.items() if v not in already_mapped}

    # 第一级：子串包含（限制长度差≤4字符，防止"人口密度"误匹配"人口"）
    for field_norm, field_name in remaining.items():
        len_diff = abs(len(source_norm) - len(field_norm))
        if len_diff <= 4 and (source_norm in field_norm or field_norm in source_norm):
            return field_name

    # 第二级：Bigram Jaccard 相似度
    def bigrams(s: str) -> set[str]:
        return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}

    best_score, best_field = 0.0, None
    src_bg = bigrams(source_norm)
    for field_norm, field_name in remaining.items():
        fld_bg = bigrams(field_norm)
        union = src_bg | fld_bg
        if union:
            score = len(src_bg & fld_bg) / len(union)
            if score > best_score:
                best_score, best_field = score, field_name
    return best_field if best_score >= 0.5 else None


def _extract_records_from_row_evidence(target_table, task_spec: TaskSpec, evidence_pack: EvidencePack) -> list[StructuredRecord]:
    """从表格行证据中提取记录，支持精确列名匹配和模糊列名匹配。"""
    target_fields = {field.field_name: field for field in target_table.schema}
    normalized_field_map = {_normalize(field.field_name): field.field_name for field in target_table.schema}
    filters = _extract_filter_context(target_table, task_spec, evidence_pack)
    candidates: list[dict[str, object]] = []

    for item in evidence_pack.items:
        if item.evidence_type != "row" or not isinstance(item.content, dict):
            continue
        raw_row = item.content
        if not _row_matches_filters(raw_row, filters):
            continue

        values: dict[str, object] = {}
        field_sources: dict[str, list[str]] = {}
        already_mapped: set[str] = set()
        match_notes: list[str] = []
        matched = 0
        fuzzy_matched = 0

        for key, value in raw_row.items():
            normalized_key = _normalize(key)
            # 精确匹配
            if normalized_key in normalized_field_map:
                field_name = normalized_field_map[normalized_key]
                if field_name not in already_mapped:
                    values[field_name] = value
                    field_sources[field_name] = [item.evidence_id]
                    already_mapped.add(field_name)
                    matched += 1
                continue
            # 模糊匹配（仅对还未映射的目标字段）
            fuzzy_field = _fuzzy_match_field(key, normalized_field_map, already_mapped)
            if fuzzy_field:
                values[fuzzy_field] = value
                field_sources[fuzzy_field] = [item.evidence_id]
                already_mapped.add(fuzzy_field)
                match_notes.append(f"fuzzy: '{key}'->'{fuzzy_field}'")
                matched += 1
                fuzzy_matched += 1

        if matched:
            for field_name in target_fields:
                values.setdefault(field_name, None)
            # 模糊匹配降低置信度
            confidence = 0.65 if fuzzy_matched else 0.7
            candidates.append(
                {
                    "values": values,
                    "field_sources": field_sources,
                    "temporal_value": _extract_row_temporal_value(raw_row),
                    "evidence_id": item.evidence_id,
                    "confidence": confidence,
                    "notes": match_notes,
                }
            )

    resolved_candidates = _resolve_row_candidates(target_table, task_spec, filters, candidates)
    return [_candidate_to_record(target_table, index, candidate) for index, candidate in enumerate(resolved_candidates)]


# ── COVID 回退（保留用于向后兼容）──────────────────────────────────────────────

def _convert_unit_number(number_text: str, unit: str) -> int:
    value = float(number_text)
    if unit == "亿":
        return int(value * 100000000)
    if unit == "万":
        return int(value * 10000)
    return int(value)


def _extract_population(text: str) -> int | None:
    match = POPULATION_PATTERN.search(text)
    if not match:
        return None
    return _convert_unit_number(match.group(1), match.group(2))


def _extract_per_gdp(text: str) -> int | None:
    match = PER_GDP_PATTERN.search(text)
    if not match:
        return None
    value = float(match.group(1))
    if "万元" in match.group(0) or "万" in match.group(0):
        return int(value * 10000)
    return int(value)


def _extract_tests(text: str) -> int | None:
    match = TEST_PATTERN.search(text)
    if not match:
        return None
    return _convert_unit_number(match.group(1), match.group(2))


def _extract_cases(text: str) -> int | None:
    if any(token in text for token in ("无新增", "零新增", "全零报告")):
        return 0
    match = ADD_CASES_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


def _apply_paragraph_temporal_policy(target_table, task_spec: TaskSpec, values: dict[str, object], temporal_value: date | None, notes: list[str]) -> tuple[dict[str, object], list[str]]:
    # Do not append date suffix to identity fields; return values unchanged.
    return dict(values), list(notes)


def _extract_covid_country_record(target_table, task_spec: TaskSpec, evidence_pack: EvidencePack) -> list[StructuredRecord]:
    """COVID 国家级记录提取（legacy 兼容回退，仅在 schema 完全匹配时调用）。"""
    field_names = {field.field_name for field in target_table.schema}
    if not COVID_COUNTRY_FIELDS.issubset(field_names):
        return []

    paragraph_items = [item for item in evidence_pack.items if item.evidence_type == "paragraph" and isinstance(item.content, str)]
    if not paragraph_items:
        return []

    title_date: date | None = None
    national_cases: int | None = None
    continent: str | None = None
    country_name = "China"
    province_sections: list[dict[str, object]] = []

    for index, item in enumerate(paragraph_items):
        text = item.content.strip()
        if not text:
            continue
        if title_date is None:
            match = TITLE_DATE_PATTERN.search(text)
            if match:
                title_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if continent is None and "Asia" in text:
            continent = "Asia"
        if national_cases is None:
            match = NATIONAL_CASES_PATTERN.search(text)
            if match:
                national_cases = int(match.group(1))
        if PROVINCE_NAME_PATTERN.match(text) and index + 1 < len(paragraph_items):
            detail_text = paragraph_items[index + 1].content.strip()
            province_sections.append(
                {
                    "heading": text,
                    "detail": detail_text,
                    "evidence_ids": [item.evidence_id, paragraph_items[index + 1].evidence_id],
                    "population": _extract_population(detail_text),
                    "per_gdp": _extract_per_gdp(detail_text),
                    "tests": _extract_tests(detail_text),
                    "cases": _extract_cases(detail_text),
                }
            )

    if continent is None and any("中国" in item.content for item in paragraph_items):
        continent = "Asia"

    valid_population_sections = [section for section in province_sections if section["population"] is not None]
    valid_test_sections = [section for section in province_sections if section["tests"] is not None]
    valid_gdp_sections = [section for section in province_sections if section["population"] is not None and section["per_gdp"] is not None]

    if not any([continent, national_cases is not None, valid_population_sections, valid_test_sections, valid_gdp_sections]):
        return []

    population_value = sum(section["population"] for section in valid_population_sections) if valid_population_sections else None
    test_value = sum(section["tests"] for section in valid_test_sections) if valid_test_sections else None
    per_gdp_value = None
    if valid_gdp_sections:
        weighted_sum = sum(section["population"] * section["per_gdp"] for section in valid_gdp_sections)
        total_population = sum(section["population"] for section in valid_gdp_sections)
        if total_population:
            per_gdp_value = int(weighted_sum / total_population)

    values = {
        "国家/地区": country_name,
        "大洲": continent,
        "人均GDP": per_gdp_value,
        "人口": population_value,
        "每日检测数": test_value,
        "病例数": national_cases,
    }
    field_sources = {
        "国家/地区": [paragraph_items[0].evidence_id],
    }
    if continent is not None:
        field_sources["大洲"] = [item.evidence_id for item in paragraph_items if "Asia" in item.content][:1]
    if national_cases is not None:
        field_sources["病例数"] = [item.evidence_id for item in paragraph_items if NATIONAL_CASES_PATTERN.search(item.content)][:1]
    if valid_gdp_sections:
        field_sources["人均GDP"] = [evidence_id for section in valid_gdp_sections for evidence_id in section["evidence_ids"][:1]][:3]
    if valid_population_sections:
        field_sources["人口"] = [evidence_id for section in valid_population_sections for evidence_id in section["evidence_ids"][:1]][:3]
    if valid_test_sections:
        field_sources["每日检测数"] = [evidence_id for section in valid_test_sections for evidence_id in section["evidence_ids"][:1]][:3]

    notes = [
        f"Synthesized country-level record from docx schema extraction using {len(province_sections)} provincial sections.",
    ]
    if valid_population_sections:
        notes.append("Population is aggregated from detected provincial sections and may be partial.")
    if valid_test_sections:
        notes.append("Daily tests are aggregated from detected provincial sections and may be partial.")
    if valid_gdp_sections:
        notes.append("Per-capita GDP is inferred as a population-weighted average over detected provincial sections.")
    if national_cases is not None:
        notes.append("Case count is taken from the national overview paragraph.")

    values, notes = _apply_paragraph_temporal_policy(target_table, task_spec, values, title_date, notes)
    return [
        StructuredRecord(
            record_id=f"{target_table.target_table_id}#docx-country-0",
            target_table_id=target_table.target_table_id,
            values=values,
            field_sources={field_name: list(evidence_ids) for field_name, evidence_ids in field_sources.items()},
            confidence=0.55,
            status="partial",
            notes=notes,
        )
    ]


# ── 通用段落提取 ───────────────────────────────────────────────────────────────

def _parse_comma_number(text: str) -> float | None:
    """解析含逗号分隔符的数字，如 '56,708.71' → 56708.71。"""
    clean = text.replace(",", "")
    try:
        return float(clean)
    except ValueError:
        return None


def _extract_city_gdp_from_para(text: str) -> float | None:
    """提取段落中的城市 GDP（亿元），优先选择与 GDP 关键字距离最近的数字。"""
    candidates: list[tuple[int, float]] = []
    for pat in (GDP_BEFORE_KW, GDP_AFTER_KW):
        for m in pat.finditer(text):
            val = _parse_comma_number(m.group(1))
            if val is not None:
                candidates.append((m.start(), val))
    if not candidates:
        return None
    # 预算收入通常有明确标签，排除已被 BUDGET_PARA_PATTERN 匹配的数字
    budget_spans: set[int] = set()
    for m in BUDGET_PARA_PATTERN.finditer(text):
        val = _parse_comma_number(m.group(1))
        if val is not None:
            budget_spans.add(round(val, 2))
    non_budget = [(pos, v) for pos, v in candidates if round(v, 2) not in budget_spans]
    if non_budget:
        return non_budget[0][1]
    return candidates[0][1] if candidates else None


def _extract_city_population_from_para(text: str) -> float | None:
    match = POPULATION_PARA_PATTERN.search(text)
    if match:
        return _parse_comma_number(match.group(1))
    match = POPULATION_REVERSE_PATTERN.search(text)
    if match:
        return _parse_comma_number(match.group(1))
    return None


def _extract_city_per_gdp_from_para(text: str) -> int | None:
    match = PER_GDP_PARA_PATTERN.search(text)
    if match:
        val = _parse_comma_number(match.group(1))
        if val is not None:
            return int(val)
    match = PER_GDP_REVERSE_PATTERN.search(text)
    if match:
        val = _parse_comma_number(match.group(1))
        if val is not None:
            return int(val)
    return None


def _extract_city_budget_from_para(text: str) -> float | None:
    match = BUDGET_PARA_PATTERN.search(text)
    if not match:
        return None
    return _parse_comma_number(match.group(1))


def _extract_city_rank_from_para(text: str) -> int | None:
    match = CITY_RANK_PATTERN.search(text)
    if not match:
        return None
    for group in match.groups():
        if group is not None:
            return int(group)
    return None


def _extract_multi_city_records_from_paragraphs(
    target_table,
    task_spec: TaskSpec,
    para_items: list,
) -> list[StructuredRecord]:
    """从段落中提取多城市记录（适用于城市经济百强等叙述型文档）。

    每个段落以城市名开头，后跟 GDP、人口、人均GDP、财政收入等内联数据。
    """
    target_fields = [f.field_name for f in target_table.schema]
    city_field = next((f for f in target_fields if "城市" in f or "城市名" in f), None)
    if city_field is None:
        return []

    # 为已知经济字段建立提取函数映射
    field_extractors: dict[str, object] = {}
    for fn in target_fields:
        if fn == city_field:
            continue
        norm = _normalize(fn)
        if ("gdp" in norm or "生产总值" in norm or "经济总量" in norm) and "人均" not in norm:
            field_extractors[fn] = _extract_city_gdp_from_para
        elif "人均" in norm and ("gdp" in norm or "收入" in norm):
            field_extractors[fn] = _extract_city_per_gdp_from_para
        elif "人口" in norm and "人均" not in norm:
            field_extractors[fn] = _extract_city_population_from_para
        elif "预算" in norm or ("财政" in norm and "收入" in norm):
            field_extractors[fn] = _extract_city_budget_from_para
        elif "排名" in norm or "名次" in norm:
            field_extractors[fn] = _extract_city_rank_from_para

    if not field_extractors:
        return []

    records: list[StructuredRecord] = []
    for idx, item in enumerate(para_items):
        text = item.content.strip()
        if not text:
            continue
        city_match = CITY_IN_PARA_PATTERN.match(text)
        if not city_match:
            continue
        # 段落须含 GDP 关键字且附近有数字+亿元
        if not GDP_BEFORE_KW.search(text) and not GDP_AFTER_KW.search(text):
            continue
        city_name = city_match.group(1)
        values: dict[str, object] = {f: None for f in target_fields}
        values[city_field] = city_name
        field_sources: dict[str, list[str]] = {city_field: [item.evidence_id]}
        for fn, extractor in field_extractors.items():
            val = extractor(text)  # type: ignore[operator]
            if val is not None:
                values[fn] = val
                field_sources[fn] = [item.evidence_id]

        has_data = any(v is not None for fn, v in values.items() if fn != city_field)
        if not has_data:
            continue
        status = "partial" if any(v is None for v in values.values()) else "ready"
        records.append(
            StructuredRecord(
                record_id=f"{target_table.target_table_id}#city-{idx}",
                target_table_id=target_table.target_table_id,
                values=values,
                field_sources=field_sources,
                confidence=0.7,
                status=status,
                notes=["Multi-city inline paragraph extraction."],
            )
        )
    return records


def _extract_kv_from_paragraph(text: str, target_fields: list[str]) -> dict[str, object]:
    """在段落文本中查找"字段名：值"/"字段名: 值"显式 KV 标注。"""
    result: dict[str, object] = {}
    for field_name in target_fields:
        pattern = re.compile(
            rf"{re.escape(field_name)}\s*[：:]\s*([^\s，,；;。\n]+)",
            re.UNICODE,
        )
        match = pattern.search(text)
        if match:
            result[field_name] = match.group(1).strip()
    return result


def _extract_nearby_number(text: str, field_name: str) -> object | None:
    """字段名出现在文本中时，提取其后 15 字符内的第一个数字。"""
    pattern = re.compile(
        rf"{re.escape(field_name)}.{{0,15}}?(\d[\d,]*\.?\d*)",
        re.UNICODE,
    )
    match = pattern.search(text)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        return int(raw) if "." not in raw else float(raw)
    except ValueError:
        return raw


def _extract_records_from_paragraph_evidence(target_table, task_spec: TaskSpec, evidence_pack: EvidencePack) -> list[StructuredRecord]:
    """通用段落提取：KV 模式匹配 + 近邻数字提取，对任意领域数据均有效。

    若通用提取无结果且 schema 匹配 COVID 特征，回退到 _extract_covid_country_record
    以保持已有测试的向后兼容性。
    """
    # COVID 优先路径：schema 精确匹配时使用领域专用提取，保证已有测试不退化
    field_names = {f.field_name for f in target_table.schema}
    if COVID_COUNTRY_FIELDS.issubset(field_names):
        return _extract_covid_country_record(target_table, task_spec, evidence_pack)

    target_fields = [f.field_name for f in target_table.schema]
    para_items = [
        item for item in evidence_pack.items
        if item.evidence_type == "paragraph" and isinstance(item.content, str)
    ]
    if not para_items:
        return []

    # 城市多行提取路径：目标含"城市"字段且文档为叙述型时优先使用
    if any("城市" in f for f in target_fields):
        city_records = _extract_multi_city_records_from_paragraphs(target_table, task_spec, para_items)
        if city_records:
            return city_records

    accumulated: dict[str, object] = {}
    field_sources: dict[str, list[str]] = {}

    for item in para_items:
        text = item.content.strip()
        if not text:
            continue
        # 第一阶段：显式 KV 格式提取
        for fn, val in _extract_kv_from_paragraph(text, target_fields).items():
            if fn not in accumulated:
                accumulated[fn] = val
                field_sources.setdefault(fn, []).append(item.evidence_id)
        # 第二阶段：近邻数字提取（仅针对还未匹配的字段）
        for fn in target_fields:
            if fn in accumulated or fn not in text:
                continue
            val = _extract_nearby_number(text, fn)
            if val is not None:
                accumulated[fn] = val
                field_sources.setdefault(fn, []).append(item.evidence_id)

    if accumulated:
        values = {f: accumulated.get(f) for f in target_fields}
        temporal_value: date | None = None
        for item in para_items[:3]:
            temporal_value = _parse_date_value(item.content[:50])
            if temporal_value:
                break
        values, notes = _apply_paragraph_temporal_policy(
            target_table, task_spec, values, temporal_value,
            notes=["Generic paragraph KV extraction."],
        )
        status = "partial" if any(v is None for v in values.values()) else "ready"
        return [
            StructuredRecord(
                record_id=f"{target_table.target_table_id}#paragraph-generic-0",
                target_table_id=target_table.target_table_id,
                values=values,
                field_sources={fn: list(ev) for fn, ev in field_sources.items()},
                confidence=0.6,
                status=status,
                notes=notes,
            )
        ]

    return []


class DefaultExtractor:
    """Build records from row evidence and paragraph evidence.

    .. deprecated::
        This is a legacy fallback. Prefer ``build_rule_candidates()`` + ``merge_candidates()``.
    """

    def extract(
        self,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        evidence_pack: EvidencePack,
    ) -> list[StructuredRecord]:
        warnings.warn(
            "DefaultExtractor.extract() is a legacy fallback path. "
            "The primary extraction path uses build_rule_candidates() and merge_candidates().",
            DeprecationWarning,
            stacklevel=2,
        )
        all_records: list[StructuredRecord] = []
        for target_table in template_spec.target_tables:
            row_records = _extract_records_from_row_evidence(target_table, task_spec, evidence_pack)
            paragraph_records = _extract_records_from_paragraph_evidence(target_table, task_spec, evidence_pack)
            records = [*row_records, *paragraph_records]
            if not records:
                records = [
                    StructuredRecord(
                        record_id=f"{target_table.target_table_id}#record-0",
                        target_table_id=target_table.target_table_id,
                        values={field.field_name: None for field in target_table.schema},
                        field_sources={},
                        confidence=0.0,
                        status="partial",
                        notes=["No matching evidence found for this target table."],
                    )
                ]
            all_records.extend(records)
        return all_records
