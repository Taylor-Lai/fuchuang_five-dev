"""Extractors."""

from __future__ import annotations

from datetime import date, datetime
import re

from any2table.core.models import EvidencePack, StructuredRecord, TaskSpec, TemplateSpec


TEMPORAL_FIELD_TOKENS = ("日期", "时间", "时刻", "监测时间", "date", "time")
COVID_COUNTRY_FIELDS = {"国家/地区", "大洲", "人均GDP", "人口", "每日检测数", "病例数"}
PROVINCE_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{2,12}(?:省|自治区|直辖市|兵团)$")
TITLE_DATE_PATTERN = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
NATIONAL_CASES_PATTERN = re.compile(r"全国新增确诊病例\s*(\d+)\s*例")
POPULATION_PATTERN = re.compile(r"(?:常住人口|人口)(?:约)?\s*(\d+(?:\.\d+)?)\s*(亿|万)")
PER_GDP_PATTERN = re.compile(r"人均\s*GDP[^\d]{0,6}(\d+(?:\.\d+)?)\s*万?元")
TEST_PATTERN = re.compile(r"(?:核酸)?检测量[^\d]{0,8}(\d+(?:\.\d+)?)\s*(亿|万|份)")
ADD_CASES_PATTERN = re.compile(r"新增[^\d]{0,6}(\d+)\s*例")
ECON_PARAGRAPH_PATTERN = re.compile(
    r"(?P<city>[\u4e00-\u9fff]{2,6}(?:市|州|地区)?)"
    r".*?(?P<gdp>\d[\d,]*\.?\d*)\s*亿元"
    r".*?(?P<pop>\d[\d,]*\.?\d*)\s*万"
    r".*?人均\s*GDP[^\d]*(?P<per_gdp>\d[\d,]*\.?\d*)\s*元"
    r".*?一般公共预算收入[^\d]*(?P<budget>\d[\d,]*\.?\d*)\s*亿元"
)


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
        if _target_has_temporal_field(target_table):
            return candidates
        resolved: list[dict[str, object]] = []
        for candidate in candidates:
            updated = dict(candidate)
            updated["values"] = _append_temporal_suffix_to_values(target_table, candidate["values"], candidate.get("temporal_value"))
            if candidate.get("temporal_value") is not None:
                updated["notes"] = list(candidate.get("notes", [])) + [
                    f"Expanded all_dates row using {candidate['temporal_value'].isoformat()}."
                ]
            resolved.append(updated)
        return resolved

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


def _extract_records_from_row_evidence(target_table, task_spec: TaskSpec, evidence_pack: EvidencePack) -> list[StructuredRecord]:
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
        matched = 0
        for key, value in raw_row.items():
            normalized_key = _normalize(key)
            if normalized_key in normalized_field_map:
                field_name = normalized_field_map[normalized_key]
                values[field_name] = value
                field_sources[field_name] = [item.evidence_id]
                matched += 1
        if matched:
            for field_name in target_fields:
                values.setdefault(field_name, None)
            candidates.append(
                {
                    "values": values,
                    "field_sources": field_sources,
                    "temporal_value": _extract_row_temporal_value(raw_row),
                    "evidence_id": item.evidence_id,
                    "confidence": 0.7,
                    "notes": [],
                }
            )

    resolved_candidates = _resolve_row_candidates(target_table, task_spec, filters, candidates)
    return [_candidate_to_record(target_table, index, candidate) for index, candidate in enumerate(resolved_candidates)]


def _clean_city_name(value: str) -> str:
    value = value.strip()
    for suffix in ("以", "凭", "在", "达"):
        if value.endswith(suffix) and len(value) > 2:
            return value[:-1]
    return value


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
    if temporal_value is None:
        return dict(values), list(notes)
    if getattr(task_spec, "task_policy", "all_dates") != "all_dates":
        return dict(values), list(notes)
    if _target_has_temporal_field(target_table):
        return dict(values), list(notes)
    updated_values = _append_temporal_suffix_to_values(target_table, values, temporal_value)
    updated_notes = list(notes)
    updated_notes.append(f"Expanded all_dates paragraph record using {temporal_value.isoformat()}.")
    return updated_values, updated_notes


def _extract_covid_country_record(target_table, task_spec: TaskSpec, evidence_pack: EvidencePack) -> list[StructuredRecord]:
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


def _extract_records_from_econ_paragraphs(target_table, evidence_pack: EvidencePack) -> list[StructuredRecord]:
    field_names = [field.field_name for field in target_table.schema]
    normalized_fields = [_normalize(name) for name in field_names]
    city_field = next((name for name in field_names if "城市" in name), field_names[0] if field_names else None)
    gdp_field = next((name for name in field_names if "gdp总量" in _normalize(name)), None)
    pop_field = next((name for name in field_names if "常住人口" in name), None)
    per_gdp_field = next((name for name in field_names if "人均gdp" in _normalize(name)), None)
    budget_field = next((name for name in field_names if "一般公共预算收入" in name), None)
    if not all([city_field, gdp_field, pop_field, per_gdp_field, budget_field]):
        return []

    records: list[StructuredRecord] = []
    for item in evidence_pack.items:
        if item.evidence_type != "paragraph" or not isinstance(item.content, str):
            continue
        if not any("gdp" in nf for nf in normalized_fields):
            continue
        match = ECON_PARAGRAPH_PATTERN.search(item.content)
        if not match:
            continue
        values = {
            city_field: _clean_city_name(match.group("city")),
            gdp_field: match.group("gdp"),
            pop_field: match.group("pop"),
            per_gdp_field: match.group("per_gdp"),
            budget_field: match.group("budget"),
        }
        records.append(
            StructuredRecord(
                record_id=f"{target_table.target_table_id}#paragraph-{len(records)}",
                target_table_id=target_table.target_table_id,
                values=values,
                field_sources={field: [item.evidence_id] for field in values},
                confidence=0.8,
                status="ready",
            )
        )
    return records


def _extract_air_quality_records(target_table, evidence_pack: EvidencePack) -> list[StructuredRecord]:
    field_names = [field.field_name for field in target_table.schema]
    city_field = next((name for name in field_names if "城市" in name), None)
    pm25_field = next((name for name in field_names if "PM2.5" in name), None)
    pm10_field = next((name for name in field_names if "PM10" in name), None)
    so2_field = next((name for name in field_names if "SO2" in name), None)
    no2_field = next((name for name in field_names if "NO2" in name), None)
    co_field = next((name for name in field_names if "CO" in name), None)
    o3_field = next((name for name in field_names if "O3" in name), None)
    
    if not city_field or not any([pm25_field, pm10_field, so2_field, no2_field, co_field, o3_field]):
        return []
    
    city_pattern = re.compile(r"(\w+?)：")
    pm25_pattern = re.compile(r"- PM2\.5：(\d+)")
    pm10_pattern = re.compile(r"- PM10：(\d+)")
    so2_pattern = re.compile(r"- SO2：(\d+)")
    no2_pattern = re.compile(r"- NO2：(\d+)")
    co_pattern = re.compile(r"- CO：(\d+\.\d+)")
    o3_pattern = re.compile(r"- O3：(\d+)")
    
    records: list[StructuredRecord] = []
    current_city = None
    current_data = {}
    current_evidence_id = None
    
    for item in evidence_pack.items:
        if item.evidence_type != "paragraph" or not isinstance(item.content, str):
            continue
        
        text = item.content
        city_match = city_pattern.search(text)
        if city_match:
            if current_city and current_data:
                values = {city_field: current_city}
                if pm25_field and "pm25" in current_data:
                    values[pm25_field] = current_data["pm25"]
                if pm10_field and "pm10" in current_data:
                    values[pm10_field] = current_data["pm10"]
                if so2_field and "so2" in current_data:
                    values[so2_field] = current_data["so2"]
                if no2_field and "no2" in current_data:
                    values[no2_field] = current_data["no2"]
                if co_field and "co" in current_data:
                    values[co_field] = current_data["co"]
                if o3_field and "o3" in current_data:
                    values[o3_field] = current_data["o3"]
                
                records.append(
                    StructuredRecord(
                        record_id=f"{target_table.target_table_id}#air-quality-{len(records)}",
                        target_table_id=target_table.target_table_id,
                        values=values,
                        field_sources={field: [current_evidence_id] for field in values},
                        confidence=0.8,
                        status="ready",
                    )
                )
            
            current_city = city_match.group(1)
            current_data = {}
            current_evidence_id = item.evidence_id
        
        pm25_match = pm25_pattern.search(text)
        if pm25_match:
            current_data["pm25"] = int(pm25_match.group(1))
        
        pm10_match = pm10_pattern.search(text)
        if pm10_match:
            current_data["pm10"] = int(pm10_match.group(1))
        
        so2_match = so2_pattern.search(text)
        if so2_match:
            current_data["so2"] = int(so2_match.group(1))
        
        no2_match = no2_pattern.search(text)
        if no2_match:
            current_data["no2"] = int(no2_match.group(1))
        
        co_match = co_pattern.search(text)
        if co_match:
            current_data["co"] = float(co_match.group(1))
        
        o3_match = o3_pattern.search(text)
        if o3_match:
            current_data["o3"] = int(o3_match.group(1))
    
    if current_city and current_data:
        values = {city_field: current_city}
        if pm25_field and "pm25" in current_data:
            values[pm25_field] = current_data["pm25"]
        if pm10_field and "pm10" in current_data:
            values[pm10_field] = current_data["pm10"]
        if so2_field and "so2" in current_data:
            values[so2_field] = current_data["so2"]
        if no2_field and "no2" in current_data:
            values[no2_field] = current_data["no2"]
        if co_field and "co" in current_data:
            values[co_field] = current_data["co"]
        if o3_field and "o3" in current_data:
            values[o3_field] = current_data["o3"]
        
        records.append(
            StructuredRecord(
                record_id=f"{target_table.target_table_id}#air-quality-{len(records)}",
                target_table_id=target_table.target_table_id,
                values=values,
                field_sources={field: [current_evidence_id] for field in values},
                confidence=0.8,
                status="ready",
            )
        )
    
    return records

def _extract_student_records(target_table, evidence_pack: EvidencePack) -> list[StructuredRecord]:
    field_names = [field.field_name for field in target_table.schema]
    name_field = next((name for name in field_names if "学生姓名" in name or "姓名" in name), None)
    teacher_field = next((name for name in field_names if "指导教师" in name or "教师" in name), None)
    student_id_field = next((name for name in field_names if "学号" in name), None)
    course_field = next((name for name in field_names if "课程名称" in name or "课程" in name), None)
    
    if not name_field:
        return []
    
    import re
    # 支持带冒号和不带冒号的格式，以及更多字段名称变体
    student_pattern = re.compile(r"学生姓名[:：]?\s*(.*?)\s*指导教师[:：]?\s*(.*?)\s*学号[:：]?\s*(.*?)\s*课程名称[:：]?\s*(.*?)(?:$|\n)", re.DOTALL)
    name_pattern = re.compile(r"^\s*(?:学生姓名|姓名|学生)[:：]?\s*(.*?)\s*$")
    teacher_pattern = re.compile(r"^\s*(?:指导教师|教师|老师)[:：]?\s*(.*?)\s*$")
    id_pattern = re.compile(r"^\s*(?:学号|ID|id)[:：]?\s*(.*?)\s*$")
    course_pattern = re.compile(r"^\s*(?:课程名称|课程|课)[:：]?\s*(.*?)\s*$")
    
    # 过滤掉无效值的关键词
    invalid_values = ["签字", "签名", "日期", "时间", "地点", "备注"]
    
    # 跨段落收集学生信息
    student_info = {}
    evidence_ids = {}
    source_lines = []
    
    for item in evidence_pack.items:
        if item.evidence_type != "paragraph" or not isinstance(item.content, str):
            continue
        
        text = item.content
        # 收集所有行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        source_lines.extend(lines)
        
        # 尝试匹配完整的学生信息
        matches = student_pattern.findall(text)
        for match in matches:
            name, teacher, student_id, course = match
            values = {}
            
            # 过滤无效值
            if name.strip() and not any(invalid in name for invalid in invalid_values):
                values[name_field] = name.strip()
            if teacher_field and teacher.strip() and not any(invalid in teacher for invalid in invalid_values):
                values[teacher_field] = teacher.strip()
            if student_id_field and student_id.strip() and not any(invalid in student_id for invalid in invalid_values):
                values[student_id_field] = student_id.strip()
            if course_field and course.strip() and not any(invalid in course for invalid in invalid_values):
                values[course_field] = course.strip()
            
            if values:
                return [
                    StructuredRecord(
                        record_id=f"{target_table.target_table_id}#student-0",
                        target_table_id=target_table.target_table_id,
                        values=values,
                        field_sources={field: [item.evidence_id] for field in values},
                        confidence=0.8,
                        status="ready",
                    )
                ]
        
        # 尝试匹配单独的字段（逐行匹配）
        for line in lines:
            # 跳过包含无效关键词的行
            if any(invalid in line for invalid in invalid_values):
                continue
            
            name_match = name_pattern.match(line)
            if name_match:
                name_value = name_match.group(1).strip()
                if name_value and not any(invalid in name_value for invalid in invalid_values):
                    student_info[name_field] = name_value
                    evidence_ids[name_field] = item.evidence_id
                continue
            
            teacher_match = teacher_pattern.match(line)
            if teacher_match and teacher_field:
                teacher_value = teacher_match.group(1).strip()
                if teacher_value and not any(invalid in teacher_value for invalid in invalid_values):
                    student_info[teacher_field] = teacher_value
                    evidence_ids[teacher_field] = item.evidence_id
                continue
            
            id_match = id_pattern.match(line)
            if id_match and student_id_field:
                id_value = id_match.group(1).strip()
                if id_value and not any(invalid in id_value for invalid in invalid_values):
                    student_info[student_id_field] = id_value
                    evidence_ids[student_id_field] = item.evidence_id
                continue
            
            course_match = course_pattern.match(line)
            if course_match and course_field:
                course_value = course_match.group(1).strip()
                if course_value and not any(invalid in course_value for invalid in invalid_values):
                    student_info[course_field] = course_value
                    evidence_ids[course_field] = item.evidence_id
                continue
    
    # 检查是否成功提取了所有字段
    if student_info and len(student_info) >= 2:
        field_sources = {field: [evidence_ids.get(field, evidence_pack.items[0].evidence_id)] for field in student_info}
        return [
            StructuredRecord(
                record_id=f"{target_table.target_table_id}#student-0",
                target_table_id=target_table.target_table_id,
                values=student_info,
                field_sources=field_sources,
                confidence=0.7,
                status="ready",
            )
        ]
    
    # 尝试处理没有字段名称的情况，根据表头顺序匹配数据
    if len(source_lines) >= 4:
        values = {}
        # 过滤无效值
        if name_field and source_lines[0] and not any(invalid in source_lines[0] for invalid in invalid_values):
            values[name_field] = source_lines[0]
        if teacher_field and source_lines[1] and not any(invalid in source_lines[1] for invalid in invalid_values):
            values[teacher_field] = source_lines[1]
        if student_id_field and source_lines[2] and not any(invalid in source_lines[2] for invalid in invalid_values):
            values[student_id_field] = source_lines[2]
        if course_field and source_lines[3] and not any(invalid in source_lines[3] for invalid in invalid_values):
            values[course_field] = source_lines[3]
        
        if values:
            field_sources = {field: [evidence_pack.items[0].evidence_id] for field in values}
            return [
                StructuredRecord(
                    record_id=f"{target_table.target_table_id}#student-0",
                    target_table_id=target_table.target_table_id,
                    values=values,
                    field_sources=field_sources,
                    confidence=0.6,
                    status="ready",
                )
            ]
    
    # 尝试处理只有学生姓名的情况
    elif len(source_lines) == 1 and name_field:
        name_value = source_lines[0]
        if name_value and not any(invalid in name_value for invalid in invalid_values):
            values = {name_field: name_value}
            field_sources = {name_field: [evidence_pack.items[0].evidence_id]}
            return [
                StructuredRecord(
                    record_id=f"{target_table.target_table_id}#student-0",
                    target_table_id=target_table.target_table_id,
                    values=values,
                    field_sources=field_sources,
                    confidence=0.5,
                    status="ready",
                )
            ]
    
    return []

def _extract_records_from_paragraph_evidence(target_table, task_spec: TaskSpec, evidence_pack: EvidencePack) -> list[StructuredRecord]:
    covid_records = _extract_covid_country_record(target_table, task_spec, evidence_pack)
    econ_records = _extract_records_from_econ_paragraphs(target_table, evidence_pack)
    air_quality_records = _extract_air_quality_records(target_table, evidence_pack)
    student_records = _extract_student_records(target_table, evidence_pack)
    return [*covid_records, *econ_records, *air_quality_records, *student_records]


class DefaultExtractor:
    """Build records from row evidence and paragraph evidence."""

    def extract(
        self,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        evidence_pack: EvidencePack,
    ) -> list[StructuredRecord]:
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
