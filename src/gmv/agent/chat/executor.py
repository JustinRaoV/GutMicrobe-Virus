"""Tool execution for GMV ChatOps (shell=False, argv=list[str]).

High-risk actions require explicit confirmation unless --auto-approve is enabled.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from gmv.agent.chat.tools import sanitize_args, tool_risk


@dataclass(frozen=True)
class ToolResult:
    returncode: int
    stdout_tail: str
    stderr_tail: str
    artifact_paths: List[str]
    content_for_llm: str


def _tail_text(text: str, *, max_lines: int = 200, max_bytes: int = 20_000) -> str:
    if not text:
        return ""
    # bytes clamp first (keep tail)
    b = text.encode("utf-8", errors="replace")
    if len(b) > max_bytes:
        b = b[-max_bytes:]
        text = b.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines)


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_artifact(dir_path: Path, name: str, content: str) -> str:
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / name
    p.write_text(content, encoding="utf-8", errors="replace")
    return str(p)


def _repo_root() -> Path:
    # .../src/gmv/agent/chat/executor.py -> chat -> agent -> gmv -> src -> repo
    return Path(__file__).resolve().parents[4]


def _confirm(prompt: str) -> bool:
    try:
        ans = input(prompt).strip().lower()
    except EOFError:
        return False
    return ans in {"y", "yes"}


def _run_argv(
    argv: List[str],
    *,
    cwd: Path,
    env: Optional[Mapping[str, str]] = None,
    timeout_s: Optional[int] = None,
) -> Tuple[int, str, str]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        env=None if env is None else dict(env),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return int(proc.returncode), str(proc.stdout or ""), str(proc.stderr or "")


def _tail_file(path: Path, *, lines: int) -> str:
    if not path.exists():
        return f"ERROR: file not found: {path}"
    # Read last ~1MB for efficiency, then split lines.
    try:
        size = path.stat().st_size
        read_bytes = min(size, 1024 * 1024)
        with path.open("rb") as fh:
            if read_bytes < size:
                fh.seek(-read_bytes, 2)
            data = fh.read()
        text = data.decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])
    except Exception as exc:
        return f"ERROR: cannot read file: {path} ({exc})"


def execute_tool(
    tool_name: str,
    args: Mapping[str, Any],
    *,
    config_path: str,
    auto_approve: bool,
    interactive: bool,
    dry_run_tools: bool,
    log_dir: Path,
) -> ToolResult:
    a = sanitize_args(tool_name, args)
    risk = tool_risk(tool_name, a)

    repo_root = _repo_root()

    preview = {"tool": tool_name, "risk": risk, "args": a}
    preview_text = json.dumps(preview, ensure_ascii=False, indent=2)

    if risk == "high" and not auto_approve:
        if interactive:
            print("检测到高风险动作，需要确认后执行：")
            print(preview_text)
            if not _confirm("确认执行？[y/N] "):
                return ToolResult(
                    returncode=3,
                    stdout_tail="",
                    stderr_tail="用户取消执行高风险动作",
                    artifact_paths=[],
                    content_for_llm="USER_CANCELLED: high-risk action not executed.",
                )
        else:
            return ToolResult(
                returncode=3,
                stdout_tail="",
                stderr_tail="需要确认才能执行高风险动作（请使用交互模式或添加 --auto-approve）",
                artifact_paths=[_write_artifact(log_dir, f"tool.{_utc_ts()}.{tool_name}.preview.json", preview_text + "\n")],
                content_for_llm="NEEDS_CONFIRMATION: high-risk action blocked.",
            )

    if tool_name in {"tail_file"}:
        path = Path(str(a["path"])).expanduser()
        out = _tail_file(path, lines=int(a["lines"]))
        return ToolResult(
            returncode=0,
            stdout_tail=_tail_text(out),
            stderr_tail="",
            artifact_paths=[],
            content_for_llm=out,
        )

    if tool_name == "show_latest_snakemake_log":
        log_root = repo_root / ".snakemake" / "log"
        logs = sorted(log_root.glob("*.snakemake.log")) if log_root.exists() else []
        if not logs:
            out = f"ERROR: no snakemake logs found under {log_root}"
        else:
            out = f"==> {logs[-1]}\n" + _tail_file(logs[-1], lines=int(a.get("lines", 200)))
        return ToolResult(
            returncode=0 if "ERROR:" not in out else 1,
            stdout_tail=_tail_text(out),
            stderr_tail="",
            artifact_paths=[],
            content_for_llm=out,
        )

    argv: List[str]
    if tool_name == "gmv_validate":
        argv = [sys.executable, "-m", "gmv.cli", "validate", "--config", str(a["config_path"])]
        if bool(a.get("strict", False)):
            argv.append("--strict")
    elif tool_name == "gmv_run":
        argv = [
            sys.executable,
            "-m",
            "gmv.cli",
            "run",
            "--config",
            str(a["config_path"]),
            "--profile",
            str(a["profile"]),
            "--stage",
            str(a.get("stage") or "all"),
        ]
        if bool(a.get("dry_run", False)):
            argv.append("--dry-run")
        if a.get("cores") is not None:
            argv.extend(["--cores", str(int(a["cores"]))])
    elif tool_name == "gmv_report":
        argv = [sys.executable, "-m", "gmv.cli", "report", "--config", str(a["config_path"])]
        if a.get("run_id"):
            argv.extend(["--run-id", str(a["run_id"])])
    elif tool_name == "gmv_agent_harvest":
        argv = [sys.executable, "-m", "gmv.cli", "agent", "harvest", "--config", str(a["config_path"])]
        if a.get("run_id"):
            argv.extend(["--run-id", str(a["run_id"])])
        if a.get("snakemake_log"):
            argv.extend(["--snakemake-log", str(a["snakemake_log"])])
    elif tool_name == "slurm_squeue":
        argv = ["squeue", "-h", "-o", "%i|%T|%j|%u|%M|%D|%R"]
        if a.get("user"):
            argv.extend(["-u", str(a["user"])])
        if a.get("name"):
            argv.extend(["-n", str(a["name"])])
        if a.get("states"):
            argv.extend(["-t", str(a["states"])])
        argv.extend(["--sort", "i"])
    elif tool_name == "slurm_sacct":
        fields = a.get("fields") or []
        if not fields:
            fields = ["JobID", "State", "ExitCode", "ElapsedRaw", "MaxRSS", "ReqMem", "AllocCPUS"]
        argv = [
            "sacct",
            "-X",
            "-P",
            "-n",
            "-j",
            str(a["job_id"]),
            "-o",
            ",".join([str(x) for x in fields]),
        ]
    elif tool_name == "slurm_scontrol_show_job":
        argv = ["scontrol", "show", "job", str(a["job_id"])]
    elif tool_name == "slurm_scancel":
        argv = ["scancel", str(a["job_id"])]
    else:
        return ToolResult(
            returncode=2,
            stdout_tail="",
            stderr_tail=f"未知工具: {tool_name}",
            artifact_paths=[],
            content_for_llm=f"ERROR: unknown tool: {tool_name}",
        )

    # Ensure we always operate with the user-provided config path for gmv_* tools.
    # Some tools don't use config_path; still include in preview for audit.
    _ = config_path

    if dry_run_tools:
        out = f"DRY_RUN_TOOL: would run argv={argv} cwd={repo_root}"
        artifact = _write_artifact(log_dir, f"tool.{_utc_ts()}.{tool_name}.dryrun.txt", out + "\n")
        return ToolResult(
            returncode=0,
            stdout_tail=_tail_text(out),
            stderr_tail="",
            artifact_paths=[artifact],
            content_for_llm=out,
        )

    rc, stdout, stderr = _run_argv(argv, cwd=repo_root, env=os.environ)
    artifact_content = f"argv={argv}\n\n--- stdout ---\n{stdout}\n\n--- stderr ---\n{stderr}\n"
    artifact = _write_artifact(log_dir, f"tool.{_utc_ts()}.{tool_name}.log.txt", artifact_content)
    return ToolResult(
        returncode=rc,
        stdout_tail=_tail_text(stdout),
        stderr_tail=_tail_text(stderr),
        artifact_paths=[artifact],
        content_for_llm=_tail_text(stdout + ("\n" + stderr if stderr else "")),
    )

