import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from any2table.compute import PythonComputeEngine
from any2table.core.models import (
    EvidenceItem,
    EvidencePack,
    FieldSpec,
    FillResult,
    StructuredRecord,
    TargetTableSpec,
    TaskSpec,
    TemplateSpec,
)
from any2table.verifiers import DefaultVerifier


class ComputeEngineTests(unittest.TestCase):
    def test_normalizes_chinese_units(self) -> None:
        record = StructuredRecord(
            record_id="r1",
            target_table_id="t1",
            values={"人口": "1.2亿", "病例数": "3,000例", "城市": "测试市"},
        )

        out = PythonComputeEngine().compute([record], TaskSpec("task", "fill_table", "template"))

        self.assertEqual(out[0].values["人口"], 120000000)
        self.assertEqual(out[0].values["病例数"], 3000)
        self.assertTrue(any("Normalized numeric field" in note for note in out[0].notes))

    def test_computes_missing_per_capita_gdp(self) -> None:
        record = StructuredRecord(
            record_id="r1",
            target_table_id="t1",
            values={"GDP": "120亿元", "人口": 1000000, "人均GDP": None},
            field_sources={"GDP": ["e1"], "人口": ["e2"]},
        )

        out = PythonComputeEngine().compute([record], TaskSpec("task", "fill_table", "template"))

        self.assertEqual(out[0].values["人均GDP"], 12000)
        self.assertEqual(out[0].field_sources["人均GDP"], ["e1", "e2"])

    def test_auto_corrects_missing_row_total(self) -> None:
        record = StructuredRecord(
            record_id="r1",
            target_table_id="t1",
            values={"一月": 10, "二月": 20, "总计": None},
            field_sources={"一月": ["e1"], "二月": ["e2"]},
        )

        out = PythonComputeEngine().compute([record], TaskSpec("task", "fill_table", "template"))

        self.assertEqual(out[0].values["总计"], 30)
        self.assertEqual(out[0].field_sources["总计"], ["e1", "e2"])
        self.assertTrue(any("Auto-corrected missing aggregate field" in note for note in out[0].notes))

    def test_auto_corrects_cross_record_summary_row(self) -> None:
        records = [
            StructuredRecord("r1", "t1", values={"城市": "A", "GDP": 10}, field_sources={"GDP": ["e1"]}),
            StructuredRecord("r2", "t1", values={"城市": "B", "GDP": 20}, field_sources={"GDP": ["e2"]}),
            StructuredRecord("r3", "t1", values={"城市": "合计", "GDP": None}),
        ]

        out = PythonComputeEngine().compute(records, TaskSpec("task", "fill_table", "template"))

        self.assertEqual(out[2].values["GDP"], 30)
        self.assertEqual(out[2].field_sources["GDP"], ["e1", "e2"])
        self.assertTrue(any("cross-record sum" in note for note in out[2].notes))


class VerifierTests(unittest.TestCase):
    def test_reports_missing_required_and_evidence(self) -> None:
        template_spec = TemplateSpec(
            template_doc_id="template",
            target_tables=[
                TargetTableSpec(
                    target_table_id="t1",
                    logical_name="table",
                    schema=[
                        FieldSpec("f1", "城市", "城市", "string", True),
                        FieldSpec("f2", "GDP", "gdp", "number", True),
                    ],
                )
            ],
        )
        task_spec = TaskSpec("task", "fill_table", "template")
        records = [
            StructuredRecord(
                record_id="r1",
                target_table_id="t1",
                values={"城市": "北京", "GDP": None},
                field_sources={},
                confidence=0.5,
            )
        ]
        report = DefaultVerifier().verify(
            task_spec=task_spec,
            template_spec=template_spec,
            evidence_pack=EvidencePack("task", items=[EvidenceItem("e1", "paragraph", "doc", "北京 GDP 数据")]),
            records=records,
            fill_result=FillResult("template", "out.xlsx"),
        )

        self.assertEqual(report.status, "warning")
        self.assertIn("r1:GDP", report.missing_fields)
        self.assertIn("r1", report.conflict_records)
        checks = {check.name: check for check in report.checks}
        self.assertEqual(checks["required_field_completeness"].status, "warning")
        self.assertEqual(checks["evidence_traceability"].status, "warning")

    def test_reports_auto_corrected_records(self) -> None:
        template_spec = TemplateSpec(
            template_doc_id="template",
            target_tables=[
                TargetTableSpec(
                    target_table_id="t1",
                    logical_name="table",
                    schema=[
                        FieldSpec("f1", "一月", "一月", "number", False),
                        FieldSpec("f2", "二月", "二月", "number", False),
                        FieldSpec("f3", "总计", "总计", "number", False),
                    ],
                )
            ],
        )
        records = [
            StructuredRecord(
                record_id="r1",
                target_table_id="t1",
                values={"一月": 10, "二月": 20, "总计": 30},
                field_sources={"一月": ["e1"], "二月": ["e2"], "总计": ["e1", "e2"]},
                notes=["Auto-corrected missing aggregate field '总计' using row-level sum over 2 numeric field(s)."],
            )
        ]

        report = DefaultVerifier().verify(
            task_spec=TaskSpec("task", "fill_table", "template"),
            template_spec=template_spec,
            evidence_pack=EvidencePack("task", items=[EvidenceItem("e1", "row", "doc", {"一月": 10})]),
            records=records,
            fill_result=FillResult("template", "out.xlsx"),
        )

        checks = {check.name: check for check in report.checks}
        self.assertEqual(checks["deterministic_auto_correction"].related_ids, ["r1"])

    def test_reports_field_type_mismatch(self) -> None:
        template_spec = TemplateSpec(
            template_doc_id="template",
            target_tables=[
                TargetTableSpec(
                    target_table_id="t1",
                    logical_name="table",
                    schema=[FieldSpec("f1", "GDP", "gdp", "number", False)],
                )
            ],
        )
        records = [
            StructuredRecord(
                record_id="r1",
                target_table_id="t1",
                values={"GDP": "不是数字"},
                field_sources={"GDP": ["e1"]},
            )
        ]

        report = DefaultVerifier().verify(
            task_spec=TaskSpec("task", "fill_table", "template"),
            template_spec=template_spec,
            evidence_pack=EvidencePack("task", items=[EvidenceItem("e1", "row", "doc", {"GDP": "不是数字"})]),
            records=records,
            fill_result=FillResult("template", "out.xlsx"),
        )

        checks = {check.name: check for check in report.checks}
        self.assertEqual(checks["field_type_validation"].status, "warning")
        self.assertEqual(checks["field_type_validation"].related_ids, ["r1:GDP"])


if __name__ == "__main__":
    unittest.main()
