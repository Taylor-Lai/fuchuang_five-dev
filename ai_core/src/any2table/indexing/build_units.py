"""Build retrieval-ready units from canonical documents."""

from __future__ import annotations

from any2table.core.models import CanonicalDocument


def _location_payload(location) -> dict[str, object] | None:
    return None if location is None else location.to_dict()



def _infer_entity_level(doc: CanonicalDocument, payload: dict[str, object] | None, text: str | None) -> str:
    if payload:
        keys = set(payload)
        if "国家/地区" in keys:
            return "country"
        if "城市" in keys:
            return "city"
        if any("省" in str(value) or "自治区" in str(value) for value in payload.values() if value is not None):
            return "province"
    content = text or ""
    if any(token in content for token in ("省", "自治区", "直辖市")):
        return "province"
    if "市" in content:
        return "city"
    if doc.doc_type == "xlsx":
        return "row"
    return "unknown"



def _row_text(payload: dict[str, object]) -> str:
    parts = [f"{key}={value}" for key, value in payload.items() if value not in (None, "")]
    return ", ".join(parts)



def build_retrieval_units(documents: list[CanonicalDocument]) -> dict[str, list[dict[str, object]]]:
    units_by_doc: dict[str, list[dict[str, object]]] = {}
    for doc in documents:
        units: list[dict[str, object]] = []
        for block in doc.blocks:
            text = (block.text or "").strip()
            if not text:
                continue
            units.append(
                {
                    "unit_id": f"{block.block_id}#paragraph",
                    "doc_id": doc.doc_id,
                    "source_type": doc.doc_type,
                    "unit_type": "paragraph",
                    "text": text,
                    "structured_payload": None,
                    "location": _location_payload(block.location),
                    "metadata": {
                        "block_type": block.block_type,
                        "entity_level": _infer_entity_level(doc, None, text),
                        **block.attrs,
                    },
                }
            )
        for table in doc.tables:
            units.append(
                {
                    "unit_id": f"{table.table_id}#summary",
                    "doc_id": doc.doc_id,
                    "source_type": doc.doc_type,
                    "unit_type": "table_summary",
                    "text": f"table={table.name or table.table_id}, headers={','.join(header.name for header in table.headers)}, rows={max(len(table.rows) - 1, 0)}",
                    "structured_payload": {
                        "table_id": table.table_id,
                        "table_name": table.name,
                        "headers": [header.name for header in table.headers],
                        "row_count": max(len(table.rows) - 1, 0),
                    },
                    "location": _location_payload(table.location),
                    "metadata": {
                        "table_type": table.table_type,
                        "entity_level": "table",
                    },
                }
            )
            for row in table.rows[1:]:
                payload: dict[str, object] = {}
                for header, cell in zip(table.headers, row.cells):
                    payload[header.name] = cell.value
                units.append(
                    {
                        "unit_id": f"{row.row_id}#row",
                        "doc_id": doc.doc_id,
                        "source_type": doc.doc_type,
                        "unit_type": "row",
                        "text": _row_text(payload),
                        "structured_payload": payload,
                        "location": _location_payload(row.cells[0].location if row.cells else table.location),
                        "metadata": {
                            "table_id": table.table_id,
                            "entity_level": _infer_entity_level(doc, payload, None),
                        },
                    }
                )
        units_by_doc[doc.doc_id] = units
    return units_by_doc
