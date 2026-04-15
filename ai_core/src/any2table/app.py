"""Application assembly helpers."""

from __future__ import annotations

import logging

from any2table.agents import CoderAgent, MasterAgent, RAGAgent, RetrievalAgent, RouterAgent, TableAgent, VerifierAgent
from any2table.analyzers import DefaultTemplateAnalyzer
from any2table.compute import PythonComputeEngine
from any2table.config import AppConfig
from any2table.core.orchestrator import MultiAgentOrchestrator, SequentialOrchestrator
from any2table.core.runtime import GraphRuntime, LangGraphRuntime
from any2table.extractors import DefaultExtractor
from any2table.llm import build_llm_client
from any2table.parsers import DoclingSourceParser, DocxParser, TextParser, XlsxParser
from any2table.planners import DefaultTaskPlanner
from any2table.rag import DefaultRagBackend, HybridRagBackend
from any2table.registry import ComponentRegistry
from any2table.retrievers import RuleRetriever
from any2table.skills.registry import SkillRegistry
from any2table.verifiers import DefaultVerifier
from any2table.writers import DocxTableWriter, XlsxWriter

logger = logging.getLogger(__name__)


def build_registry(config: AppConfig | None = None) -> ComponentRegistry:
    registry = ComponentRegistry()
    registry.config = config or AppConfig()

    docling_parser = DoclingSourceParser()
    if not docling_parser._converter:
        logger.warning(
            "docling is not installed or failed to initialize; "
            "source documents will be parsed with DocxParser/XlsxParser instead. "
            "Install docling for enhanced table extraction: pip install docling"
        )
    registry.register_parser(docling_parser)
    registry.register_parser(TextParser())
    registry.register_parser(DocxParser())
    registry.register_parser(XlsxParser())

    registry.register_template_analyzer(DefaultTemplateAnalyzer())
    registry.register_task_planner("default", DefaultTaskPlanner())
    registry.register_retriever("rule", RuleRetriever())
    registry.register_rag_backend("default", DefaultRagBackend())
    registry.register_rag_backend("hybrid", HybridRagBackend())
    registry.register_extractor("default", DefaultExtractor())
    registry.register_compute_engine("python", PythonComputeEngine())
    registry.register_writer("xlsx", XlsxWriter())
    registry.register_writer("docx", DocxTableWriter())
    registry.register_verifier("default", DefaultVerifier())
    if registry.config.enable_skill_runtime:
        registry.skill_registry = SkillRegistry.from_root(registry.config.skills_root)
    if registry.config.enable_llm_skill_execution:
        registry.llm_client = build_llm_client(registry.config)
    return registry


def build_agent_runtime(registry: ComponentRegistry) -> GraphRuntime | LangGraphRuntime:
    nodes = [
        ("master", MasterAgent(registry)),
        ("table_agent", TableAgent(registry)),
        ("router_agent", RouterAgent(registry)),
        ("retrieval_agent", RetrievalAgent(registry)),
        ("rag_agent", RAGAgent(registry)),
        ("coder_agent", CoderAgent(registry)),
        ("verifier_agent", VerifierAgent(registry)),
    ]
    if registry.config.agent_runtime_backend == "langgraph":
        return LangGraphRuntime(nodes)
    return GraphRuntime(nodes)


def build_orchestrator(config: AppConfig | None = None):
    registry = build_registry(config=config)
    if registry.config.enable_agent_runtime:
        return MultiAgentOrchestrator(registry, runtime=build_agent_runtime(registry))
    return SequentialOrchestrator(registry)
