import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from docnexus_ai.document_operations import FormatAction, build_rule_based_plan
from docnexus_ai.information_extraction import merge_chunk_extractions


class DocumentOperationModelTests(unittest.TestCase):
    def test_format_action_supports_non_format_operations(self) -> None:
        action = FormatAction(
            operation="replace",
            target_paragraph_index=-1,
            target_text="旧文本",
            content="新文本",
        )

        self.assertEqual(action.operation, "replace")
        self.assertEqual(action.target_text, "旧文本")
        self.assertEqual(action.content, "新文本")

    def test_rule_plan_splits_complex_command(self) -> None:
        plan = build_rule_based_plan("把第一段加粗并设为红色，然后将“旧标题”替换为“新标题”，最后添加目录")

        operations = [action.operation for action in plan.actions]
        self.assertIn("format", operations)
        self.assertIn("replace", operations)
        self.assertIn("structure", operations)
        self.assertEqual(plan.actions[0].target_paragraph_index, 0)
        self.assertEqual(plan.actions[0].color_hex, "#FF0000")

    def test_rule_plan_inherits_target_for_split_style_command(self) -> None:
        plan = build_rule_based_plan("把第一段加粗并且设为红色")

        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].operation, "format")
        self.assertEqual(plan.actions[0].target_paragraph_index, 0)
        self.assertTrue(plan.actions[0].bold)
        self.assertEqual(plan.actions[0].color_hex, "#FF0000")


class InformationExtractionMetadataTests(unittest.TestCase):
    def test_merge_outputs_normalized_values_and_confidence(self) -> None:
        chunks = [{"chunk_id": 0, "start": 0, "end": 30, "text": "项目日期为2026年5月26日，预算100万元。"}]
        result = merge_chunk_extractions(
            [{"项目日期": "2026年5月26日", "预算": "100万元"}],
            chunks,
            ["项目日期", "预算"],
            chunks[0]["text"],
        )

        self.assertEqual(result["_meta"]["normalized"]["项目日期"], "2026-05-26")
        self.assertEqual(result["_meta"]["normalized"]["预算"], 100)
        self.assertGreaterEqual(result["_meta"]["confidence"]["项目日期"], 0.7)
        self.assertEqual(result["_meta"]["validation"]["项目日期"]["status"], "pass")
        self.assertEqual(result["_meta"]["validation"]["预算"]["expected_type"], "number")
        self.assertEqual(result["_meta"]["candidates"]["预算"], ["100万元"])

    def test_conflict_lowers_confidence(self) -> None:
        chunks = [
            {"chunk_id": 0, "start": 0, "end": 10, "text": "负责人张三"},
            {"chunk_id": 1, "start": 10, "end": 20, "text": "负责人李四"},
        ]
        result = merge_chunk_extractions(
            [{"负责人": "张三"}, {"负责人": "李四"}],
            chunks,
            ["负责人"],
            "负责人张三负责人李四",
        )

        self.assertEqual(result["负责人"], "张三")
        self.assertEqual(result["_meta"]["conflicts"]["负责人"], ["张三", "李四"])
        self.assertEqual(result["_meta"]["confidence"]["负责人"], 0.55)
        self.assertEqual(result["_meta"]["validation"]["负责人"]["status"], "conflict")


if __name__ == "__main__":
    unittest.main()
