"""Unified CLI for GutMicrobeVirus v3."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from gmv.chat.session import run_chat
from gmv.config import ConfigError, load_pipeline_config
from gmv.reporting.generator import generate_report
from gmv.validation import validate_environment
from gmv.workflow.runner import run_snakemake


def _print_validation(result: dict) -> None:
    for msg in result.get("info", []):
        print(msg)
    for msg in result.get("warnings", []):
        print(f"WARNING: {msg}")
    for msg in result.get("errors", []):
        print(f"ERROR: {msg}")


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        config = load_pipeline_config(args.config)
    except ConfigError as exc:
        print(f"ERROR: {exc}")
        return 1

    result = validate_environment(config, strict=args.strict)
    _print_validation(result)
    return 1 if result["errors"] else 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_pipeline_config(args.config)
    except ConfigError as exc:
        print(f"ERROR: {exc}")
        return 1

    profile = args.profile or config["execution"].get("profile", "local")
    return run_snakemake(
        config=config,
        config_path=args.config,
        profile=str(profile),
        dry_run=bool(args.dry_run),
        cores=args.cores,
        stage=str(args.stage),
    )


def cmd_report(args: argparse.Namespace) -> int:
    try:
        config = load_pipeline_config(args.config)
    except ConfigError as exc:
        print(f"ERROR: {exc}")
        return 1

    run_id = args.run_id or config["execution"].get("run_id", "default-run")
    outputs = generate_report(
        results_dir=config["execution"]["results_dir"],
        reports_dir=config["execution"]["reports_dir"],
        run_id=str(run_id),
    )
    for key, value in outputs.items():
        print(f"{key}: {value}")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    result = run_chat(
        config_path=args.config,
        message=args.message,
        auto_approve=bool(args.auto_approve),
        max_steps=int(args.max_steps),
        log_dir=args.log_dir,
        base_url=args.base_url,
        model=args.model,
        api_key_env=args.api_key_env,
        llm_config=args.llm_config,
    )
    print(f"audit_log: {result.audit_log}")
    return int(result.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gmv", description="GutMicrobeVirus v3 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="校验配置、镜像和运行环境")
    p.add_argument("--config", default="config/pipeline.yaml")
    p.add_argument("--strict", action="store_true")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("run", help="执行 Snakemake workflow")
    p.add_argument("--config", default="config/pipeline.yaml")
    p.add_argument("--profile", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--stage", choices=["upstream", "project", "all"], default="all")
    p.add_argument("--cores", type=int, default=None)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="生成中文报告与英文图表")
    p.add_argument("--config", default="config/pipeline.yaml")
    p.add_argument("--run-id", default=None)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("chat", help="对话式 ChatOps（本地/SLURM 白名单工具）")
    p.add_argument("--config", default="config/pipeline.yaml")
    p.add_argument("--message", default=None, help="单条消息；不传则进入 REPL")
    p.add_argument("--auto-approve", action="store_true", help="允许执行高风险动作")
    p.add_argument("--max-steps", type=int, default=8)
    p.add_argument("--log-dir", default=None)
    p.add_argument("--base-url", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--api-key-env", default=None)
    p.add_argument("--llm-config", default=None)
    p.set_defaults(func=cmd_chat)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
