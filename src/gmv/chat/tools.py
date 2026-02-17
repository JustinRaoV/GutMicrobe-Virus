"""Whitelisted ChatOps tools and argument sanitization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional


def _safe_token(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if any(ch in text for ch in [";", "|", ">", "<", "&"]):
        raise ValueError(f"不安全参数: {name} 包含 shell 元字符: {text!r}")
    return text


def _safe_int(name: str, value: Any, *, min_value: int, max_value: int) -> int:
    try:
        n = int(value)
    except Exception as exc:
        raise ValueError(f"不合法整数: {name}={value!r}") from exc
    if n < min_value or n > max_value:
        raise ValueError(f"不合法范围: {name}={n}（允许 {min_value}..{max_value}）")
    return n


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Mapping[str, Any]
    risk: Callable[[Mapping[str, Any]], str]


def _risk_low(_args: Mapping[str, Any]) -> str:
    return "low"


def _risk_run(args: Mapping[str, Any]) -> str:
    return "low" if bool(args.get("dry_run", False)) else "high"


def _risk_high(_args: Mapping[str, Any]) -> str:
    return "high"


TOOL_SPECS: Dict[str, ToolSpec] = {
    "gmv_validate": ToolSpec(
        name="gmv_validate",
        description="运行 gmv validate 进行环境与配置检查。",
        parameters={
            "type": "object",
            "properties": {
                "config_path": {"type": "string"},
                "strict": {"type": "boolean", "default": False},
            },
            "required": ["config_path"],
            "additionalProperties": False,
        },
        risk=_risk_low,
    ),
    "gmv_run": ToolSpec(
        name="gmv_run",
        description="运行 gmv run（支持 stage/profile/cores；非 dry-run 高风险）。",
        parameters={
            "type": "object",
            "properties": {
                "config_path": {"type": "string"},
                "profile": {"type": "string", "enum": ["local", "slurm"]},
                "stage": {"type": "string", "enum": ["upstream", "project", "all"], "default": "all"},
                "cores": {"type": ["integer", "null"], "default": None},
                "dry_run": {"type": "boolean", "default": False},
                "needs_confirmation": {"type": "boolean", "default": False},
            },
            "required": ["config_path", "profile"],
            "additionalProperties": False,
        },
        risk=_risk_run,
    ),
    "gmv_report": ToolSpec(
        name="gmv_report",
        description="运行 gmv report 生成报告。",
        parameters={
            "type": "object",
            "properties": {
                "config_path": {"type": "string"},
                "run_id": {"type": ["string", "null"], "default": None},
            },
            "required": ["config_path"],
            "additionalProperties": False,
        },
        risk=_risk_low,
    ),
    "slurm_squeue": ToolSpec(
        name="slurm_squeue",
        description="查询 SLURM 队列（squeue）。",
        parameters={
            "type": "object",
            "properties": {
                "user": {"type": ["string", "null"], "default": None},
                "name": {"type": ["string", "null"], "default": None},
                "states": {"type": ["string", "null"], "default": None},
                "limit": {"type": "integer", "default": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        risk=_risk_low,
    ),
    "slurm_sacct": ToolSpec(
        name="slurm_sacct",
        description="查询 SLURM 账务统计（sacct）。",
        parameters={
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        risk=_risk_low,
    ),
    "slurm_scontrol_show_job": ToolSpec(
        name="slurm_scontrol_show_job",
        description="查看 SLURM 作业详情（scontrol show job）。",
        parameters={
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        risk=_risk_low,
    ),
    "slurm_scancel": ToolSpec(
        name="slurm_scancel",
        description="取消 SLURM 作业（高风险）。",
        parameters={
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "needs_confirmation": {"type": "boolean", "default": True},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        risk=_risk_high,
    ),
    "tail_file": ToolSpec(
        name="tail_file",
        description="读取文件末尾 N 行。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "lines": {"type": "integer", "default": 200},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        risk=_risk_low,
    ),
    "show_latest_snakemake_log": ToolSpec(
        name="show_latest_snakemake_log",
        description="显示最近一次 snakemake 日志的末尾内容。",
        parameters={
            "type": "object",
            "properties": {"lines": {"type": "integer", "default": 200}},
            "additionalProperties": False,
        },
        risk=_risk_low,
    ),
}


def openai_tools() -> List[Mapping[str, Any]]:
    out: List[Mapping[str, Any]] = []
    for spec in TOOL_SPECS.values():
        out.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": dict(spec.parameters),
                },
            }
        )
    return sorted(out, key=lambda item: item["function"]["name"])


def tool_risk(tool_name: str, args: Mapping[str, Any]) -> str:
    spec = TOOL_SPECS.get(tool_name)
    if not spec:
        return "high"
    try:
        return str(spec.risk(args))
    except Exception:
        return "high"


def sanitize_args(tool_name: str, args: Mapping[str, Any]) -> Dict[str, Any]:
    clean = dict(args or {})

    if tool_name == "gmv_run":
        clean["config_path"] = _safe_token("config_path", clean.get("config_path")) or ""
        clean["profile"] = _safe_token("profile", clean.get("profile")) or "local"
        clean["stage"] = _safe_token("stage", clean.get("stage")) or "all"
        if clean.get("cores") is not None:
            clean["cores"] = _safe_int("cores", clean["cores"], min_value=1, max_value=10_000)

    if tool_name == "gmv_validate" or tool_name == "gmv_report":
        clean["config_path"] = _safe_token("config_path", clean.get("config_path")) or ""

    if tool_name == "slurm_squeue":
        clean["user"] = _safe_token("user", clean.get("user"))
        clean["name"] = _safe_token("name", clean.get("name"))
        clean["states"] = _safe_token("states", clean.get("states"))
        clean["limit"] = _safe_int("limit", clean.get("limit", 50), min_value=1, max_value=500)

    if tool_name in {"slurm_sacct", "slurm_scontrol_show_job", "slurm_scancel"}:
        clean["job_id"] = _safe_token("job_id", clean.get("job_id")) or ""

    if tool_name == "tail_file":
        clean["path"] = _safe_token("path", clean.get("path")) or ""
        clean["lines"] = _safe_int("lines", clean.get("lines", 200), min_value=1, max_value=2000)

    if tool_name == "show_latest_snakemake_log":
        clean["lines"] = _safe_int("lines", clean.get("lines", 200), min_value=1, max_value=2000)

    return clean
