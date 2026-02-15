"""Chat session runner for GMV ChatOps."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from gmv.agent.chat.executor import ToolResult, execute_tool
from gmv.agent.chat.tools import openai_tools
from gmv.ai.openai_compatible import chat_completions
from gmv.ai.settings import LLMSettings, load_llm_settings
from gmv.config_schema import load_pipeline_config


@dataclass(frozen=True)
class ChatRunResult:
    returncode: int
    audit_log: str


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_log_dir(config: Mapping[str, Any], repo_root: Path) -> Path:
    run_id = str(config.get("execution", {}).get("run_id", "default-run"))
    results_dir = str(config.get("execution", {}).get("results_dir", "results"))
    p = Path(results_dir)
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    return p / run_id / "agent" / "chat"


def _write_audit_line(fp: Path, payload: Mapping[str, Any]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _mock_llm(messages: List[Mapping[str, Any]], *, config_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Offline mock model for tests: one tool-call, then a final summary."""
    last = messages[-1] if messages else {}
    role = str(last.get("role") or "")
    content = str(last.get("content") or "")

    if role == "tool":
        return ("已完成（mock）。", [])

    t = content.lower()
    if role == "user" and ("validate" in t or "校验" in content):
        return (
            "OK，我将先校验配置。",
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

    return ("我暂时只能处理 validate 示例（mock）。", [])


def _parse_tool_calls(msg: Mapping[str, Any]) -> List[Dict[str, Any]]:
    tool_calls = msg.get("tool_calls") or []
    if isinstance(tool_calls, list):
        return [tc for tc in tool_calls if isinstance(tc, dict)]
    # Older field name.
    fc = msg.get("function_call")
    if isinstance(fc, dict) and "name" in fc:
        return [{"id": "legacy_call_1", "type": "function", "function": fc}]
    # Fallback: JSON directive parsing from assistant content
    content = msg.get("content")
    if not isinstance(content, str):
        return []
    text = content.strip()
    if "tool" not in text and "tool_calls" not in text:
        return []

    def try_json(s: str) -> Optional[Any]:
        try:
            return json.loads(s)
        except Exception:
            return None

    # Try fenced json first
    if text.startswith("```"):
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i].strip()
            if block.lower().startswith("json"):
                block = block[4:].lstrip()
            obj = try_json(block)
            if obj is not None:
                text = block
                break

    obj = try_json(text)
    if obj is None:
        return []

    if isinstance(obj, dict) and isinstance(obj.get("tool_calls"), list):
        return [tc for tc in obj["tool_calls"] if isinstance(tc, dict)]

    # Single-tool format: {"tool": "...", "args": {...}}
    if isinstance(obj, dict) and ("tool" in obj or "tool_name" in obj):
        name = obj.get("tool") or obj.get("tool_name")
        args = obj.get("args") or obj.get("tool_args") or {}
        try:
            args_json = json.dumps(args, ensure_ascii=False)
        except Exception:
            args_json = "{}"
        return [{"id": "json_call_1", "type": "function", "function": {"name": str(name), "arguments": args_json}}]

    if isinstance(obj, list):
        calls: List[Dict[str, Any]] = []
        for idx, item in enumerate(obj, start=1):
            if not isinstance(item, dict):
                continue
            name = item.get("tool") or item.get("tool_name")
            args = item.get("args") or item.get("tool_args") or {}
            if not name:
                continue
            try:
                args_json = json.dumps(args, ensure_ascii=False)
            except Exception:
                args_json = "{}"
            calls.append({"id": f"json_call_{idx}", "type": "function", "function": {"name": str(name), "arguments": args_json}})
        return calls
    return []


def _system_prompt() -> str:
    return (
        "你是 GMV ChatOps 助手。你只能通过系统提供的工具（tools）执行动作，不能编造执行结果。"
        "涉及高风险动作（如提交运行或 scancel）必须请求确认。默认用中文回答。"
    )


def _render_tool_summary(tool_name: str, result: ToolResult) -> str:
    lines = [
        f"[tool] {tool_name} rc={result.returncode}",
    ]
    if result.stdout_tail:
        lines.append("[stdout_tail]")
        lines.append(result.stdout_tail)
    if result.stderr_tail:
        lines.append("[stderr_tail]")
        lines.append(result.stderr_tail)
    if result.artifact_paths:
        lines.append("[artifacts]")
        lines.extend(result.artifact_paths)
    return "\n".join(lines).strip() + "\n"


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
    repo_root = _repo_root()
    cfg = load_pipeline_config(config_path)
    session_log_dir = Path(log_dir).expanduser().resolve() if log_dir else _default_log_dir(cfg, repo_root)
    session_log_dir.mkdir(parents=True, exist_ok=True)

    audit_file = session_log_dir / f"chat.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"

    # LLM settings (skip key requirement in mock mode).
    settings: Optional[LLMSettings] = None
    if os.environ.get("GMV_CHAT_MOCK", "").strip() != "1":
        settings = load_llm_settings(base_url=base_url, model=model, api_key_env=api_key_env, llm_config=llm_config)

    tools = openai_tools()
    messages: List[Dict[str, Any]] = [{"role": "system", "content": _system_prompt()}]
    _write_audit_line(audit_file, {"timestamp": _utc_iso(), "role": "system", "content": messages[0]["content"]})

    dry_run_tools = os.environ.get("GMV_CHAT_MOCK", "").strip() == "1" or os.environ.get("GMV_CHAT_DRY_RUN_TOOLS", "").strip() == "1"

    def handle_user_turn(user_text: str, *, interactive: bool) -> int:
        messages.append({"role": "user", "content": user_text})
        _write_audit_line(audit_file, {"timestamp": _utc_iso(), "role": "user", "content": user_text})

        for _step in range(max_steps):
            if os.environ.get("GMV_CHAT_MOCK", "").strip() == "1":
                assistant_text, tool_calls = _mock_llm(messages, config_path=config_path)
                assistant_msg = {"role": "assistant", "content": assistant_text, "tool_calls": tool_calls}
            else:
                resp = chat_completions(settings=settings, messages=messages, tools=tools, tool_choice="auto")
                assistant_msg = resp.assistant_message()
            assistant_content = str(assistant_msg.get("content") or "")
            tool_calls = _parse_tool_calls(assistant_msg)

            messages.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls} if tool_calls else {"role": "assistant", "content": assistant_content})
            _write_audit_line(audit_file, {"timestamp": _utc_iso(), "role": "assistant", "content": assistant_content, "tool_calls": tool_calls})

            if assistant_content:
                print(assistant_content)

            if not tool_calls:
                return 0

            # Execute each tool call and feed back results.
            for tc in tool_calls:
                fn = (tc.get("function") or {}) if isinstance(tc.get("function"), dict) else {}
                tool_name = str(fn.get("name") or "")
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except Exception:
                    args = {}

                _write_audit_line(audit_file, {"timestamp": _utc_iso(), "role": "tool", "tool_name": tool_name, "tool_args": args})
                result = execute_tool(
                    tool_name,
                    args,
                    config_path=config_path,
                    auto_approve=auto_approve,
                    interactive=interactive,
                    dry_run_tools=dry_run_tools,
                    log_dir=session_log_dir,
                )
                summary = _render_tool_summary(tool_name, result)
                print(summary)
                _write_audit_line(
                    audit_file,
                    {
                        "timestamp": _utc_iso(),
                        "role": "tool",
                        "tool_name": tool_name,
                        "tool_args": args,
                        "returncode": result.returncode,
                        "stdout_tail": result.stdout_tail,
                        "stderr_tail": result.stderr_tail,
                        "artifact_paths": result.artifact_paths,
                    },
                )

                # Feed tool results back to LLM (OpenAI "tool" role).
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tc.get("id") or ""),
                        "name": tool_name,
                        "content": result.content_for_llm,
                    }
                )

                if result.returncode == 3 and not auto_approve and not interactive:
                    # blocked by confirmation in non-interactive mode
                    return 3

            # Continue loop to let LLM summarize / decide next tool call.
        return 1

    if message is not None:
        rc = handle_user_turn(message, interactive=False)
        return ChatRunResult(returncode=rc, audit_log=str(audit_file))

    # Interactive REPL
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
        _ = handle_user_turn(user_text, interactive=True)

    return ChatRunResult(returncode=0, audit_log=str(audit_file))
