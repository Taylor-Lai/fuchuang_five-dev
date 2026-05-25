"""Multi-source table filling adapter for the Any2table pipeline."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Callable

from any2table.app import build_orchestrator
from any2table.cli import discover_assets
from any2table.config import AppConfig
from docnexus_ai.llm import LLM_PROVIDER, OPENAI_BASE_URL, OPENAI_MODEL

def _schema_classes():
    try:
        from ai_core.engine.schemas import Mod3_FusionOutput
    except ImportError:  # pragma: no cover - compatibility for tests importing engine directly
        from engine.schemas import Mod3_FusionOutput
    return Mod3_FusionOutput


def handle_table_filling(
    input_data,
    progress_callback: Callable[[str, str, str], None] | None = None,
) :
    Mod3_FusionOutput = _schema_classes()
    work_dir = Path(input_data.workspace_dir)
    user_request_content = input_data.user_request or "请根据源文档中的信息，自动填充模板表格。"
    (work_dir / "用户要求.txt").write_text(user_request_content, encoding="utf-8")

    try:
        if progress_callback:
            progress_callback(input_data.task_id, "processing", "正在初始化多智能体融合环境...")

        llm_provider = LLM_PROVIDER
        llm_model = "glm-4" if llm_provider == "zhipu" else OPENAI_MODEL
        llm_api_key_env = "ZHIPU_API_KEY" if llm_provider == "zhipu" else "OPENAI_API_KEY"

        config = AppConfig(
            enable_agent_runtime=True,
            agent_runtime_backend="langgraph",
            enable_llm_skill_execution=True,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key_env=llm_api_key_env,
            llm_base_url=OPENAI_BASE_URL or None,
        )

        assets = discover_assets(work_dir)
        if progress_callback:
            progress_callback(input_data.task_id, "processing", f"已识别 {len(assets)} 个文档资产，启动 LangGraph 引擎...")

        orchestrator = build_orchestrator(config=config)
        if progress_callback:
            progress_callback(input_data.task_id, "processing", "7大智能体开始协同流转，进行跨文件特征提取与对齐...")

        result = orchestrator.run(assets)
        if progress_callback:
            progress_callback(input_data.task_id, "success", "多源数据融合与质检完成，物理资产已生成！")

        warnings = list(result.fill_result.warnings)
        if result.verification_report.status != "pass":
            warnings.append(result.verification_report.summary)

        return Mod3_FusionOutput(
            status="success",
            task_id=input_data.task_id,
            output_excel_path=str(result.fill_result.output_path),
            warnings=warnings,
        )

    except Exception:
        if progress_callback:
            progress_callback(input_data.task_id, "failed", "流转异常打断")
        return Mod3_FusionOutput(
            status="failed",
            task_id=input_data.task_id,
            error_msg=traceback.format_exc(),
        )
