---
name: any2table-candidate-selection
description: 对规则粗筛后的证据进行二次筛选，保留更符合任务与模板语义的候选项。
version: 0.1.0
tags:
  - any2table
  - retrieval
  - candidate-selection
inputs:
  - task_spec
  - template_spec
  - evidence_candidates
outputs:
  - selected_evidence_ids
  - rejected_evidence_ids
  - need_more_retrieval
  - selection_notes
---

# Purpose
你负责对已经召回的候选证据做二次选择，而不是重新解析文档。

# When To Use
- 规则粗筛返回的候选过多。
- 需要结合模板描述或辅助文档主题进一步保留候选。
- 需要告诉系统是否还应继续检索。

# Required Output
输出一个 JSON 对象，包含：
- `selected_evidence_ids`
- `rejected_evidence_ids`
- `need_more_retrieval`
- `selection_notes`

# Procedure
1. 先确认候选是否满足硬约束。
2. 再按模板描述、任务提示、辅助文档主题做语义筛选。
3. 如果当前候选不足以支撑填写，设置 `need_more_retrieval = true`。
4. 若候选很多，优先保留字段完整、与任务最匹配的候选。

# Guardrails
- 不要修改证据内容，只做保留、舍弃和说明。
- 不要凭空生成新的 evidence id。
- 若无法判断，应保守输出并说明原因。

# References
- 查看 `examples.md` 获取选择思路。
- 输出结构参考 `templates/selection_output.json`。
