"""Resource estimation helpers for Snakemake rules.

Design goals:
- Deterministic, offline (no sacct dependency).
- Conservative-by-default via a global `fudge` factor.
- Per-tool defaults that can be overridden by config.

`mem_mb` is interpreted as total memory (SLURM `--mem`).
`runtime` is minutes (SLURM `--time` via profile mapping).
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Tuple

# Tool -> coefficients. These are intentionally coarse defaults; users can
# override per site/tool in `resources.estimation.overrides`.
DEFAULT_TOOL_ESTIMATES: dict[str, dict[str, int]] = {
    "default": {
        "mem_mb_base": 2000,
        "mem_mb_per_gb": 500,
        "runtime_base": 30,
        "runtime_per_gb": 10,
        "mem_mb_max": 64000,
        "runtime_max": 24 * 60,
    },
    "fastp": {
        "mem_mb_base": 2000,
        "mem_mb_per_gb": 800,
        "runtime_base": 20,
        "runtime_per_gb": 15,
        "mem_mb_max": 16000,
        "runtime_max": 6 * 60,
    },
    "bowtie2": {
        "mem_mb_base": 4000,
        "mem_mb_per_gb": 1200,
        "runtime_base": 30,
        "runtime_per_gb": 20,
        "mem_mb_max": 96000,
        "runtime_max": 12 * 60,
    },
    "megahit": {
        "mem_mb_base": 8000,
        "mem_mb_per_gb": 5000,
        "runtime_base": 60,
        "runtime_per_gb": 60,
        "mem_mb_max": 256000,
        "runtime_max": 48 * 60,
    },
    "vsearch": {
        "mem_mb_base": 2000,
        "mem_mb_per_gb": 1500,
        "runtime_base": 15,
        "runtime_per_gb": 10,
        "mem_mb_max": 64000,
        "runtime_max": 8 * 60,
    },
    "virsorter": {
        "mem_mb_base": 16000,
        "mem_mb_per_gb": 2500,
        "runtime_base": 120,
        "runtime_per_gb": 60,
        "mem_mb_max": 256000,
        "runtime_max": 72 * 60,
    },
    "genomad": {
        "mem_mb_base": 16000,
        "mem_mb_per_gb": 2000,
        "runtime_base": 60,
        "runtime_per_gb": 30,
        "mem_mb_max": 256000,
        "runtime_max": 48 * 60,
    },
    "checkv": {
        "mem_mb_base": 16000,
        "mem_mb_per_gb": 1500,
        "runtime_base": 60,
        "runtime_per_gb": 30,
        "mem_mb_max": 192000,
        "runtime_max": 48 * 60,
    },
    "busco": {
        "mem_mb_base": 16000,
        "mem_mb_per_gb": 1000,
        "runtime_base": 60,
        "runtime_per_gb": 20,
        "mem_mb_max": 128000,
        "runtime_max": 48 * 60,
    },
    "vclust": {
        "mem_mb_base": 8000,
        "mem_mb_per_gb": 2000,
        "runtime_base": 60,
        "runtime_per_gb": 30,
        "mem_mb_max": 192000,
        "runtime_max": 72 * 60,
    },
    # Project-wide downstream (single job).
    "coverm": {
        "mem_mb_base": 16000,
        "mem_mb_per_gb": 1800,
        "runtime_base": 60,
        "runtime_per_gb": 30,
        "mem_mb_max": 192000,
        "runtime_max": 72 * 60,
    },
    "phabox2": {
        "mem_mb_base": 16000,
        "mem_mb_per_gb": 1000,
        "runtime_base": 60,
        "runtime_per_gb": 20,
        "mem_mb_max": 128000,
        "runtime_max": 48 * 60,
    },
    # Lightweight python glue steps.
    "gmv": {
        "mem_mb_base": 2000,
        "mem_mb_per_gb": 500,
        "runtime_base": 10,
        "runtime_per_gb": 5,
        "mem_mb_max": 32000,
        "runtime_max": 6 * 60,
    },
}


def _as_float(v: Any, *, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _as_int(v: Any, *, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _merged_tool_estimate(tool: str, overrides: Mapping[str, Any] | None) -> dict[str, int]:
    base = DEFAULT_TOOL_ESTIMATES.get(tool, DEFAULT_TOOL_ESTIMATES["default"]).copy()
    if not overrides:
        return base
    tool_ov = overrides.get(tool) if isinstance(overrides, Mapping) else None
    if not isinstance(tool_ov, Mapping):
        return base
    for k in ("mem_mb_base", "mem_mb_per_gb", "runtime_base", "runtime_per_gb", "mem_mb_max", "runtime_max"):
        if k in tool_ov:
            base[k] = _as_int(tool_ov[k], default=base[k])
    return base


def estimate_tool_resources(tool: str, *, size_mb: float, estimation_cfg: Mapping[str, Any] | None) -> Tuple[int, int]:
    """Estimate (mem_mb, runtime_minutes) for a tool given total input size in MB."""
    estimation_cfg = estimation_cfg or {}
    enabled = bool(estimation_cfg.get("enabled", True))
    overrides = estimation_cfg.get("overrides", {}) if isinstance(estimation_cfg, Mapping) else {}

    est = _merged_tool_estimate(tool, overrides)
    mem_base = int(est["mem_mb_base"])
    runtime_base = int(est["runtime_base"])
    if not enabled:
        return mem_base, runtime_base

    fudge = _as_float(estimation_cfg.get("fudge", 1.2), default=1.2)
    size_mb = max(0.0, float(size_mb))
    gb = size_mb / 1024.0

    mem = (mem_base + float(est["mem_mb_per_gb"]) * gb) * fudge
    runtime = (runtime_base + float(est["runtime_per_gb"]) * gb) * fudge

    mem = min(mem, float(est["mem_mb_max"]))
    runtime = min(runtime, float(est["runtime_max"]))

    # Ceil to avoid under-allocating due to rounding.
    return int(max(mem_base, math.ceil(mem))), int(max(runtime_base, math.ceil(runtime)))

