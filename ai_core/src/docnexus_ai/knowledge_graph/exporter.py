"""KG export helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .models import KnowledgeGraph


def export_graph_json(graph: KnowledgeGraph, output_path: str | Path | None = None) -> str:
    payload = json.dumps(graph.to_dict(), ensure_ascii=False, indent=2)
    if output_path is not None:
        Path(output_path).write_text(payload, encoding="utf-8")
    return payload
