"""Compute engines."""

from __future__ import annotations

from any2table.core.models import StructuredRecord, TaskSpec


class PythonComputeEngine:
    """Reserved for deterministic calculations and value normalization."""

    def compute(self, records: list[StructuredRecord], task_spec: TaskSpec) -> list[StructuredRecord]:
        return records
