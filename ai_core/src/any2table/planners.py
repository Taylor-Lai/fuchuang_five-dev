"""Task planners."""

from __future__ import annotations

import re

from any2table.core.models import CanonicalDocument, Constraint, TaskSpec, TemplateSpec

DATE_RANGE_PATTERN = re.compile(
    r"(\d{4})[/-年](\d{1,2})[/-月](\d{1,2})[日]?"
    r".{0,20}?"
    r"(\d{4})[/-年](\d{1,2})[/-月](\d{1,2})[日]?"
)
ISO_DATETIME_PATTERN = re.compile(r"(\d{4}-\d{1,2}-\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)")


TASK_POLICY_PATTERNS = {
    "latest": [r"latest", r"最后一天", r"最新", r"取最新", r"取最后", r"截至"],
    "earliest": [r"earliest", r"最早", r"第一天", r"取最早", r"取第一条"],
    "average": [r"average", r"avg", r"平均", r"均值", r"平均值"],
    "all_dates": [r"all\s*dates", r"全部日期", r"所有日期", r"按日期展开", r"逐日", r"每天"],
}


def _extract_request_constraints(user_request_doc: CanonicalDocument, request_text: str) -> list[Constraint]:
    constraints: list[Constraint] = []
    if request_text:
        constraints.append(
            Constraint(
                constraint_id=f"{user_request_doc.doc_id}#request",
                source="user_request",
                kind="request_text",
                field=None,
                operator="contains",
                value=request_text,
            )
        )

    date_range_match = DATE_RANGE_PATTERN.search(request_text)
    if date_range_match:
        y1, m1, d1, y2, m2, d2 = date_range_match.groups()
        constraints.append(
            Constraint(
                constraint_id=f"{user_request_doc.doc_id}#date-range",
                source="user_request",
                kind="date_range",
                field="日期",
                operator="between",
                value={
                    "start": f"{int(y1):04d}-{int(m1):02d}-{int(d1):02d}",
                    "end": f"{int(y2):04d}-{int(m2):02d}-{int(d2):02d}",
                },
            )
        )

    exact_datetime_match = ISO_DATETIME_PATTERN.search(request_text)
    if exact_datetime_match:
        constraints.append(
            Constraint(
                constraint_id=f"{user_request_doc.doc_id}#datetime",
                source="user_request",
                kind="exact_datetime",
                field="监测时间",
                operator="equals",
                value=exact_datetime_match.group(1),
            )
        )

    return constraints


def _infer_task_policy(request_text: str) -> str:
    lowered = request_text.lower()
    for policy in ("all_dates", "latest", "earliest", "average"):
        for pattern in TASK_POLICY_PATTERNS[policy]:
            if re.search(pattern, lowered, re.IGNORECASE):
                return policy
    return "all_dates"


class DefaultTaskPlanner:
    """Translate request text into a minimal task spec."""

    def plan(
        self,
        user_request_doc: CanonicalDocument,
        template_spec: TemplateSpec,
        source_docs: list[CanonicalDocument],
    ) -> TaskSpec:
        request_text = "\n".join(block.text or "" for block in user_request_doc.blocks).strip()
        constraints = _extract_request_constraints(user_request_doc, request_text)
        target_tables = [table.target_table_id for table in template_spec.target_tables]
        target_fields = [field.field_name for table in template_spec.target_tables for field in table.schema]
        return TaskSpec(
            task_id=f"{user_request_doc.doc_id}#task",
            intent="fill_table",
            target_template_id=template_spec.template_doc_id,
            target_tables=target_tables,
            constraints=constraints,
            target_fields=target_fields,
            record_granularity="row",
            allow_inference=False,
            allow_empty_output=False,
            error_policy="strict",
            task_policy=_infer_task_policy(request_text),
        )
