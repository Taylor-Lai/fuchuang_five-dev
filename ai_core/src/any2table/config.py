"""Configuration defaults for Any2table."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Skills bundled inside the package so they are committed alongside the code.
_PACKAGE_SKILLS_ROOT = str(Path(__file__).parent / "skills" / "definitions")

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application-level configuration for local runs."""

    retrieval_backend: str = "rule"
    router_backend: str = "default"
    rag_backend: str = "hybrid"
    extractor_backend: str = "default"
    verifier_backend: str = "default"
    writer_backend: Literal["auto", "xlsx", "docx"] = "auto"
    enable_agent_runtime: bool = False
    agent_runtime_backend: str = "langgraph"
    enable_skill_runtime: bool = True
    skills_root: str = field(default_factory=lambda: _PACKAGE_SKILLS_ROOT)
    enable_llm_skill_execution: bool = False
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_api_key_env: str = "OPENAI_API_KEY"
    output_dir: str = "outputs"
    enable_intermediate_dump: bool = False
    intermediate_root: str = "workspace/cache"
    extra: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.enable_llm_skill_execution and not self.enable_skill_runtime:
            logger.warning(
                "enable_llm_skill_execution=True has no effect when enable_skill_runtime=False; "
                "set enable_skill_runtime=True to execute skills with LLM."
            )
        if self.writer_backend not in ("auto", "xlsx", "docx"):
            raise ValueError(
                f"Invalid writer_backend '{self.writer_backend}'; must be one of: 'auto', 'xlsx', 'docx'."
            )
