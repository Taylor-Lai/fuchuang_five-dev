import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from any2table.candidates.builders import (
    build_agent_candidates_from_skill_result,
    infer_target_entity_level,
)
from any2table.candidates.models import CandidateRecord
from any2table.core.models import (
    CanonicalDocument,
    DocumentBlock,
    FieldSpec,
    FileAsset,
    LocationRef,
    TargetTableSpec,
    TaskSpec,
    TemplateSpec,
)
from any2table.merging import merge_candidates


class CandidateMergerTests(unittest.TestCase):
    def setUp(self) -> None:
        schema = [
            FieldSpec(field_id="f1", field_name="国家/地区", normalized_name="国家/地区", data_type="string", required=True),
            FieldSpec(field_id="f2", field_name="大洲", normalized_name="大洲", data_type="string", required=False),
            FieldSpec(field_id="f3", field_name="人口", normalized_name="人口", data_type="number", required=False),
            FieldSpec(field_id="f4", field_name="病例数", normalized_name="病例数", data_type="number", required=False),
        ]
        self.template_spec = TemplateSpec(
            template_doc_id="template-doc",
            target_tables=[
                TargetTableSpec(
                    target_table_id="target-table-1",
                    logical_name="covid",
                    schema=schema,
                )
            ],
        )
        self.task_spec = TaskSpec(
            task_id="task-1",
            intent="fill_table",
            target_template_id="template-doc",
            target_tables=["target-table-1"],
            target_fields=[field.field_name for field in schema],
        )
        self.source_doc = CanonicalDocument(
            doc_id="source-doc",
            file=FileAsset(
                id="source-doc",
                path="test_data/source.docx",
                name="source.docx",
                ext="docx",
                role="source",
                mime_type=None,
                size=0,
            ),
            doc_type="docx",
            blocks=[
                DocumentBlock(
                    block_id="source-doc#p-1",
                    block_type="paragraph",
                    text="湖北省在该阶段病例数为0。",
                    location=LocationRef(doc_id="source-doc", paragraph_index=1),
                )
            ],
        )

    def test_infer_target_entity_level_prefers_city(self) -> None:
        self.assertEqual(infer_target_entity_level(["国家/地区", "城市", "人口"]), "city")

    def test_agent_candidate_is_marked_as_province_from_docx_note(self) -> None:
        skill_result = {
            "records": [
                {
                    "values": {"国家/地区": "China", "大洲": "Asia", "人口": 57750000, "病例数": 0},
                    "source_paragraph_ids": ["source-doc#p-1"],
                    "confidence": 0.9,
                    "notes": ["湖北省 data used."],
                }
            ]
        }

        candidates = build_agent_candidates_from_skill_result(
            task_spec=self.task_spec,
            template_spec=self.template_spec,
            source_doc=self.source_doc,
            skill_result=skill_result,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].entity_level, "province")
        self.assertEqual(candidates[0].row_identity, {"国家/地区": "China"})
        self.assertTrue(candidates[0].metadata["row_identity_complete"])

    def test_merge_rejects_province_candidate_for_country_template(self) -> None:
        agent_candidate = CandidateRecord(
            candidate_id="agent-1",
            target_table_id="target-table-1",
            row_identity={"国家/地区": "China"},
            values={"国家/地区": "China", "大洲": "Asia", "人口": 57750000, "病例数": 0},
            field_evidence={"国家/地区": ["source-doc#p-1"]},
            confidence=0.9,
            source_strategy="agent",
            entity_level="province",
            notes=["湖北省 data used."],
        )

        result = merge_candidates(
            rule_candidates=[],
            agent_candidates=[agent_candidate],
            target_entity_level="country",
        )

        self.assertEqual(len(result.merged_candidates), 0)
        self.assertEqual(len(result.rejected_candidates), 1)
        self.assertIn("entity level province does not match target level country", result.warnings[0])

    def test_merge_rejects_candidate_missing_required_identity(self) -> None:
        agent_candidate = CandidateRecord(
            candidate_id="agent-2",
            target_table_id="target-table-1",
            row_identity={},
            values={"国家/地区": None, "大洲": "Asia", "人口": 10, "病例数": 1},
            field_evidence={},
            confidence=0.7,
            source_strategy="agent",
            entity_level="unknown",
        )

        result = merge_candidates(
            rule_candidates=[],
            agent_candidates=[agent_candidate],
            target_entity_level="country",
        )

        self.assertEqual(len(result.merged_candidates), 0)
        self.assertEqual(len(result.rejected_candidates), 1)
        self.assertIn("missing required row identity fields: 国家/地区", result.warnings[0])

    def test_merge_combines_candidates_with_same_identity(self) -> None:
        rule_candidate = CandidateRecord(
            candidate_id="rule-1",
            target_table_id="target-table-1",
            row_identity={"国家/地区": "China"},
            values={"国家/地区": "China", "大洲": None, "人口": 1410000000, "病例数": None},
            field_evidence={"国家/地区": ["row-1"], "人口": ["row-1"]},
            confidence=0.7,
            source_strategy="rule",
            entity_level="country",
        )
        agent_candidate = CandidateRecord(
            candidate_id="agent-3",
            target_table_id="target-table-1",
            row_identity={"国家/地区": "China"},
            values={"国家/地区": "China", "大洲": "Asia", "人口": 1400000000, "病例数": 4},
            field_evidence={"大洲": ["source-doc#p-1"], "病例数": ["source-doc#p-1"]},
            confidence=0.9,
            source_strategy="agent",
            entity_level="country",
        )

        result = merge_candidates(
            rule_candidates=[rule_candidate],
            agent_candidates=[agent_candidate],
            target_entity_level="country",
        )

        self.assertEqual(len(result.merged_candidates), 1)
        merged = result.merged_candidates[0]
        self.assertEqual(merged.values["国家/地区"], "China")
        self.assertEqual(merged.values["大洲"], "Asia")
        self.assertEqual(merged.values["人口"], 1400000000)
        self.assertEqual(merged.values["病例数"], 4)
        self.assertEqual(merged.source_strategy, "merged")
        self.assertIn("rule-1", merged.metadata["merged_from"])
        self.assertIn("agent-3", merged.metadata["merged_from"])


if __name__ == "__main__":
    unittest.main()
