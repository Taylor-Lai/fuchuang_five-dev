"""Verifiers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from any2table.core.models import EvidencePack, FillResult, StructuredRecord, TaskSpec, TemplateSpec, VerificationCheck, VerificationReport


def _status_from_counts(*, fail_count: int = 0, warning_count: int = 0) -> str:
    if fail_count:
        return "fail"
    if warning_count:
        return "warning"
    return "pass"


def _required_fields_by_table(template_spec: TemplateSpec) -> dict[str, list[str]]:
    required: dict[str, list[str]] = {}
    for target_table in template_spec.target_tables:
        required[target_table.target_table_id] = [field.field_name for field in target_table.schema if field.required]
    return required


def _all_fields_by_table(template_spec: TemplateSpec) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for target_table in template_spec.target_tables:
        fields[target_table.target_table_id] = [field.field_name for field in target_table.schema]
    return fields


def _is_empty(value: object) -> bool:
    return value is None or value == "" or value == "未找到"


def _missing_required_fields(records: list[StructuredRecord], template_spec: TemplateSpec) -> list[str]:
    required = _required_fields_by_table(template_spec)
    missing: list[str] = []
    for record in records:
        for field_name in required.get(record.target_table_id, []):
            if _is_empty(record.values.get(field_name)):
                missing.append(f"{record.record_id}:{field_name}")
    return missing


def _missing_evidence_fields(records: list[StructuredRecord], template_spec: TemplateSpec) -> list[str]:
    table_fields = _all_fields_by_table(template_spec)
    missing: list[str] = []
    for record in records:
        for field_name in table_fields.get(record.target_table_id, []):
            value = record.values.get(field_name)
            if _is_empty(value):
                continue
            if not record.field_sources.get(field_name):
                missing.append(f"{record.record_id}:{field_name}")
    return missing


def _low_confidence_records(records: list[StructuredRecord], threshold: float = 0.6) -> list[str]:
    return [record.record_id for record in records if record.confidence < threshold]


def _auto_corrected_records(records: list[StructuredRecord]) -> list[str]:
    corrected: list[str] = []
    for record in records:
        if any("Auto-corrected" in note or note.startswith("Computed ") for note in record.notes):
            corrected.append(record.record_id)
    return corrected


def _field_type_mismatches(records: list[StructuredRecord], template_spec: TemplateSpec) -> list[str]:
    field_types: dict[tuple[str, str], str] = {}
    for target_table in template_spec.target_tables:
        for field in target_table.schema:
            field_types[(target_table.target_table_id, field.field_name)] = field.data_type

    mismatches: list[str] = []
    for record in records:
        for field_name, value in record.values.items():
            if _is_empty(value):
                continue
            data_type = field_types.get((record.target_table_id, field_name), "string")
            if data_type in {"number", "numeric", "float", "int"}:
                try:
                    Decimal(str(value).replace(",", ""))
                except (InvalidOperation, ValueError):
                    mismatches.append(f"{record.record_id}:{field_name}")
            elif data_type in {"string", "text"} and isinstance(value, (dict, list)):
                mismatches.append(f"{record.record_id}:{field_name}")
    return mismatches


def _written_field_count(fill_result: FillResult) -> int:
    return sum(1 for cell in fill_result.written_cells if not _is_empty(cell.value))


class DefaultVerifier:
    """Completeness, evidence traceability, and write-back checks."""

    def verify(
        self,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        evidence_pack: EvidencePack,
        records: list[StructuredRecord],
        fill_result: FillResult,
    ) -> VerificationReport:
        missing_required = _missing_required_fields(records, template_spec)
        missing_evidence = _missing_evidence_fields(records, template_spec)
        low_confidence = _low_confidence_records(records)
        auto_corrected = _auto_corrected_records(records)
        type_mismatches = _field_type_mismatches(records, template_spec)
        expected_tables = {table.target_table_id for table in template_spec.target_tables}
        tables_with_records = {record.target_table_id for record in records}
        empty_tables = sorted(expected_tables - tables_with_records)
        written_non_empty = _written_field_count(fill_result)

        checks = [
            VerificationCheck(
                name="evidence_presence",
                status="pass" if evidence_pack.items else "warning",
                message=f"Collected {len(evidence_pack.items)} evidence item(s).",
            ),
            VerificationCheck(
                name="record_generation",
                status="pass" if records else "fail",
                message=f"Generated {len(records)} record(s).",
            ),
            VerificationCheck(
                name="required_field_completeness",
                status="pass" if not missing_required else "warning",
                message=(
                    "All required fields are filled."
                    if not missing_required
                    else f"{len(missing_required)} required field value(s) are missing."
                ),
                related_ids=missing_required[:20],
            ),
            VerificationCheck(
                name="evidence_traceability",
                status="pass" if not missing_evidence else "warning",
                message=(
                    "All non-empty values have evidence ids."
                    if not missing_evidence
                    else f"{len(missing_evidence)} filled field(s) lack evidence ids."
                ),
                related_ids=missing_evidence[:20],
            ),
            VerificationCheck(
                name="confidence_review",
                status="pass" if not low_confidence else "warning",
                message=(
                    "No low-confidence records detected."
                    if not low_confidence
                    else f"{len(low_confidence)} record(s) are below confidence threshold."
                ),
                related_ids=low_confidence[:20],
            ),
            VerificationCheck(
                name="deterministic_auto_correction",
                status="pass",
                message=(
                    "No deterministic correction was needed."
                    if not auto_corrected
                    else f"{len(auto_corrected)} record(s) include computed or auto-corrected value(s)."
                ),
                related_ids=auto_corrected[:20],
            ),
            VerificationCheck(
                name="field_type_validation",
                status="pass" if not type_mismatches else "warning",
                message=(
                    "All filled values match expected field types."
                    if not type_mismatches
                    else f"{len(type_mismatches)} filled value(s) do not match expected field types."
                ),
                related_ids=type_mismatches[:20],
            ),
            VerificationCheck(
                name="table_coverage",
                status="pass" if not empty_tables else "warning",
                message=(
                    "Every target table has at least one record."
                    if not empty_tables
                    else f"{len(empty_tables)} target table(s) have no generated records."
                ),
                related_ids=empty_tables[:20],
            ),
            VerificationCheck(
                name="writer_output",
                status="pass" if fill_result.output_path and fill_result.written_cells else "warning",
                message=(
                    f"Output document was generated with {len(fill_result.written_cells)} written cell trace(s), "
                    f"{written_non_empty} non-empty."
                    if fill_result.output_path
                    else "Writer did not generate an output file."
                ),
            ),
        ]
        warning_count = sum(1 for check in checks if check.status == "warning")
        fail_count = sum(1 for check in checks if check.status == "fail")
        status = _status_from_counts(fail_count=fail_count, warning_count=warning_count)
        return VerificationReport(
            task_id=task_spec.task_id,
            status=status,
            summary=(
                f"Verification completed: {len(records)} record(s), "
                f"{len(fill_result.written_cells)} cell trace(s), "
                f"{len(missing_required)} missing required field(s), "
                f"{len(missing_evidence)} traceability warning(s), "
                f"{len(auto_corrected)} auto-corrected record(s), "
                f"{len(type_mismatches)} type warning(s)."
            ),
            checks=checks,
            missing_fields=missing_required,
            conflict_records=low_confidence,
        )
