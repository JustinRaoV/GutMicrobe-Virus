"""Conversation loop for GMV ChatOps."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from gmv.chat.llm import chat_completions
from gmv.chat.tools import openai_tools, sanitize_args, tool_risk
from gmv.config import LLMConfig, load_llm_config, load_pipeline_config


@dataclass(frozen=True)
class ToolResult:
    returncode: int
    stdout_tail: str
    stderr_tail: str
    artifact_paths: List[str]
    content_for_llm: str


@dataclass(frozen=True)
class ChatRunResult:
    returncode: int
    audit_log: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _tail_text(text: str, *, max_lines: int = 200, max_bytes: int = 20_000) -> str:
    if not text:
        return ""
    b = text.encode("utf-8", errors="replace")
    if len(b) > max_bytes:
        b = b[-max_bytes:]
        text = b.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines)


def _write_audit_line(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_artifact(path: Path, name: str, content: str) -> str:
    path.mkdir(parents=True, exist_ok=True)
    output = path / name
    output.write_text(content, encoding="utf-8", errors="replace")
    return str(output)


def _confirm(prompt: str) -> bool:
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _run_argv(argv: List[str], *, cwd: Path) -> Tuple[int, str, str]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        env=os.environ,
        capture_output=True,
        text=True,
        check=False,
    )
    return int(proc.returncode), str(proc.stdout or ""), str(proc.stderr or "")


def _tail_file(path: Path, *, lines: int) -> str:
    if not path.exists():
        return f"ERROR: file not found: {path}"
    size = path.stat().st_size
    read_bytes = min(size, 1024 * 1024)
    with path.open("rb") as fh:
        if read_bytes < size:
            fh.seek(-read_bytes, 2)
        data = fh.read()
    text = data.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def _parse_tool_calls(message: Mapping[str, Any]) -> List[Dict[str, Any]]:
    tool_calls = message.get("tool_calls") or []
    if isinstance(tool_calls, list):
        return [item for item in tool_calls if isinstance(item, dict)]

    content = message.get("content")
    if not isinstance(content, str):
        return []

    try:
        parsed = json.loads(content)
    except Exception:
        return []

    if isinstance(parsed, dict) and isinstance(parsed.get("tool_calls"), list):
        return [item for item in parsed["tool_calls"] if isinstance(item, dict)]
    return []


def _mock_llm(messages: List[Mapping[str, Any]], *, config_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    last = messages[-1] if messages else {}
    role = str(last.get("role") or "")
    content = str(last.get("content") or "")

    if role == "tool":
        return ("已完成（mock）。", [])

    if role == "user" and ("validate" in content.lower() or "校验" in content):
        return (
            "先执行 validate。",
            [
                {
                    "id": "mock_call_1",
                    "type": "function",
                    "function": {
                        "name": "gmv_validate",
                        "arguments": json.dumps({"config_path": config_path, "strict": False}),
                    },
                }
            ],
        )

    return ("mock 模式当前仅内置 validate 演示。", [])


def _render_tool_result(tool_name: str, result: ToolResult) -> str:
    parts = [f"[tool] {tool_name} rc={result.returncode}"]
    if result.stdout_tail:
        parts.extend(["[stdout_tail]", result.stdout_tail])
    if result.stderr_tail:
        parts.extend(["[stderr_tail]", result.stderr_tail])
    if result.artifact_paths:
        parts.extend(["[artifacts]", *result.artifact_paths])
    return "\n".join(parts)


def _system_prompt() -> str:
    return (
        "你是 GMV ChatOps 助手。你只能通过 tools 执行动作，不能伪造执行结果。"
        "高风险动作必须确认。默认使用中文输出。"
    )


def _execute_tool(
    *,
    tool_name: str,
    args: Mapping[str, Any],
    config_path: str,
    auto_approve: bool,
    interactive: bool,
    dry_run_tools: bool,
    artifacts_dir: Path,
) -> ToolResult:
    cleaned = sanitize_args(tool_name, args)
    risk = tool_risk(tool_name, cleaned)
    repo_root = _repo_root()

    preview = json.dumps({"tool": tool_name, "risk": risk, "args": cleaned}, ensure_ascii=False, indent=2)

    if risk == "high" and not auto_approve:
        if interactive:
            print("检测到高风险动作，需要确认后执行：")
            print(preview)
            if not _confirm("确认执行？[y/N] "):
                return ToolResult(
                    returncode=3,
                    stdout_tail="",
                    stderr_tail="用户取消执行高风险动作",
                    artifact_paths=[],
                    content_for_llm="USER_CANCELLED",
                )
        else:
            artifact = _write_artifact(artifacts_dir, f"tool.{_utc_stamp()}.{tool_name}.preview.json", preview + "\n")
            return ToolResult(
                returncode=3,
                stdout_tail="",
                stderr_tail="需要确认才能执行高风险动作（请使用交互模式或 --auto-approve）",
                artifact_paths=[artifact],
                content_for_llm="NEEDS_CONFIRMATION",
            )

    if tool_name == "tail_file":
        output = _tail_file(Path(str(cleaned.get("path", ""))).expanduser(), lines=int(cleaned.get("lines", 200)))
        return ToolResult(0, _tail_text(output), "", [], output)

    if tool_name == "show_latest_snakemake_log":
        log_dir = repo_root / ".snakemake" / "log"
        logs = sorted(log_dir.glob("*.snakemake.log")) if log_dir.exists() else []
        if not logs:
            output = f"ERROR: no snakemake logs found under {log_dir}"
            return ToolResult(1, _tail_text(output), "", [], output)
        last = logs[-1]
        output = f"==> {last}\n" + _tail_file(last, lines=int(cleaned.get("lines", 200)))
        return ToolResult(0, _tail_text(output), "", [], output)

    if tool_name == "gmv_validate":
        argv = [sys.executable, "-m", "gmv.cli", "validate", "--config", str(cleaned.get("config_path") or config_path)]
        if bool(cleaned.get("strict", False)):
            argv.append("--strict")
    elif tool_name == "gmv_run":
        argv = [
            sys.executable,
            "-m",
            "gmv.cli",
            "run",
            "--config",
            str(cleaned.get("config_path") or config_path),
            "--profile",
            str(cleaned.get("profile") or "local"),
            "--stage",
            str(cleaned.get("stage") or "all"),
        ]
        if bool(cleaned.get("dry_run", False)):
            argv.append("--dry-run")
        if cleaned.get("cores") is not None:
            argv.extend(["--cores", str(int(cleaned["cores"]))])
    elif tool_name == "gmv_report":
        argv = [sys.executable, "-m", "gmv.cli", "report", "--config", str(cleaned.get("config_path") or config_path)]
        if cleaned.get("run_id"):
            argv.extend(["--run-id", str(cleaned["run_id"])])
    elif tool_name == "slurm_squeue":
        argv = ["squeue", "-h", "-o", "%i|%T|%j|%u|%M|%D|%R", "--sort", "i"]
        if cleaned.get("user"):
            argv.extend(["-u", str(cleaned["user"])])
        if cleaned.get("name"):
            argv.extend(["-n", str(cleaned["name"])])
        if cleaned.get("states"):
            argv.extend(["-t", str(cleaned["states"])])
    elif tool_name == "slurm_sacct":
        fields = cleaned.get("fields") or ["JobID", "State", "ExitCode", "ElapsedRaw", "MaxRSS", "ReqMem", "AllocCPUS"]
        argv = ["sacct", "-X", "-P", "-n", "-j", str(cleaned.get("job_id", "")), "-o", ",".join([str(f) for f in fields])]
    elif tool_name == "slurm_scontrol_show_job":
        argv = ["scontrol", "show", "job", str(cleaned.get("job_id", ""))]
    elif tool_name == "slurm_scancel":
        argv = ["scancel", str(cleaned.get("job_id", ""))]
    else:
        return ToolResult(
            returncode=2,
            stdout_tail="",
            stderr_tail=f"未知工具: {tool_name}",
            artifact_paths=[],
            content_for_llm=f"ERROR: unknown tool: {tool_name}",
        )

    if dry_run_tools:
        text = f"DRY_RUN_TOOL: would run argv={argv} cwd={repo_root}"
        artifact = _write_artifact(artifacts_dir, f"tool.{_utc_stamp()}.{tool_name}.dryrun.txt", text + "\n")
        return ToolResult(0, _tail_text(text), "", [artifact], text)

    rc, stdout, stderr = _run_argv(argv, cwd=repo_root)
    artifact_content = f"argv={argv}\n\n--- stdout ---\n{stdout}\n\n--- stderr ---\n{stderr}\n"
    artifact = _write_artifact(artifacts_dir, f"tool.{_utc_stamp()}.{tool_name}.log.txt", artifact_content)
    return ToolResult(
        returncode=rc,
        stdout_tail=_tail_text(stdout),
        stderr_tail=_tail_text(stderr),
        artifact_paths=[artifact],
        content_for_llm=_tail_text(stdout + ("\n" + stderr if stderr else "")),
    )


def run_chat(
    *,
    config_path: str,
    message: Optional[str],
    auto_approve: bool,
    max_steps: int,
    log_dir: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
    api_key_env: Optional[str],
    llm_config: Optional[str],
) -> ChatRunResult:
    config = load_pipeline_config(config_path)
    repo_root = _repo_root()

    run_id = str(config.get("execution", {}).get("run_id", "default-run"))
    default_log_root = Path(config.get("execution", {}).get("results_dir", "results"))
    if not default_log_root.is_absolute():
        default_log_root = (repo_root / default_log_root).resolve()
    default_log_dir = default_log_root / run_id / "agent" / "chat"
    session_dir = Path(log_dir).expanduser().resolve() if log_dir else default_log_dir
    session_dir.mkdir(parents=True, exist_ok=True)

    audit_file = session_dir / f"chat.{_utc_stamp()}.jsonl"
    messages: List[Dict[str, Any]] = [{"role": "system", "content": _system_prompt()}]
    _write_audit_line(audit_file, {"timestamp": _utc_iso(), "role": "system", "content": messages[0]["content"]})

    mock_mode = os.environ.get("GMV_CHAT_MOCK", "").strip() == "1"
    dry_run_tools = mock_mode or os.environ.get("GMV_CHAT_DRY_RUN_TOOLS", "").strip() == "1"

    settings: Optional[LLMConfig] = None
    if not mock_mode:
        settings = load_llm_config(
            base_url=base_url,
            model=model,
            api_key_env=api_key_env,
            llm_config=llm_config,
        )

    tools = openai_tools()

    def handle_turn(user_text: str, *, interactive: bool) -> int:
        messages.append({"role": "user", "content": user_text})
        _write_audit_line(audit_file, {"timestamp": _utc_iso(), "role": "user", "content": user_text})

        for _ in range(max_steps):
            if mock_mode:
                assistant_text, tool_calls = _mock_llm(messages, config_path=config_path)
                assistant_msg: Dict[str, Any] = {"role": "assistant", "content": assistant_text, "tool_calls": tool_calls}
            else:
                response = chat_completions(settings=settings, messages=messages, tools=tools, tool_choice="auto")
                assistant_msg = response.assistant_message()

            assistant_text = str(assistant_msg.get("content") or "")
            tool_calls = _parse_tool_calls(assistant_msg)

            msg_record: Dict[str, Any] = {"role": "assistant", "content": assistant_text}
            if tool_calls:
                msg_record["tool_calls"] = tool_calls
            messages.append(msg_record)
            _write_audit_line(audit_file, {"timestamp": _utc_iso(), "role": "assistant", "content": assistant_text, "tool_calls": tool_calls})

            if assistant_text:
                print(assistant_text)

            if not tool_calls:
                return 0

            for call in tool_calls:
                function_data = call.get("function") if isinstance(call.get("function"), dict) else {}
                tool_name = str(function_data.get("name") or "")
                raw_args = function_data.get("arguments") or "{}"
                try:
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except Exception:
                    parsed_args = {}

                result = _execute_tool(
                    tool_name=tool_name,
                    args=parsed_args,
                    config_path=config_path,
                    auto_approve=auto_approve,
                    interactive=interactive,
                    dry_run_tools=dry_run_tools,
                    artifacts_dir=session_dir,
                )

                summary = _render_tool_result(tool_name, result)
                print(summary)

                _write_audit_line(
                    audit_file,
                    {
                        "timestamp": _utc_iso(),
                        "role": "tool",
                        "content": summary,
                        "tool_name": tool_name,
                        "tool_args": parsed_args,
                        "returncode": result.returncode,
                        "stdout_tail": result.stdout_tail,
                        "stderr_tail": result.stderr_tail,
                        "artifact_paths": result.artifact_paths,
                    },
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id") or ""),
                        "name": tool_name,
                        "content": result.content_for_llm,
                    }
                )

                if result.returncode == 3 and not auto_approve and not interactive:
                    return 3

        return 1

    if message is not None:
        rc = handle_turn(message, interactive=False)
        return ChatRunResult(returncode=rc, audit_log=str(audit_file))

    print("GMV ChatOps (输入 exit/quit 退出)")
    while True:
        try:
            user_text = input("gmv> ").strip()
        except EOFError:
            print("")
            break
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break
        _ = handle_turn(user_text, interactive=True)

    return ChatRunResult(returncode=0, audit_log=str(audit_file))
