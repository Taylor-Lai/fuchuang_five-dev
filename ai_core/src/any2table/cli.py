"""CLI entrypoint for Any2table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from any2table.app import build_orchestrator
from any2table.config import AppConfig
from any2table.core.models import FileAsset

TEMPLATE_MARKER = "\u6a21\u677f"
USER_REQUEST_MARKER = "\u7528\u6237\u8981\u6c42"


def discover_assets(path: Path) -> list[FileAsset]:
    assets: list[FileAsset] = []
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        role = "source"
        name = file_path.name
        if "template" in name.lower() or TEMPLATE_MARKER in name:
            role = "template"
        elif USER_REQUEST_MARKER in name:
            role = "user_request"
        assets.append(
            FileAsset(
                id=file_path.as_posix(),
                path=str(file_path),
                name=name,
                ext=file_path.suffix.lower().lstrip("."),
                role=role,
                mime_type=None,
                size=file_path.stat().st_size,
            )
        )
    return assets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Any2table CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect file discovery only.")
    inspect_parser.add_argument("--path", required=True, help="Path to inspect.")

    run_parser = subparsers.add_parser("run", help="Run the fill pipeline.")
    run_parser.add_argument("--path", required=True, help="Path containing task files.")
    run_parser.add_argument(
        "--agent-runtime",
        action="store_true",
        help="Run the multi-agent orchestration runtime.",
    )
    run_parser.add_argument(
        "--agent-runtime-backend",
        choices=["langgraph", "graph"],
        default="langgraph",
        help="Select the agent orchestration backend.",
    )
    run_parser.add_argument(
        "--disable-skills",
        action="store_true",
        help="Disable local skill loading and skill trace generation.",
    )
    run_parser.add_argument(
        "--enable-llm-skills",
        action="store_true",
        help="Execute loaded skills with the configured OpenAI-compatible LLM.",
    )
    run_parser.add_argument(
        "--llm-model",
        default="gpt-4o-mini",
        help="Model name for OpenAI-compatible LLM skill execution.",
    )
    run_parser.add_argument(
        "--llm-base-url",
        default=None,
        help="Base URL for an OpenAI-compatible API endpoint.",
    )
    run_parser.add_argument(
        "--llm-api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable name containing the API key.",
    )
    run_parser.add_argument(
        "--rag-backend",
        choices=["default", "hybrid"],
        default="default",
        help="Select the registered RAG backend. Router still controls whether RAG is actually used.",
    )
    run_parser.add_argument(
        "--dump-intermediate",
        action="store_true",
        help="Dump canonical JSON, retrieval JSONL, and schema JSON artifacts.",
    )
    run_parser.add_argument(
        "--intermediate-root",
        default="workspace/cache",
        help="Root directory for intermediate JSON artifacts.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "inspect":
        assets = discover_assets(Path(args.path))
        print(json.dumps([asset.to_dict() for asset in assets], ensure_ascii=False, indent=2))
        return

    if args.command == "run":
        assets = discover_assets(Path(args.path))
        config = AppConfig(
            enable_agent_runtime=args.agent_runtime,
            agent_runtime_backend=args.agent_runtime_backend,
            enable_skill_runtime=not args.disable_skills,
            enable_llm_skill_execution=args.enable_llm_skills,
            llm_model=args.llm_model,
            llm_base_url=args.llm_base_url,
            llm_api_key_env=args.llm_api_key_env,
            rag_backend=args.rag_backend,
            enable_intermediate_dump=args.dump_intermediate,
            intermediate_root=args.intermediate_root,
        )
        orchestrator = build_orchestrator(config=config)
        result = orchestrator.run(assets)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
