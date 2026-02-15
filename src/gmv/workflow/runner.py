"""Snakemake runner helpers."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def run_snakemake(config_path: str, profile: str, dry_run: bool = False, cores: Optional[int] = None) -> int:
    snake = shutil.which("snakemake")
    if not snake:
        print("错误: 未找到 snakemake 命令，请在服务器环境安装 Snakemake。")
        return 2
    cfg_path = Path(config_path).resolve()
    cfg_dir = cfg_path.parent

    # Prefer singularity, fall back to apptainer if needed.
    container_runtime = "singularity"
    if not shutil.which("singularity") and shutil.which("apptainer"):
        container_runtime = "apptainer"

    repo_root = Path(__file__).resolve().parents[3]
    snakefile = repo_root / "workflow" / "Snakefile"
    profile_dir = repo_root / "profiles" / profile

    cmd = [
        snake,
        "--snakefile",
        str(snakefile),
        "--configfile",
        str(cfg_path),
        "--config",
        f"config_dir={cfg_dir}",
        f"container_runtime={container_runtime}",
        "--profile",
        str(profile_dir),
    ]

    if dry_run:
        cmd.append("-n")
    if cores is not None:
        cmd.extend(["--cores", str(cores)])

    result = subprocess.run(cmd, check=False)
    return int(result.returncode)
