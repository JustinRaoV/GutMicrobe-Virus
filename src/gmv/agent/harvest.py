"""Harvest resource usage and suggest next-run overrides (offline-friendly).

This is intentionally best-effort:
- If `sacct` is unavailable, we still emit a YAML skeleton.
- If we cannot parse job ids from snakemake logs, we emit a YAML skeleton.

The output file is *not* auto-applied to configs; it is advisory.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

import yaml


_SUBMITTED_RE = re.compile(r"Submitted job (?P<jobid>\\d+) with external jobid '?\"?(?P<ext>\\d+)", re.IGNORECASE)
_RULE_RE = re.compile(r"^(?:local)?rule\\s+(?P<rule>[A-Za-z0-9_]+):\\s*$")
_JOBID_RE = re.compile(r"^\\s*jobid:\\s*(?P<jobid>\\d+)\\s*$")


@dataclass(frozen=True)
class SacctRow:
    job_id: str
    max_rss_mb: Optional[int]
    elapsed_min: Optional[int]
    state: str
    exit_code: str


def _find_latest_snakemake_log(repo_root: Path) -> Optional[Path]:
    log_dir = repo_root / ".snakemake" / "log"
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob("*.snakemake.log"))
    return logs[-1] if logs else None


def _parse_snakemake_log_for_jobids(log_file: Path) -> Dict[str, str]:
    """Return mapping of external slurm jobid -> rule name."""
    # First map snakemake internal jobid -> rule name.
    jobid_to_rule: Dict[str, str] = {}
    current_rule: Optional[str] = None
    with log_file.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = _RULE_RE.match(line)
            if m:
                current_rule = m.group("rule")
                continue
            m = _JOBID_RE.match(line)
            if m and current_rule:
                jobid_to_rule[m.group("jobid")] = current_rule

    # Then map external jobid -> internal jobid, and join.
    ext_to_rule: Dict[str, str] = {}
    with log_file.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = _SUBMITTED_RE.search(line)
            if not m:
                continue
            internal = m.group("jobid")
            ext = m.group("ext")
            rule = jobid_to_rule.get(internal)
            if rule:
                ext_to_rule[ext] = rule
    return ext_to_rule


def _parse_rss_to_mb(v: str) -> Optional[int]:
    v = (v or "").strip()
    if not v or v in {"Unknown", "N/A"}:
        return None
    # Common: "123456K", "1024M", "1.5G", sometimes "123456" (KB).
    m = re.match(r"^(?P<num>\\d+(?:\\.\\d+)?)(?P<unit>[KMGTP])?$", v, re.IGNORECASE)
    if not m:
        return None
    num = float(m.group("num"))
    unit = (m.group("unit") or "K").upper()
    factor = {"K": 1.0 / 1024.0, "M": 1.0, "G": 1024.0, "T": 1024.0 * 1024.0, "P": 1024.0 * 1024.0 * 1024.0}[unit]
    return int(math.ceil(num * factor))


def _seconds_to_minutes(v: str) -> Optional[int]:
    v = (v or "").strip()
    if not v:
        return None
    try:
        sec = int(float(v))
    except ValueError:
        return None
    return int(math.ceil(sec / 60.0))


def _sacct_rows(job_ids: Iterable[str]) -> Dict[str, SacctRow]:
    """Fetch sacct stats for job ids. Keys are base job ids (no .batch)."""
    job_ids = [j for j in job_ids if str(j).strip()]
    if not job_ids:
        return {}
    cmd = [
        "sacct",
        "-X",
        "-P",
        "-n",
        "-j",
        ",".join(job_ids),
        "-o",
        "JobID,MaxRSS,ElapsedRaw,State,ExitCode",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {}

    rows: Dict[str, SacctRow] = {}
    for line in proc.stdout.splitlines():
        parts = line.split("|")
        if len(parts) < 5:
            continue
        job_id = parts[0].strip()
        base = job_id.split(".", 1)[0]
        rows[base] = SacctRow(
            job_id=base,
            max_rss_mb=_parse_rss_to_mb(parts[1]),
            elapsed_min=_seconds_to_minutes(parts[2]),
            state=parts[3].strip(),
            exit_code=parts[4].strip(),
        )
    return rows


def _rule_to_tool(rule: str) -> str:
    mapping = {
        "preprocess": "fastp",
        "host_removal": "bowtie2",
        "assembly": "megahit",
        "vsearch": "vsearch",
        "detect_virsorter": "virsorter",
        "detect_genomad": "genomad",
        "combine": "gmv",
        "checkv": "checkv",
        "high_quality": "gmv",
        "busco_filter": "busco",
        "viruslib_merge": "gmv",
        "viruslib_dedup": "vclust",
        "viruslib_annotation": "phabox2",
        "downstream_quant": "coverm",
        "agent_decision_log": "gmv",
    }
    return mapping.get(rule, "default")


def harvest_resources(
    *,
    config: Mapping[str, Any],
    run_id: str,
    repo_root: Optional[Path] = None,
    snakemake_log: Optional[str] = None,
) -> Path:
    repo_root = repo_root or Path.cwd()
    results_dir = Path(str(config.get("execution", {}).get("results_dir", "results")))
    out_dir = results_dir / run_id / "agent"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "resources_overrides.yaml"

    estimation_cfg = config.get("resources", {}).get("estimation", {}) or {}
    fudge = float(estimation_cfg.get("fudge", 1.2) or 1.2)

    log_path: Optional[Path] = Path(snakemake_log).expanduser().resolve() if snakemake_log else _find_latest_snakemake_log(repo_root)

    have_sacct = shutil.which("sacct") is not None
    ext_to_rule: Dict[str, str] = {}
    if log_path and log_path.exists():
        ext_to_rule = _parse_snakemake_log_for_jobids(log_path)

    overrides: Dict[str, Dict[str, int]] = {}
    notes = []

    if not have_sacct:
        notes.append("未检测到 sacct：仅生成 overrides 模板（不含学习结果）。")
    elif not ext_to_rule:
        notes.append("未能从 snakemake log 解析 SLURM jobid：仅生成 overrides 模板。")
    else:
        rows = _sacct_rows(ext_to_rule.keys())
        if not rows:
            notes.append("sacct 返回为空或调用失败：仅生成 overrides 模板。")
        else:
            per_tool_rss: Dict[str, int] = {}
            per_tool_elapsed: Dict[str, int] = {}
            for ext, rule in ext_to_rule.items():
                row = rows.get(ext)
                if not row:
                    continue
                tool = _rule_to_tool(rule)
                if row.max_rss_mb is not None:
                    per_tool_rss[tool] = max(per_tool_rss.get(tool, 0), int(row.max_rss_mb))
                if row.elapsed_min is not None:
                    per_tool_elapsed[tool] = max(per_tool_elapsed.get(tool, 0), int(row.elapsed_min))

            for tool in sorted(set(per_tool_rss) | set(per_tool_elapsed)):
                ov: Dict[str, int] = {}
                if tool in per_tool_rss and per_tool_rss[tool] > 0:
                    ov["mem_mb_max"] = int(math.ceil(per_tool_rss[tool] * fudge))
                if tool in per_tool_elapsed and per_tool_elapsed[tool] > 0:
                    ov["runtime_max"] = int(math.ceil(per_tool_elapsed[tool] * fudge))
                if ov:
                    overrides[tool] = ov

            notes.append(f"sacct 学习完成：生成 {len(overrides)} 个工具的 mem/runtime 上限建议。")

    payload = {
        "run_id": run_id,
        "generated_by": "gmv agent harvest",
        "source": {
            "sacct": bool(have_sacct),
            "snakemake_log": str(log_path) if log_path else "",
        },
        "notes": notes,
        "resources": {"estimation": {"overrides": overrides}},
    }
    out_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out_file

