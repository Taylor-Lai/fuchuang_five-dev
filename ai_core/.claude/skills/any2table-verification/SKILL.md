---
name: any2table-verification
description: 检查输出记录与任务、模板、证据是否一致，并给出风险与返工建议。
version: 0.1.0
tags:
  - any2table
  - verification
  - quality-check
inputs:
  - task_spec
  - template_spec
  - selected_records
  - fill_result
outputs:
  - status
  - issues
  - repair_suggestions
  - reasoning_summary
---

# Purpose
你负责在写回前后检查结果是否满足任务目标，并指出明显风险。

# When To Use
- 记录已经生成，准备写回或已完成写回。
- 需要判断是否缺字段、是否填太多、是否与模板描述冲突。
- 需要为后续返工或反思提供依据。

# Required Output
输出一个 JSON 对象，包含：
- `status`
- `issues`
- `repair_suggestions`
- `reasoning_summary`

# Procedure
1. 检查记录数量是否异常。
2. 检查关键字段是否为空或与约束冲突。
3. 检查输出是否和模板描述或任务范围明显不一致。
4. 若发现问题，给出可执行的返工建议。

# Guardrails
- 不要重写记录，只做检查与建议。
- 风险说明应具体、可执行。
- 若信息不足，明确说明“当前仅做基础校验”。

# References
- 查看 `examples.md`。
- 输出结构参考 `templates/verification_output.json`。
