from __future__ import annotations

import unittest

from any2table.core.models import Constraint, EvidenceItem, EvidencePack, FieldSpec, TaskSpec, TemplateSpec, TargetTableSpec
from any2table.rag import HybridRagBackend


class HybridRagBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = HybridRagBackend()
        self.task_spec = TaskSpec(
            task_id="task-1",
            intent="fill_table",
            target_template_id="template-1",
            target_fields=["\u56fd\u5bb6/\u5730\u533a", "\u75c5\u4f8b\u6570", "\u65e5\u671f"],
            constraints=[
                Constraint(
                    constraint_id="req-1",
                    source="user_request",
                    kind="request_text",
                    field=None,
                    operator="contains",
                    value="\u8bf7\u586b\u5199\u4e2d\u56fd 2020\u5e747\u67081\u65e5 \u7684\u75c5\u4f8b\u6570\u3002",
                ),
                Constraint(
                    constraint_id="date-1",
                    source="user_request",
                    kind="exact_datetime",
                    field="\u65e5\u671f",
                    operator="=",
                    value="2020-07-01 00:00:00",
                ),
                Constraint(
                    constraint_id="entity-1",
                    source="user_request",
                    kind="entity",
                    field="\u56fd\u5bb6/\u5730\u533a",
                    operator="=",
                    value="China",
                ),
            ],
            allow_inference=True,
        )
        self.template_spec = TemplateSpec(
            template_doc_id="template-doc",
            target_tables=[
                TargetTableSpec(
                    target_table_id="table-1",
                    logical_name="COVID data",
                    schema=[
                        FieldSpec("f1", "\u56fd\u5bb6/\u5730\u533a", "\u56fd\u5bb6\u5730\u533a", "string", True),
                        FieldSpec("f2", "\u75c5\u4f8b\u6570", "\u75c5\u4f8b\u6570", "number", True),
                        FieldSpec("f3", "\u65e5\u671f", "\u65e5\u671f", "date", True),
                    ],
                    description="\u6309\u56fd\u5bb6\u4e0e\u65e5\u671f\u586b\u5199\u75c5\u4f8b\u6570",
                )
            ],
        )
        self.source_docs = []
        self.evidence_pack = EvidencePack(
            task_id="task-1",
            items=[
                EvidenceItem(
                    evidence_id="row-china-0701",
                    evidence_type="row",
                    source_doc_id="doc-1",
                    content={"\u56fd\u5bb6/\u5730\u533a": "China", "\u75c5\u4f8b\u6570": 7, "\u65e5\u671f": "2020-07-01"},
                ),
                EvidenceItem(
                    evidence_id="row-italy-0701",
                    evidence_type="row",
                    source_doc_id="doc-1",
                    content={"\u56fd\u5bb6/\u5730\u533a": "Italy", "\u75c5\u4f8b\u6570": 50, "\u65e5\u671f": "2020-07-01"},
                ),
                EvidenceItem(
                    evidence_id="paragraph-china",
                    evidence_type="paragraph",
                    source_doc_id="doc-2",
                    content="2020\u5e747\u67081\u65e5 China reported 7 new confirmed cases.",
                ),
            ],
        )

    def test_direct_route_keeps_pack_unchanged(self) -> None:
        result = self.backend.run(
            route="direct",
            task_spec=self.task_spec,
            template_spec=self.template_spec,
            source_docs=self.source_docs,
            evidence_pack=self.evidence_pack,
        )

        self.assertFalse(result.applied)
        self.assertEqual("hybrid", result.used_backend)
        self.assertIs(result.evidence_pack, self.evidence_pack)
        self.assertIn("query_terms", result.query_summary)
        self.assertEqual([], result.selected_unit_ids)

    def test_rag_route_reranks_with_schema_grounding(self) -> None:
        result = self.backend.run(
            route="rag",
            task_spec=self.task_spec,
            template_spec=self.template_spec,
            source_docs=self.source_docs,
            evidence_pack=self.evidence_pack,
        )

        self.assertTrue(result.applied)
        self.assertEqual("hybrid", result.used_backend)
        self.assertIsNot(result.evidence_pack, self.evidence_pack)
        self.assertGreater(len(result.selected_unit_ids), 0)
        self.assertEqual("row-china-0701", result.evidence_pack.items[0].evidence_id)
        self.assertIn("\u56fd\u5bb6/\u5730\u533a", result.field_evidence_map)
        self.assertIn("row-china-0701", result.field_evidence_map["\u56fd\u5bb6/\u5730\u533a"])
        self.assertEqual("hybrid", result.evidence_pack.coverage["rag_backend"])


if __name__ == "__main__":
    unittest.main()
