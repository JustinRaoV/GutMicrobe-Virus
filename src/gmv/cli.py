from __future__ import annotations

import argparse
from pathlib import Path

from .chat.session import chat_options_from_args, run_chat
from .config import ConfigError, load_pipeline_config, prepare_sample_sheet, validate_runtime
from .reporting import generate_report
from .workflow.runner import run_pipeline


def _default_config_path() -> str:
    return str((Path.cwd() / "config" / "pipeline.yaml").resolve())


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        cfg = load_pipeline_config(args.config)
        sheet, samples, generated = prepare_sample_sheet(
            cfg,
            input_dir=args.input_dir,
            sample_sheet=args.sample_sheet,
            pair_r1=args.pair_r1,
            pair_r2=args.pair_r2,
            host=args.host,
        )
        errors, warnings = validate_runtime(cfg, samples, strict=bool(args.strict))
    except ConfigError as exc:
        print(f"ERROR: {exc}")
        return 2

    print(f"[GMV] run_id: {cfg['execution']['run_id']}")
    print(f"[GMV] sample_sheet: {sheet}")
    print(f"[GMV] samples: {len(samples)}")
    if generated:
        print("[GMV] sample sheet: auto-generated from --input-dir")

    for warning in warnings:
        print(f"WARN: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2

    print("[GMV] validate passed")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        result = run_pipeline(
            config_path=args.config,
            profile=args.profile,
            stage=args.stage,
            cores=args.cores,
            dry_run=bool(args.dry_run),
            input_dir=args.input_dir,
            sample_sheet=args.sample_sheet,
            pair_r1=args.pair_r1,
            pair_r2=args.pair_r2,
            host=args.host,
        )
    except ConfigError as exc:
        print(f"ERROR: {exc}")
        return 2
    except SystemExit as exc:
        return int(exc.code)

    print(f"[GMV] run finished: run_id={result['run_id']} stage={result['stage']} profile={result['profile']}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    try:
        result = generate_report(config_path=args.config, run_id=args.run_id)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: report failed: {exc}")
        return 2

    print(f"[GMV] report generated: {result['methods']}")
    print(f"[GMV] summary table: {result['table']}")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    options = chat_options_from_args(args)
    return run_chat(options)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gmv", description="GMV v4 unified CLI")
    parser.set_defaults(handler=lambda _: parser.print_help())

    subparsers = parser.add_subparsers(dest="command")

    validate = subparsers.add_parser("validate", help="validate config, paths, and sample inputs")
    validate.add_argument("--config", default=_default_config_path())
    validate.add_argument("--input-dir", default=None)
    validate.add_argument("--sample-sheet", default=None)
    validate.add_argument("--pair-r1", default="_R1")
    validate.add_argument("--pair-r2", default="_R2")
    validate.add_argument("--host", default="", help="default host label for all samples (e.g. hg38)")
    validate.add_argument("--strict", action="store_true")
    validate.set_defaults(handler=cmd_validate)

    run = subparsers.add_parser("run", help="run Snakemake workflow")
    run.add_argument("--config", default=_default_config_path())
    run.add_argument("--input-dir", default=None)
    run.add_argument("--sample-sheet", default=None)
    run.add_argument("--pair-r1", default="_R1")
    run.add_argument("--pair-r2", default="_R2")
    run.add_argument("--host", default="", help="default host label for all samples (e.g. hg38)")
    run.add_argument("--profile", choices=["local", "slurm"], default="local")
    run.add_argument("--stage", choices=["upstream", "project", "all"], default="all")
    run.add_argument("--cores", type=int, default=None)
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(handler=cmd_run)

    report = subparsers.add_parser("report", help="generate report package")
    report.add_argument("--config", default=_default_config_path())
    report.add_argument("--run-id", default=None)
    report.set_defaults(handler=cmd_report)

    chat = subparsers.add_parser("chat", help="chatops for local/slurm execution")
    chat.add_argument("--config", default=_default_config_path())
    chat.add_argument("--message", default=None)
    chat.add_argument("--auto-approve", action="store_true")
    chat.add_argument("--max-steps", type=int, default=8)
    chat.add_argument("--log-dir", default=None)
    chat.add_argument("--base-url", default=None)
    chat.add_argument("--model", default=None)
    chat.add_argument("--api-key-env", default="GMV_API_KEY")
    chat.add_argument("--llm-config", default="~/.config/gmv/llm.yaml")
    chat.set_defaults(handler=cmd_chat)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
