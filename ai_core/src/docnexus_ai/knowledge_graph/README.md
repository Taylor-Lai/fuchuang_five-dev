# Knowledge Graph Sidecar

这是智汇文枢 AI 模块预留的实验性知识图谱壳子。

当前状态：

- 不接入模块二信息抽取主流程
- 不接入模块三自动填表主流程
- 不影响 RAG、Agent Skill、规则抽取和写回结果
- 可从结构化抽取结果生成轻量实体-关系草图
- 可导出 JSON，供后续展示、调试或 GraphRAG 扩展使用

设计用途：

- 实体消歧：同一人名、机构名、城市名的归并
- 关系约束：字段之间的来源关系、上下文关系
- 证据追踪：把字段值、证据片段、文档块组织成图
- 后续 GraphRAG：作为检索增强的图结构补充

示例：

```python
from docnexus_ai.knowledge_graph import KnowledgeGraphBuilder, export_graph_json

result = {
    "项目名称": "智汇文枢",
    "负责人": "张三",
    "_meta": {
        "evidence": {
            "负责人": {"chunk_id": 0, "snippet": "项目负责人为张三"}
        }
    }
}

graph = KnowledgeGraphBuilder().from_extraction_result(result)
json_text = export_graph_json(graph)
```
