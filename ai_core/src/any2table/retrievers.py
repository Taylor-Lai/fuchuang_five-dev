"""Retrievers."""

from __future__ import annotations

from any2table.core.models import CanonicalDocument, EvidenceItem, EvidencePack, TaskSpec, TemplateSpec


def _table_row_to_dict(table, row) -> dict[str, object]:
    data: dict[str, object] = {}
    for header, cell in zip(table.headers, row.cells):
        data[header.name] = cell.value
    return data


class RuleRetriever:
    """Collect row-level and paragraph-level evidence from parsed sources."""

    def retrieve(
        self,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        source_docs: list[CanonicalDocument],
    ) -> EvidencePack:
        items: list[EvidenceItem] = []
        for doc in source_docs:
            for table in doc.tables:
                items.append(
                    EvidenceItem(
                        evidence_id=f"{table.table_id}#summary",
                        evidence_type="table",
                        source_doc_id=doc.doc_id,
                        content={
                            "table_id": table.table_id,
                            "name": table.name,
                            "row_count": len(table.rows),
                            "headers": [header.name for header in table.headers],
                        },
                        score=0.4,
                        location=table.location,
                    )
                )
                for row in table.rows[1:]:
                    items.append(
                        EvidenceItem(
                            evidence_id=f"{row.row_id}#row",
                            evidence_type="row",
                            source_doc_id=doc.doc_id,
                            content=_table_row_to_dict(table, row),
                            score=0.7,
                            location=row.cells[0].location if row.cells else table.location,
                        )
                    )
            for block in doc.blocks:
                if block.text:
                    items.append(
                        EvidenceItem(
                            evidence_id=f"{block.block_id}#paragraph",
                            evidence_type="paragraph",
                            source_doc_id=doc.doc_id,
                            content=block.text,
                            score=0.5,
                            location=block.location,
                        )
                    )
        return EvidencePack(
            task_id=task_spec.task_id,
            items=items,
            retrieval_logs=[{"backend": "rule", "source_doc_count": len(source_docs)}],
            coverage={"source_doc_count": len(source_docs), "evidence_count": len(items)},
        )
