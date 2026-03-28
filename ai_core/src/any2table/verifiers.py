"""Verifiers."""

from __future__ import annotations

from any2table.core.models import EvidencePack, FillResult, StructuredRecord, TaskSpec, TemplateSpec, VerificationCheck, VerificationReport


class DefaultVerifier:
    """Basic completeness and evidence presence checks."""

    def verify(
        self,
        task_spec: TaskSpec,
        template_spec: TemplateSpec,
        evidence_pack: EvidencePack,
        records: list[StructuredRecord],
        fill_result: FillResult,
    ) -> VerificationReport:
        checks = [
            VerificationCheck(
                name="evidence_presence",
                status="pass" if evidence_pack.items else "warning",
                message=f"Collected {len(evidence_pack.items)} evidence item(s).",
            ),
            VerificationCheck(
                name="record_generation",
                status="pass" if records else "warning",
                message=f"Generated {len(records)} record(s).",
            ),
            VerificationCheck(
                name="writer_output",
                status="pass" if fill_result.output_path else "warning",
                message="Output document was generated." if fill_result.output_path else "Writer did not generate an output file.",
            ),
        ]
        return VerificationReport(
            task_id=task_spec.task_id,
            status="pass" if fill_result.output_path else "warning",
            summary="Initial read/write pipeline completed.",
            checks=checks,
        )
