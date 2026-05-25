import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from docnexus_ai.knowledge_graph import KnowledgeGraphBuilder, export_graph_json


class KnowledgeGraphSidecarTests(unittest.TestCase):
    def test_builds_graph_from_extraction_result_without_main_pipeline_flag(self) -> None:
        result = {
            "项目名称": "智汇文枢",
            "负责人": "张三",
            "_meta": {
                "evidence": {
                    "负责人": {"chunk_id": 0, "snippet": "项目负责人为张三"}
                }
            },
        }

        graph = KnowledgeGraphBuilder().from_extraction_result(result)

        self.assertFalse(graph.metadata["connected_to_main_pipeline"])
        self.assertEqual(graph.metadata["status"], "experimental_sidecar")
        self.assertGreaterEqual(len(graph.entities), 3)
        self.assertTrue(any(relation.relation_type == "has_field:负责人" for relation in graph.relations))

    def test_export_graph_json_returns_valid_json(self) -> None:
        graph = KnowledgeGraphBuilder().from_text_units([
            {"id": "u1", "text": "第一段"},
            {"id": "u2", "text": "第二段"},
        ])

        payload = json.loads(export_graph_json(graph))

        self.assertEqual(payload["metadata"]["connected_to_main_pipeline"], False)
        self.assertEqual(len(payload["entities"]), 2)
        self.assertEqual(payload["relations"][0]["relation_type"], "next_text_unit")


if __name__ == "__main__":
    unittest.main()
