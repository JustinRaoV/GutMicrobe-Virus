"""Unified CLI for GutMicrobeVirus v2."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from gmv.agent.policy_engine import PolicyEngine
from gmv.agent.replay import replay_decisions
from gmv.config_schema import ConfigValidationError, load_pipeline_config
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
    except ConfigValidationError as exc:
        print(f"ERROR: {exc}")
        return 1

    result = validate_environment(config, strict=args.strict)
    _print_validation(result)
    return 1 if result["errors"] else 0


def cmd_profile(args: argparse.Namespace) -> int:
    config = load_pipeline_config(args.config)
    enabled = {k: v for k, v in config["tools"]["enabled"].items() if v}
    print(json.dumps(
        {
            "run_id": config["execution"]["run_id"],
            "profile": config["execution"]["profile"],
            "mock_mode": config["execution"]["mock_mode"],
            "enabled_tools": sorted(enabled.keys()),
            "sample_sheet": config["execution"]["sample_sheet"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load_pipeline_config(args.config)
    profile = args.profile or config["execution"]["profile"]
    return run_snakemake(config_path=args.config, profile=profile, dry_run=args.dry_run, cores=args.cores)


def cmd_report(args: argparse.Namespace) -> int:
    config = load_pipeline_config(args.config)
    run_id = args.run_id or config["execution"]["run_id"]
    report_paths = generate_report(
        results_dir=config["execution"]["results_dir"],
        reports_dir=config["execution"]["reports_dir"],
        run_id=run_id,
    )
    for k, v in report_paths.items():
        print(f"{k}: {v}")
    return 0


def cmd_agent_replay(args: argparse.Namespace) -> int:
    engine = PolicyEngine(
        auto_apply_risk_levels=set(args.auto_apply_risk_levels.split(",")),
        retry_limit=args.retry_limit,
        low_yield_threshold=args.low_yield_threshold,
    )
    decisions = replay_decisions(args.file, engine)
    for d in decisions:
        print(json.dumps(d, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gmv", description="GutMicrobeVirus v2 unified CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="校验配置、镜像和运行环境")
    p.add_argument("--config", default="config/pipeline.yaml")
    p.add_argument("--strict", action="store_true")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("profile", help="输出当前运行配置摘要")
    p.add_argument("--config", default="config/pipeline.yaml")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("run", help="执行 Snakemake workflow")
    p.add_argument("--config", default="config/pipeline.yaml")
    p.add_argument("--profile", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--cores", type=int, default=None)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="生成中文报告与英文图表")
    p.add_argument("--config", default="config/pipeline.yaml")
    p.add_argument("--run-id", default=None)
    p.set_defaults(func=cmd_report)

    agent = sub.add_parser("agent", help="Agent 工具")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    rp = agent_sub.add_parser("replay", help="回放 signal 日志并输出决策")
    rp.add_argument("--file", required=True)
    rp.add_argument("--auto-apply-risk-levels", default="low")
    rp.add_argument("--retry-limit", type=int, default=2)
    rp.add_argument("--low-yield-threshold", type=int, default=5)
    rp.set_defaults(func=cmd_agent_replay)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
