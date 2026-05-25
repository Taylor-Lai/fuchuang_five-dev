"""Experimental knowledge graph sidecar.

The KG module is intentionally not wired into the main extraction or table
filling pipeline yet.  It provides a stable shell for future GraphRAG work.
"""

from .builder import KnowledgeGraphBuilder
from .exporter import export_graph_json
from .models import GraphEntity, GraphRelation, KnowledgeGraph

__all__ = [
    "GraphEntity",
    "GraphRelation",
    "KnowledgeGraph",
    "KnowledgeGraphBuilder",
    "export_graph_json",
]
