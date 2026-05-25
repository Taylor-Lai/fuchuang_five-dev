"""Compute engines.

This module keeps deterministic post-processing out of the LLM path.  The
competition data is table-centric and often numeric, so normalizing units and
calculating simple derived fields here makes the pipeline easier to explain and
less dependent on model guesses.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from any2table.core.models import StructuredRecord, TaskSpec

UNIT_MULTIPLIERS = {
    "亿": Decimal("100000000"),
    "万": Decimal("10000"),
    "千": Decimal("1000"),
    "百": Decimal("100"),
}

NUMBER_WITH_UNIT_RE = re.compile(r"^\s*(-?\d+(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*(亿|万|千|百)?(?:人|元|亿元|万元|份|例|个|%|％)?\s*$")


def _field_norm(field_name: str) -> str:
    return "".join(str(field_name).split()).lower()


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None

    text = str(value).strip().replace(",", "")
    if not text or text in {"未找到", "null", "None"}:
        return None
    match = NUMBER_WITH_UNIT_RE.match(text)
    if not match:
        return None
    number_text, unit = match.groups()
    try:
        number = Decimal(number_text)
    except InvalidOperation:
        return None
    if unit:
        number *= UNIT_MULTIPLIERS[unit]
    return number


def _format_decimal(value: Decimal) -> int | float:
    normalized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if normalized == normalized.to_integral_value():
        return int(normalized)
    return float(normalized)


def _normalize_numeric_values(record: StructuredRecord) -> None:
    for field_name, value in list(record.values.items()):
        normalized_name = _field_norm(field_name)
        if not any(token in normalized_name for token in ("数", "量", "人口", "gdp", "收入", "金额", "预算", "病例", "检测", "比例", "率")):
            continue
        number = _to_decimal(value)
        if number is None:
            continue
        normalized = _format_decimal(number)
        if normalized != value:
            record.values[field_name] = normalized
            record.notes.append(f"Normalized numeric field '{field_name}' from '{value}' to '{normalized}'.")


def _compute_per_capita_fields(record: StructuredRecord) -> None:
    fields = list(record.values.keys())
    normalized_map = {_field_norm(field): field for field in fields}

    population_field = next((field for norm, field in normalized_map.items() if "人口" in norm and "人均" not in norm), None)
    gdp_field = next((field for norm, field in normalized_map.items() if ("gdp" in norm or "生产总值" in norm) and "人均" not in norm), None)
    per_gdp_field = next((field for norm, field in normalized_map.items() if "人均" in norm and ("gdp" in norm or "生产总值" in norm)), None)

    if not (population_field and gdp_field and per_gdp_field):
        return
    if record.values.get(per_gdp_field) not in (None, "", "未找到"):
        return

    population = _to_decimal(record.values.get(population_field))
    gdp = _to_decimal(record.values.get(gdp_field))
    if not population or not gdp:
        return

    # If GDP is still in "亿元" scale, convert to yuan before dividing.
    gdp_text = str(record.values.get(gdp_field))
    if "亿" in gdp_text:
        gdp *= UNIT_MULTIPLIERS["亿"]
    per_capita = gdp / population
    record.values[per_gdp_field] = _format_decimal(per_capita)
    sources = []
    sources.extend(record.field_sources.get(gdp_field, []))
    sources.extend(record.field_sources.get(population_field, []))
    if sources:
        record.field_sources[per_gdp_field] = list(dict.fromkeys(sources))
    record.notes.append(f"Computed '{per_gdp_field}' from '{gdp_field}' and '{population_field}'.")


def _compute_rate_fields(record: StructuredRecord) -> None:
    fields = list(record.values.keys())
    normalized_map = {_field_norm(field): field for field in fields}
    rate_fields = [field for norm, field in normalized_map.items() if ("率" in norm or "比例" in norm) and record.values.get(field) in (None, "", "未找到")]
    if not rate_fields:
        return

    numerator_field = next((field for norm, field in normalized_map.items() if any(token in norm for token in ("病例", "确诊", "检测", "数量"))), None)
    denominator_field = next((field for norm, field in normalized_map.items() if "人口" in norm and "人均" not in norm), None)
    if not (numerator_field and denominator_field):
        return

    numerator = _to_decimal(record.values.get(numerator_field))
    denominator = _to_decimal(record.values.get(denominator_field))
    if numerator is None or not denominator:
        return

    rate = numerator / denominator
    for field in rate_fields:
        record.values[field] = _format_decimal(rate)
        sources = []
        sources.extend(record.field_sources.get(numerator_field, []))
        sources.extend(record.field_sources.get(denominator_field, []))
        if sources:
            record.field_sources[field] = list(dict.fromkeys(sources))
        record.notes.append(f"Computed '{field}' from '{numerator_field}' and '{denominator_field}'.")


def _numeric_source_fields(record: StructuredRecord, *, exclude_field: str) -> list[tuple[str, Decimal]]:
    values: list[tuple[str, Decimal]] = []
    for field_name, value in record.values.items():
        if field_name == exclude_field:
            continue
        number = _to_decimal(value)
        if number is not None:
            values.append((field_name, number))
    return values


def _compute_row_aggregate_fields(record: StructuredRecord) -> None:
    for field_name, value in list(record.values.items()):
        if value not in (None, "", "未找到"):
            continue
        normalized_name = _field_norm(field_name)
        numeric_fields = _numeric_source_fields(record, exclude_field=field_name)
        if not numeric_fields:
            continue

        aggregate: Decimal | None = None
        operation = ""
        if any(token in normalized_name for token in ("合计", "总计", "总数", "总量", "total", "sum")):
            aggregate = sum(number for _, number in numeric_fields)
            operation = "sum"
        elif any(token in normalized_name for token in ("平均", "均值", "average", "avg")):
            aggregate = sum(number for _, number in numeric_fields) / Decimal(len(numeric_fields))
            operation = "average"

        if aggregate is None:
            continue
        record.values[field_name] = _format_decimal(aggregate)
        source_ids: list[str] = []
        for source_field, _ in numeric_fields:
            source_ids.extend(record.field_sources.get(source_field, []))
        if source_ids:
            record.field_sources[field_name] = list(dict.fromkeys(source_ids))
        record.notes.append(
            f"Auto-corrected missing aggregate field '{field_name}' using row-level {operation} over "
            f"{len(numeric_fields)} numeric field(s)."
        )


def _mark_remaining_missing_required(record: StructuredRecord) -> None:
    missing = [field_name for field_name, value in record.values.items() if value in (None, "", "未找到")]
    if missing:
        record.notes.append(f"Remaining missing field(s) after deterministic correction: {', '.join(missing[:10])}.")


def _is_summary_record(record: StructuredRecord) -> tuple[bool, str]:
    for value in record.values.values():
        text = str(value).strip()
        if text in {"合计", "总计", "总数", "总量", "total", "sum"}:
            return True, "sum"
        if text in {"平均", "均值", "average", "avg"}:
            return True, "average"
    return False, ""


def _compute_cross_record_summary(records: list[StructuredRecord]) -> None:
    by_table: dict[str, list[StructuredRecord]] = {}
    for record in records:
        by_table.setdefault(record.target_table_id, []).append(record)

    for table_records in by_table.values():
        summary_records = []
        source_records = []
        for record in table_records:
            is_summary, operation = _is_summary_record(record)
            if is_summary:
                summary_records.append((record, operation))
            else:
                source_records.append(record)
        if not summary_records or not source_records:
            continue

        for summary_record, operation in summary_records:
            for field_name, value in list(summary_record.values.items()):
                if value not in (None, "", "未找到"):
                    continue
                numbers: list[Decimal] = []
                source_ids: list[str] = []
                for source_record in source_records:
                    number = _to_decimal(source_record.values.get(field_name))
                    if number is None:
                        continue
                    numbers.append(number)
                    source_ids.extend(source_record.field_sources.get(field_name, []))
                if not numbers:
                    continue
                if operation == "average":
                    result = sum(numbers) / Decimal(len(numbers))
                else:
                    result = sum(numbers)
                summary_record.values[field_name] = _format_decimal(result)
                if source_ids:
                    summary_record.field_sources[field_name] = list(dict.fromkeys(source_ids))
                summary_record.notes.append(
                    f"Auto-corrected cross-record {operation} field '{field_name}' from {len(numbers)} source record(s)."
                )


class PythonComputeEngine:
    """Normalize numeric values and compute simple derived fields."""

    def compute(self, records: list[StructuredRecord], task_spec: TaskSpec) -> list[StructuredRecord]:
        for record in records:
            _normalize_numeric_values(record)
            _compute_per_capita_fields(record)
            _compute_rate_fields(record)
            _compute_row_aggregate_fields(record)
            _mark_remaining_missing_required(record)
        _compute_cross_record_summary(records)
        return records
