---
name: any2table-task-understanding
description: 理解用户填表任务，抽取任务意图、时间范围、实体约束和输出提示。
version: 0.1.0
tags:
  - any2table
  - task-understanding
  - table-filling
inputs:
  - user_request_doc
  - template_spec
  - source_doc_summaries
outputs:
  - intent
  - constraints
  - task_hints
  - reasoning_summary
---

# Purpose
你负责把用户要求转成结构化任务信息，供编排层、检索层和记录生成层使用。

# When To Use
- 用户提供了自然语言填表要求。
- 系统需要从要求中抽取硬约束与软提示。
- 后续检索或推理需要明确时间、实体、范围条件。

# Required Output
输出一个 JSON 对象，至少包含以下字段：
- `intent`
- `constraints`
- `task_hints`
- `reasoning_summary`

# Procedure
1. 先识别用户的主任务是不是填表。
2. 抽取明确硬约束，如日期区间、国家、城市、时间点、表格范围。
3. 抽取软提示，如“结合辅助文档主题”“优先填写与描述一致的数据”。
4. 若信息不足，不编造硬约束，把不确定性写进 `reasoning_summary`。
5. 输出严格 JSON，便于程序消费。

# Guardrails
- 不要凭空补充用户没有说过的硬条件。
- 硬约束和软提示要分开表达。
- 若要求不完整，宁可保守，也不要臆造。

# References
- 查看 `examples.md` 获取正反例。
- 输出结构参考 `templates/task_output.json`。
