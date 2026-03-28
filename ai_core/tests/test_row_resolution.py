import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from any2table.core.models import Constraint, EvidenceItem, EvidencePack, FieldSpec, TargetTableSpec, TaskSpec
from any2table.extractors import _extract_records_from_paragraph_evidence, _extract_records_from_row_evidence


class RowResolutionTests(unittest.TestCase):
    def test_default_all_dates_without_time_field_appends_date_to_identity(self) -> None:
        target_table = TargetTableSpec(
            target_table_id="target-table-1",
            logical_name="covid",
            schema=[
                FieldSpec(field_id="f1", field_name="国家/地区", normalized_name="国家/地区", data_type="string", required=True),
                FieldSpec(field_id="f2", field_name="大洲", normalized_name="大洲", data_type="string", required=False),
                FieldSpec(field_id="f3", field_name="病例数", normalized_name="病例数", data_type="number", required=False),
            ],
        )
        task_spec = TaskSpec(
            task_id="task-1",
            intent="fill_table",
            target_template_id="template-1",
            target_tables=["target-table-1"],
            target_fields=["国家/地区", "大洲", "病例数"],
            constraints=[
                Constraint(
                    constraint_id="c1",
                    source="user_request",
                    kind="date_range",
                    field="日期",
                    operator="between",
                    value={"start": "2020-07-01", "end": "2020-08-31"},
                )
            ],
            task_policy="all_dates",
        )
        evidence_pack = EvidencePack(
            task_id="task-1",
            items=[
                EvidenceItem(
                    evidence_id="row-1",
                    evidence_type="row",
                    source_doc_id="source-1",
                    content={"国家/地区": "Albania", "大洲": "Europe", "日期": "2020-07-01", "病例数": 2580},
                ),
                EvidenceItem(
                    evidence_id="row-2",
                    evidence_type="row",
                    source_doc_id="source-1",
                    content={"国家/地区": "Albania", "大洲": "Europe", "日期": "2020-08-31", "病例数": 9513},
                ),
            ],
        )

        records = _extract_records_from_row_evidence(target_table, task_spec, evidence_pack)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].values["国家/地区"], "Albania（2020/7/1）")
        self.assertEqual(records[1].values["国家/地区"], "Albania（2020/8/31）")

    def test_latest_policy_without_time_field_uses_latest_row_per_identity(self) -> None:
        target_table = TargetTableSpec(
            target_table_id="target-table-1",
            logical_name="covid",
            schema=[
                FieldSpec(field_id="f1", field_name="国家/地区", normalized_name="国家/地区", data_type="string", required=True),
                FieldSpec(field_id="f2", field_name="大洲", normalized_name="大洲", data_type="string", required=False),
                FieldSpec(field_id="f3", field_name="病例数", normalized_name="病例数", data_type="number", required=False),
            ],
        )
        task_spec = TaskSpec(
            task_id="task-1",
            intent="fill_table",
            target_template_id="template-1",
            target_tables=["target-table-1"],
            target_fields=["国家/地区", "大洲", "病例数"],
            constraints=[
                Constraint(
                    constraint_id="c1",
                    source="user_request",
                    kind="date_range",
                    field="日期",
                    operator="between",
                    value={"start": "2020-07-01", "end": "2020-08-31"},
                )
            ],
            task_policy="latest",
        )
        evidence_pack = EvidencePack(
            task_id="task-1",
            items=[
                EvidenceItem(
                    evidence_id="row-1",
                    evidence_type="row",
                    source_doc_id="source-1",
                    content={"国家/地区": "Albania", "大洲": "Europe", "日期": "2020-07-01", "病例数": 2580},
                ),
                EvidenceItem(
                    evidence_id="row-2",
                    evidence_type="row",
                    source_doc_id="source-1",
                    content={"国家/地区": "Albania", "大洲": "Europe", "日期": "2020-08-31", "病例数": 9513},
                ),
                EvidenceItem(
                    evidence_id="row-3",
                    evidence_type="row",
                    source_doc_id="source-1",
                    content={"国家/地区": "Ireland", "大洲": "Europe", "日期": "2020-08-31", "病例数": 28811},
                ),
            ],
        )

        records = _extract_records_from_row_evidence(target_table, task_spec, evidence_pack)

        self.assertEqual(len(records), 2)
        values_by_country = {record.values["国家/地区"]: record.values for record in records}
        self.assertEqual(values_by_country["Albania"]["病例数"], 9513)
        self.assertEqual(values_by_country["Ireland"]["病例数"], 28811)

    def test_date_range_with_time_field_keeps_multiple_rows(self) -> None:
        target_table = TargetTableSpec(
            target_table_id="target-table-1",
            logical_name="daily-table",
            schema=[
                FieldSpec(field_id="f1", field_name="国家/地区", normalized_name="国家/地区", data_type="string", required=True),
                FieldSpec(field_id="f2", field_name="日期", normalized_name="日期", data_type="string", required=True),
                FieldSpec(field_id="f3", field_name="病例数", normalized_name="病例数", data_type="number", required=False),
            ],
        )
        task_spec = TaskSpec(
            task_id="task-1",
            intent="fill_table",
            target_template_id="template-1",
            target_tables=["target-table-1"],
            target_fields=["国家/地区", "日期", "病例数"],
            constraints=[
                Constraint(
                    constraint_id="c1",
                    source="user_request",
                    kind="date_range",
                    field="日期",
                    operator="between",
                    value={"start": "2020-07-01", "end": "2020-08-31"},
                )
            ],
            task_policy="all_dates",
        )
        evidence_pack = EvidencePack(
            task_id="task-1",
            items=[
                EvidenceItem(
                    evidence_id="row-1",
                    evidence_type="row",
                    source_doc_id="source-1",
                    content={"国家/地区": "Albania", "日期": "2020-07-01", "病例数": 2580},
                ),
                EvidenceItem(
                    evidence_id="row-2",
                    evidence_type="row",
                    source_doc_id="source-1",
                    content={"国家/地区": "Albania", "日期": "2020-08-31", "病例数": 9513},
                ),
            ],
        )

        records = _extract_records_from_row_evidence(target_table, task_spec, evidence_pack)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].values["日期"], "2020-07-01")
        self.assertEqual(records[1].values["日期"], "2020-08-31")

    def test_covid_docx_schema_extraction_builds_country_record(self) -> None:
        target_table = TargetTableSpec(
            target_table_id="target-table-1",
            logical_name="covid",
            schema=[
                FieldSpec(field_id="f1", field_name="国家/地区", normalized_name="国家/地区", data_type="string", required=True),
                FieldSpec(field_id="f2", field_name="大洲", normalized_name="大洲", data_type="string", required=False),
                FieldSpec(field_id="f3", field_name="人均GDP", normalized_name="人均GDP", data_type="number", required=False),
                FieldSpec(field_id="f4", field_name="人口", normalized_name="人口", data_type="number", required=False),
                FieldSpec(field_id="f5", field_name="每日检测数", normalized_name="每日检测数", data_type="number", required=False),
                FieldSpec(field_id="f6", field_name="病例数", normalized_name="病例数", data_type="number", required=False),
            ],
        )
        task_spec = TaskSpec(
            task_id="task-1",
            intent="fill_table",
            target_template_id="template-1",
            target_tables=["target-table-1"],
            target_fields=["国家/地区", "大洲", "人均GDP", "人口", "每日检测数", "病例数"],
            task_policy="all_dates",
        )
        evidence_pack = EvidencePack(
            task_id="task-1",
            items=[
                EvidenceItem("p0", "paragraph", "docx-1", "2020 年 7 月 27 日中国各省新冠疫情全景纪实"),
                EvidenceItem("p1", "paragraph", "docx-1", "Asia（亚洲）"),
                EvidenceItem("p2", "paragraph", "docx-1", "当日全国新增确诊病例 68 例。"),
                EvidenceItem("p3", "paragraph", "docx-1", "湖北省"),
                EvidenceItem("p4", "paragraph", "docx-1", "常住人口约 5775 万人，人均 GDP 约 7.3 万元，当日核酸检测量约 12.6 万份。"),
                EvidenceItem("p5", "paragraph", "docx-1", "广东省"),
                EvidenceItem("p6", "paragraph", "docx-1", "常住人口约 1.26 亿，人均 GDP 约 9.6 万元，当日核酸检测量约 38.2 万份。"),
            ],
        )

        records = _extract_records_from_paragraph_evidence(target_table, task_spec, evidence_pack)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.values["国家/地区"], "China（2020/7/27）")
        self.assertEqual(record.values["大洲"], "Asia")
        self.assertEqual(record.values["病例数"], 68)
        self.assertTrue(record.values["人口"])
        self.assertTrue(any("Synthesized country-level record" in note for note in record.notes))


if __name__ == "__main__":
    unittest.main()
