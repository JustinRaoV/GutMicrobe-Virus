from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import (
    ConfigError,
    dump_yaml,
    load_pipeline_config,
    prepare_sample_sheet,
    validate_runtime,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _snakefile_path() -> Path:
    return _project_root() / "workflow" / "Snakefile"


def _profile_path(profile: str) -> Path:
    return _project_root() / "profiles" / profile


def _ensure_layout(cfg: dict[str, Any]) -> None:
    for key in ("raw_dir", "work_dir", "cache_dir", "results_dir", "reports_dir"):
        Path(cfg["execution"][key]).mkdir(parents=True, exist_ok=True)


def _runtime_config_path(run_id: str) -> Path:
    target = _project_root() / ".gmv" / "runtime" / f"{run_id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _build_snakemake_cmd(
    runtime_config: Path,
    profile: str,
    stage: str,
    cores: int,
    dry_run: bool,
    cfg: dict[str, Any],
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "snakemake",
        "--snakefile",
        str(_snakefile_path()),
        "--configfile",
        str(runtime_config),
        "--cores",
        str(cores),
        "--rerun-incomplete",
        "--printshellcmds",
    ]

    profile_dir = _profile_path(profile)
    if profile_dir.exists():
        cmd.extend(["--profile", str(profile_dir)])

    limits = cfg.get("resources", {}).get("limits", {})
    if limits:
        cmd.append("--resources")
        for key, value in limits.items():
            cmd.append(f"{key}={int(value)}")

    if dry_run:
        cmd.extend(["--dry-run", "--reason"])

    if stage == "upstream":
        cmd.extend(["--until", "busco_filter"])
    elif stage == "project":
        target = Path(cfg["execution"]["results_dir"]) / cfg["execution"]["run_id"] / "agent" / "decisions.jsonl"
        cmd.append(str(target))

    return cmd


def run_pipeline(
    config_path: str,
    profile: str,
    stage: str,
    cores: int | None,
    dry_run: bool,
    input_dir: str | None,
    sample_sheet: str | None,
    pair_r1: str,
    pair_r2: str,
) -> dict[str, Any]:
    cfg = load_pipeline_config(config_path)
    if profile:
        cfg["execution"]["profile"] = profile

    run_id = cfg["execution"]["run_id"]
    _ensure_layout(cfg)

    sheet_path, samples, generated = prepare_sample_sheet(
        cfg=cfg,
        input_dir=input_dir,
        sample_sheet=sample_sheet,
        pair_r1=pair_r1,
        pair_r2=pair_r2,
    )

    errors, warnings = validate_runtime(cfg, samples, strict=False)
    if errors:
        raise ConfigError("\n".join(["运行前校验失败:", *errors]))

    runtime_config = _runtime_config_path(run_id)
    dump_yaml(str(runtime_config), cfg)

    resolved_cores = int(cores or cfg.get("resources", {}).get("default_threads", 8))
    cmd = _build_snakemake_cmd(
        runtime_config=runtime_config,
        profile=cfg["execution"].get("profile", "local"),
        stage=stage,
        cores=resolved_cores,
        dry_run=dry_run,
        cfg=cfg,
    )

    print("[GMV] Snakemake command:")
    print(" ".join(shlex.quote(part) for part in cmd))
    if warnings:
        print("[GMV] Warnings:")
        for item in warnings:
            print(f"  - {item}")

    completed = subprocess.run(cmd, cwd=str(_project_root()))
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    return {
        "run_id": run_id,
        "sample_sheet": sheet_path,
        "generated_sample_sheet": generated,
        "cores": resolved_cores,
        "stage": stage,
        "profile": cfg["execution"].get("profile", "local"),
    }
