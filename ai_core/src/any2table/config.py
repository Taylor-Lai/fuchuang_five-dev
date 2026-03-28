"""Configuration defaults for Any2table."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AppConfig:
    """Application-level configuration for local runs."""

    retrieval_backend: str = "rule"
    router_backend: str = "default"
    rag_backend: str = "default"
    extractor_backend: str = "default"
    verifier_backend: str = "default"
    writer_backend: str = "auto"
    enable_agent_runtime: bool = False
    agent_runtime_backend: str = "langgraph"
    enable_skill_runtime: bool = True
    skills_root: str = ".claude/skills"
    enable_llm_skill_execution: bool = False
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_api_key_env: str = "OPENAI_API_KEY"
    output_dir: str = "outputs"
    enable_intermediate_dump: bool = False
    intermediate_root: str = "workspace/cache"
    extra: dict[str, object] = field(default_factory=dict)
