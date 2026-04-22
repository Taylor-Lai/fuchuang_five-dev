"""Core data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


class DictSerializable:
    """Simple mixin for JSON-friendly serialization."""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class FileAsset(DictSerializable):
    id: str
    path: str
    name: str
    ext: str
    role: str
    mime_type: str | None
    size: int | None


@dataclass(slots=True)
class LocationRef(DictSerializable):
    doc_id: str
    page: int | None = None
    sheet: str | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    row_index: int | None = None
    col_index: int | None = None


@dataclass(slots=True)
class DocumentBlock(DictSerializable):
    block_id: str
    block_type: str
    text: str | None
    location: LocationRef
    attrs: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class TableHeader(DictSerializable):
    header_id: str
    name: str
    normalized_name: str
    col_index: int


@dataclass(slots=True)
class TableCell(DictSerializable):
    row_index: int
    col_index: int
    value: object = None
    raw_value: object = None
    normalized_value: object = None
    location: LocationRef | None = None


@dataclass(slots=True)
class TableRow(DictSerializable):
    row_id: str
    row_index: int
    cells: list[TableCell] = field(default_factory=list)


@dataclass(slots=True)
class CanonicalTable(DictSerializable):
    table_id: str
    source_doc_id: str
    table_type: str
    name: str | None
    headers: list[TableHeader] = field(default_factory=list)
    rows: list[TableRow] = field(default_factory=list)
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)
    location: LocationRef | None = None


@dataclass(slots=True)
class TextSpan(DictSerializable):
    span_id: str
    text: str
    source_doc_id: str
    source_block_id: str
    location: LocationRef


@dataclass(slots=True)
class CanonicalDocument(DictSerializable):
    doc_id: str
    file: FileAsset
    doc_type: str
    metadata: dict[str, object] = field(default_factory=dict)
    blocks: list[DocumentBlock] = field(default_factory=list)
    tables: list[CanonicalTable] = field(default_factory=list)
    text_index: list[TextSpan] = field(default_factory=list)


@dataclass(slots=True)
class FieldSpec(DictSerializable):
    field_id: str
    field_name: str
    normalized_name: str
    data_type: str
    required: bool


@dataclass(slots=True)
class Constraint(DictSerializable):
    constraint_id: str
    source: str
    kind: str
    field: str | None
    operator: str
    value: object


@dataclass(slots=True)
class TargetTableSpec(DictSerializable):
    target_table_id: str
    logical_name: str | None
    schema: list[FieldSpec] = field(default_factory=list)
    description: str | None = None
    local_constraints: list[Constraint] = field(default_factory=list)
    capacity: int | None = None
    supports_row_insert: bool = True
    anchor: LocationRef | None = None


@dataclass(slots=True)
class TemplateSpec(DictSerializable):
    template_doc_id: str
    target_tables: list[TargetTableSpec] = field(default_factory=list)
    global_constraints: list[Constraint] = field(default_factory=list)
    write_mode: str = "mixed"


@dataclass(slots=True)
class TaskSpec(DictSerializable):
    task_id: str
    intent: str
    target_template_id: str
    target_tables: list[str] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    target_fields: list[str] = field(default_factory=list)
    record_granularity: str = "row"
    allow_inference: bool = False
    allow_empty_output: bool = False
    error_policy: str = "strict"
    task_policy: str = "all_dates"


@dataclass(slots=True)
class EvidenceItem(DictSerializable):
    evidence_id: str
    evidence_type: str
    source_doc_id: str
    content: dict[str, object] | str
    matched_fields: list[str] = field(default_factory=list)
    score: float = 0.0
    location: LocationRef | None = None


@dataclass(slots=True)
class EvidencePack(DictSerializable):
    task_id: str
    items: list[EvidenceItem] = field(default_factory=list)
    retrieval_logs: list[dict[str, object]] = field(default_factory=list)
    coverage: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class StructuredRecord(DictSerializable):
    record_id: str
    target_table_id: str
    values: dict[str, object] = field(default_factory=dict)
    field_sources: dict[str, list[str]] = field(default_factory=dict)
    confidence: float = 0.0
    status: str = "ready"
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CellWriteTrace(DictSerializable):
    target_table_id: str
    row_index: int
    col_index: int
    field_name: str
    value: object
    record_id: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FillResult(DictSerializable):
    output_doc_id: str
    output_path: str
    written_cells: list[CellWriteTrace] = field(default_factory=list)
    inserted_rows: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VerificationCheck(DictSerializable):
    name: str
    status: str
    message: str
    related_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VerificationReport(DictSerializable):
    task_id: str
    status: str
    summary: str
    checks: list[VerificationCheck] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    conflict_records: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FillRunResult(DictSerializable):
    fill_result: FillResult
    verification_report: VerificationReport
    debug: dict[str, object] = field(default_factory=dict)
