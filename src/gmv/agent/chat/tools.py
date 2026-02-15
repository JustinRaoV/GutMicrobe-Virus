"""Tool registry for GMV ChatOps.

This file defines:
- The OpenAI tool schemas exposed to the LLM (function-calling).
- Risk classification (low/high) per tool and arguments.
- Argument sanitization for user-supplied fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional


def _safe_token(name: str, v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v)
    # Even though we never use `shell=True`, reject obvious shell metacharacters to keep
    # "arg injection" style surprises away from ops commands.
    if any(ch in s for ch in [";", "|", ">", "<", "&"]):
        raise ValueError(f"不安全参数: {name} 包含 shell 元字符: {s!r}")
    return s


def _safe_int(name: str, v: Any, *, min_value: int, max_value: int) -> int:
    try:
        n = int(v)
    except Exception as exc:
        raise ValueError(f"不合法整数: {name}={v!r}") from exc
    if n < min_value or n > max_value:
        raise ValueError(f"不合法范围: {name}={n}（允许 {min_value}..{max_value}）")
    return n


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Mapping[str, Any]
    risk: Callable[[Mapping[str, Any]], str]  # returns "low" or "high"


def _risk_always_low(_args: Mapping[str, Any]) -> str:
    return "low"


def _risk_gmv_run(args: Mapping[str, Any]) -> str:
    # Only dry-run is considered low risk.
    return "low" if bool(args.get("dry_run", False)) else "high"


def _risk_always_high(_args: Mapping[str, Any]) -> str:
    return "high"


TOOL_SPECS: Dict[str, ToolSpec] = {
    "gmv_validate": ToolSpec(
        name="gmv_validate",
        description="运行 `gmv validate` 校验配置/容器/数据库/环境。",
        parameters={
            "type": "object",
            "properties": {
                "config_path": {"type": "string"},
                "strict": {"type": "boolean", "default": False},
            },
            "required": ["config_path"],
            "additionalProperties": False,
        },
        risk=_risk_always_low,
    ),
    "gmv_run": ToolSpec(
        name="gmv_run",
        description="运行 `gmv run`（可 dry-run、可指定 stage/profile/cores）。注意：非 dry-run 属于高风险执行。",
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
        risk=_risk_gmv_run,
    ),
    "gmv_report": ToolSpec(
        name="gmv_report",
        description="运行 `gmv report` 生成报告产物。",
        parameters={
            "type": "object",
            "properties": {
                "config_path": {"type": "string"},
                "run_id": {"type": ["string", "null"], "default": None},
            },
            "required": ["config_path"],
            "additionalProperties": False,
        },
        risk=_risk_always_low,
    ),
    "gmv_agent_harvest": ToolSpec(
        name="gmv_agent_harvest",
        description="运行 `gmv agent harvest`（可选使用 sacct）生成 resources_overrides.yaml 建议。",
        parameters={
            "type": "object",
            "properties": {
                "config_path": {"type": "string"},
                "run_id": {"type": ["string", "null"], "default": None},
                "snakemake_log": {"type": ["string", "null"], "default": None},
            },
            "required": ["config_path"],
            "additionalProperties": False,
        },
        risk=_risk_always_low,
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
        risk=_risk_always_low,
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
        risk=_risk_always_low,
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
        risk=_risk_always_low,
    ),
    "slurm_scancel": ToolSpec(
        name="slurm_scancel",
        description="取消 SLURM 作业（scancel，高风险）。",
        parameters={
            "type": "object",
            "properties": {"job_id": {"type": "string"}, "needs_confirmation": {"type": "boolean", "default": True}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        risk=_risk_always_high,
    ),
    "tail_file": ToolSpec(
        name="tail_file",
        description="读取文件末尾 N 行（只读）。",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}, "lines": {"type": "integer", "default": 200}},
            "required": ["path"],
            "additionalProperties": False,
        },
        risk=_risk_always_low,
    ),
    "show_latest_snakemake_log": ToolSpec(
        name="show_latest_snakemake_log",
        description="显示最近一次 snakemake log 的末尾内容（只读）。",
        parameters={"type": "object", "properties": {"lines": {"type": "integer", "default": 200}}, "additionalProperties": False},
        risk=_risk_always_low,
    ),
}


def openai_tools() -> List[Mapping[str, Any]]:
    tools = []
    for spec in TOOL_SPECS.values():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": dict(spec.parameters),
                },
            }
        )
    # Keep order deterministic.
    return sorted(tools, key=lambda x: x["function"]["name"])


def tool_risk(tool_name: str, args: Mapping[str, Any]) -> str:
    spec = TOOL_SPECS.get(tool_name)
    if not spec:
        return "high"
    try:
        return str(spec.risk(args))
    except Exception:
        return "high"


def sanitize_args(tool_name: str, args: Mapping[str, Any]) -> Dict[str, Any]:
    """Best-effort sanitization for user-provided fields."""
    a = dict(args or {})
    if tool_name in {"slurm_squeue"}:
        a["user"] = _safe_token("user", a.get("user"))
        a["name"] = _safe_token("name", a.get("name"))
        a["states"] = _safe_token("states", a.get("states"))
        a["limit"] = _safe_int("limit", a.get("limit", 50), min_value=1, max_value=500)
    if tool_name in {"slurm_sacct", "slurm_scontrol_show_job", "slurm_scancel"}:
        a["job_id"] = _safe_token("job_id", a.get("job_id")) or ""
    if tool_name == "tail_file":
        a["path"] = _safe_token("path", a.get("path")) or ""
        a["lines"] = _safe_int("lines", a.get("lines", 200), min_value=1, max_value=2000)
    if tool_name == "show_latest_snakemake_log":
        a["lines"] = _safe_int("lines", a.get("lines", 200), min_value=1, max_value=2000)
    return a

