from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..config import load_pipeline_config
from ..reporting import generate_report
from ..workflow.runner import run_pipeline


@dataclass(frozen=True)
class ChatTool:
    name: str
    description: str
    risk: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


def _tail(path: Path, lines: int = 200) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def _run_cmd(argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(argv, capture_output=True, text=True)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _tool_validate(args: dict[str, Any]) -> dict[str, Any]:
    from ..config import prepare_sample_sheet, validate_runtime

    config_path = args["config_path"]
    cfg = load_pipeline_config(config_path)
    sheet_path, samples, generated = prepare_sample_sheet(
        cfg,
        input_dir=args.get("input_dir"),
        sample_sheet=args.get("sample_sheet"),
        pair_r1=args.get("pair_r1", "_R1"),
        pair_r2=args.get("pair_r2", "_R2"),
        host=args.get("host", ""),
    )
    errors, warnings = validate_runtime(cfg, samples, strict=bool(args.get("strict", False)))
    return {
        "returncode": 0 if not errors else 2,
        "errors": errors,
        "warnings": warnings,
        "sample_sheet": sheet_path,
        "generated_sample_sheet": generated,
    }


def _tool_run(args: dict[str, Any]) -> dict[str, Any]:
    result = run_pipeline(
        config_path=args["config_path"],
        profile=args.get("profile", "local"),
        stage=args.get("stage", "all"),
        cores=args.get("cores"),
        dry_run=bool(args.get("dry_run", False)),
        input_dir=args.get("input_dir"),
        sample_sheet=args.get("sample_sheet"),
        pair_r1=args.get("pair_r1", "_R1"),
        pair_r2=args.get("pair_r2", "_R2"),
        host=args.get("host", ""),
    )
    return {"returncode": 0, **result}


def _tool_report(args: dict[str, Any]) -> dict[str, Any]:
    result = generate_report(config_path=args["config_path"], run_id=args.get("run_id"))
    return {"returncode": 0, **result}


def _tool_squeue(args: dict[str, Any]) -> dict[str, Any]:
    argv = ["squeue", "-h", "-o", "%i %u %t %M %D %R %j"]
    if args.get("user"):
        argv.extend(["-u", str(args["user"])])
    result = _run_cmd(argv)
    lines = result["stdout"].splitlines()
    limit = int(args.get("limit", 50))
    result["stdout_tail"] = "\n".join(lines[:limit])
    return result


def _tool_sacct(args: dict[str, Any]) -> dict[str, Any]:
    fields = args.get("fields") or ["JobID", "State", "Elapsed", "MaxRSS", "ReqMem", "ExitCode"]
    argv = ["sacct", "-j", str(args["job_id"]), "--format", ",".join(fields), "-n", "-P"]
    return _run_cmd(argv)


def _tool_scontrol(args: dict[str, Any]) -> dict[str, Any]:
    return _run_cmd(["scontrol", "show", "job", str(args["job_id"])])


def _tool_scancel(args: dict[str, Any]) -> dict[str, Any]:
    return _run_cmd(["scancel", str(args["job_id"])])


def _tool_tail_file(args: dict[str, Any]) -> dict[str, Any]:
    path = Path(args["path"]).expanduser().resolve()
    return {
        "returncode": 0,
        "path": str(path),
        "stdout": _tail(path, lines=int(args.get("lines", 200))),
        "stderr": "",
    }


def _tool_show_latest_snakemake_log(args: dict[str, Any]) -> dict[str, Any]:
    cfg = load_pipeline_config(args["config_path"])
    logs_root = Path(cfg["_meta"]["project_root"]) / ".snakemake" / "log"
    candidates = sorted(logs_root.glob("*.snakemake.log"))
    if not candidates:
        return {"returncode": 1, "stdout": "", "stderr": f"未找到日志目录或日志文件: {logs_root}"}
    latest = candidates[-1]
    return {
        "returncode": 0,
        "path": str(latest),
        "stdout": _tail(latest, lines=int(args.get("lines", 200))),
        "stderr": "",
    }


def tool_registry() -> dict[str, ChatTool]:
    tools = [
        ChatTool(
            name="gmv_validate",
            description="Validate GMV config, samples, database paths, and container mapping.",
            risk="low",
            schema={
                "type": "object",
                "properties": {
                    "config_path": {"type": "string"},
                    "input_dir": {"type": "string"},
                    "sample_sheet": {"type": "string"},
                    "pair_r1": {"type": "string"},
                    "pair_r2": {"type": "string"},
                    "host": {"type": "string"},
                    "strict": {"type": "boolean"},
                },
                "required": ["config_path"],
            },
            handler=_tool_validate,
        ),
        ChatTool(
            name="gmv_run",
            description="Run Snakemake workflow for stage upstream|project|all in local or slurm profile.",
            risk="high",
            schema={
                "type": "object",
                "properties": {
                    "config_path": {"type": "string"},
                    "profile": {"type": "string", "enum": ["local", "slurm"]},
                    "stage": {"type": "string", "enum": ["upstream", "project", "all"]},
                    "cores": {"type": "integer"},
                    "dry_run": {"type": "boolean"},
                    "input_dir": {"type": "string"},
                    "sample_sheet": {"type": "string"},
                    "pair_r1": {"type": "string"},
                    "pair_r2": {"type": "string"},
                    "host": {"type": "string"},
                },
                "required": ["config_path"],
            },
            handler=_tool_run,
        ),
        ChatTool(
            name="gmv_report",
            description="Generate manuscript-ready report package from existing run outputs.",
            risk="low",
            schema={
                "type": "object",
                "properties": {
                    "config_path": {"type": "string"},
                    "run_id": {"type": "string"},
                },
                "required": ["config_path"],
            },
            handler=_tool_report,
        ),
        ChatTool(
            name="slurm_squeue",
            description="Read SLURM queue overview.",
            risk="low",
            schema={
                "type": "object",
                "properties": {
                    "user": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            handler=_tool_squeue,
        ),
        ChatTool(
            name="slurm_sacct",
            description="Read SLURM accounting metrics for a job.",
            risk="low",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["job_id"],
            },
            handler=_tool_sacct,
        ),
        ChatTool(
            name="slurm_scontrol_show_job",
            description="Read detailed SLURM job state.",
            risk="low",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                },
                "required": ["job_id"],
            },
            handler=_tool_scontrol,
        ),
        ChatTool(
            name="slurm_scancel",
            description="Cancel a SLURM job.",
            risk="high",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                },
                "required": ["job_id"],
            },
            handler=_tool_scancel,
        ),
        ChatTool(
            name="tail_file",
            description="Tail text file for troubleshooting.",
            risk="low",
            schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "lines": {"type": "integer"},
                },
                "required": ["path"],
            },
            handler=_tool_tail_file,
        ),
        ChatTool(
            name="show_latest_snakemake_log",
            description="Show tail of latest .snakemake log.",
            risk="low",
            schema={
                "type": "object",
                "properties": {
                    "config_path": {"type": "string"},
                    "lines": {"type": "integer"},
                },
                "required": ["config_path"],
            },
            handler=_tool_show_latest_snakemake_log,
        ),
    ]
    return {tool.name: tool for tool in tools}


def openai_tool_schemas() -> list[dict[str, Any]]:
    schemas = []
    for tool in tool_registry().values():
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.schema,
                },
            }
        )
    return schemas


def parse_tool_arguments(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"tool arguments 不是合法 JSON: {raw}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments 必须是 JSON object")
    return parsed
