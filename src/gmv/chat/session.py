from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import load_llm_settings, load_pipeline_config
from .llm import LLMError, chat_completion
from .tools import openai_tool_schemas, parse_tool_arguments, tool_registry


SYSTEM_PROMPT = """你是 GMV ChatOps 助手。必须只通过提供的 tools 执行动作。
默认输出中文。高风险动作需要用户确认。
高风险动作: gmv_run(非dry_run) 与 slurm_scancel。"""


@dataclass
class ChatOptions:
    config_path: str
    message: str | None
    auto_approve: bool
    max_steps: int
    log_dir: str | None
    base_url: str | None
    model: str | None
    api_key_env: str | None
    llm_config: str | None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_high_risk(tool_name: str, tool_args: dict[str, Any]) -> bool:
    if tool_name == "slurm_scancel":
        return True
    if tool_name == "gmv_run" and not bool(tool_args.get("dry_run", False)):
        return True
    return False


def _default_log_dir(config_path: str) -> Path:
    cfg = load_pipeline_config(config_path)
    run_id = cfg["execution"]["run_id"]
    return Path(cfg["execution"]["results_dir"]) / run_id / "agent" / "chat"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _truncate(text: str, max_chars: int = 20_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _mock_tool_calls(message: str, config_path: str) -> list[dict[str, Any]]:
    lower = message.lower()
    if "validate" in lower or "校验" in lower:
        return [{"name": "gmv_validate", "arguments": {"config_path": config_path, "strict": False}}]
    if "dry" in lower or "dry-run" in lower:
        return [
            {
                "name": "gmv_run",
                "arguments": {
                    "config_path": config_path,
                    "stage": "all",
                    "profile": "local",
                    "dry_run": True,
                },
            }
        ]
    if "report" in lower or "报告" in lower:
        return [{"name": "gmv_report", "arguments": {"config_path": config_path}}]
    return [{"name": "gmv_validate", "arguments": {"config_path": config_path, "strict": False}}]


def _ask_confirm(tool_name: str, tool_args: dict[str, Any], non_interactive: bool, auto_approve: bool) -> bool:
    if auto_approve:
        return True
    if not _is_high_risk(tool_name, tool_args):
        return True
    if non_interactive:
        return False
    preview = json.dumps(tool_args, ensure_ascii=False, sort_keys=True)
    answer = input(f"[GMV] 高风险动作确认: {tool_name} {preview}\n继续执行? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _execute_tool(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    registry = tool_registry()
    if tool_name not in registry:
        return {"returncode": 1, "stderr": f"未知工具: {tool_name}", "stdout": ""}
    try:
        return registry[tool_name].handler(tool_args)
    except SystemExit as exc:
        return {"returncode": int(exc.code), "stderr": f"SystemExit: {exc.code}", "stdout": ""}
    except Exception as exc:  # noqa: BLE001
        return {"returncode": 1, "stderr": str(exc), "stdout": ""}


def _tool_result_for_llm(tool_name: str, result: dict[str, Any]) -> str:
    payload = {
        "tool": tool_name,
        "returncode": result.get("returncode", 1),
        "stdout": _truncate(str(result.get("stdout", ""))),
        "stderr": _truncate(str(result.get("stderr", ""))),
    }
    extra = {k: v for k, v in result.items() if k not in {"stdout", "stderr"}}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _extract_json_tool_command(text: str) -> tuple[str, dict[str, Any]] | None:
    text = text.strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    tool_name = parsed.get("tool")
    args = parsed.get("args", {})
    if isinstance(tool_name, str) and isinstance(args, dict):
        return tool_name, args
    return None


def _interactive_loop(options: ChatOptions) -> int:
    while True:
        try:
            message = input("gmv> ").strip()
        except EOFError:
            print()
            return 0
        if not message:
            continue
        if message in {"exit", "quit", ":q"}:
            return 0
        code = run_single_message(options, message=message)
        if code != 0:
            return code


def run_single_message(options: ChatOptions, message: str | None = None) -> int:
    non_interactive = message is not None
    user_message = message or options.message or ""
    if not user_message:
        print("缺少 message")
        return 2

    log_root = Path(options.log_dir).expanduser().resolve() if options.log_dir else _default_log_dir(options.config_path)
    log_root.mkdir(parents=True, exist_ok=True)
    log_file = log_root / f"chat.{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"

    _append_jsonl(
        log_file,
        {
            "timestamp": _now_iso(),
            "role": "user",
            "content": user_message,
        },
    )

    if os.environ.get("GMV_CHAT_MOCK"):
        calls = _mock_tool_calls(user_message, options.config_path)
        for call in calls:
            tool_name = call["name"]
            tool_args = call["arguments"]
            if not _ask_confirm(tool_name, tool_args, non_interactive, options.auto_approve):
                print(f"高风险动作需要确认: {tool_name}")
                return 3
            result = _execute_tool(tool_name, tool_args)
            _append_jsonl(
                log_file,
                {
                    "timestamp": _now_iso(),
                    "role": "tool",
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "returncode": result.get("returncode", 1),
                    "stdout_tail": _truncate(str(result.get("stdout", ""))),
                    "stderr_tail": _truncate(str(result.get("stderr", ""))),
                },
            )
            print(json.dumps({"tool": tool_name, **result}, ensure_ascii=False, indent=2))
            if result.get("returncode", 1) != 0:
                return int(result.get("returncode", 1))
        return 0

    try:
        llm_settings = load_llm_settings(
            llm_config_path=options.llm_config,
            base_url=options.base_url,
            model=options.model,
            api_key_env=options.api_key_env,
            require_api_key=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"加载 LLM 配置失败: {exc}")
        return 2

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    tool_schemas = openai_tool_schemas()
    registry = tool_registry()

    for _ in range(options.max_steps):
        try:
            reply = chat_completion(llm_settings, messages, tools=tool_schemas)
        except LLMError as exc:
            print(f"LLM 调用失败: {exc}")
            return 2

        content = reply.get("content", "") or ""
        tool_calls = reply.get("tool_calls", []) or []

        if content:
            _append_jsonl(log_file, {"timestamp": _now_iso(), "role": "assistant", "content": content})

        if not tool_calls:
            maybe_json = _extract_json_tool_command(content)
            if maybe_json:
                tool_calls = [
                    {
                        "id": "fallback-json",
                        "name": maybe_json[0],
                        "arguments": json.dumps(maybe_json[1], ensure_ascii=False),
                    }
                ]
            else:
                print(content)
                return 0

        messages.append({"role": "assistant", "content": content, "tool_calls": reply.get("raw", {}).get("choices", [{}])[0].get("message", {}).get("tool_calls", [])})

        for call in tool_calls:
            tool_name = call.get("name", "")
            try:
                tool_args = parse_tool_arguments(call.get("arguments", "{}"))
            except ValueError as exc:
                print(f"工具参数解析失败: {exc}")
                return 2

            if tool_name not in registry:
                print(f"未知工具: {tool_name}")
                return 2

            if "config_path" in registry[tool_name].schema.get("required", []) and "config_path" not in tool_args:
                tool_args["config_path"] = options.config_path

            if not _ask_confirm(tool_name, tool_args, non_interactive, options.auto_approve):
                print(f"高风险动作需要确认: {tool_name}")
                return 3

            result = _execute_tool(tool_name, tool_args)
            tool_text = _tool_result_for_llm(tool_name, result)

            _append_jsonl(
                log_file,
                {
                    "timestamp": _now_iso(),
                    "role": "tool",
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "returncode": result.get("returncode", 1),
                    "stdout_tail": _truncate(str(result.get("stdout", ""))),
                    "stderr_tail": _truncate(str(result.get("stderr", ""))),
                },
            )

            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "name": tool_name, "content": tool_text})

            if result.get("returncode", 1) != 0:
                print(tool_text)
                return int(result.get("returncode", 1))

    print("达到最大步骤上限，已停止。")
    return 4


def run_chat(options: ChatOptions) -> int:
    if options.message:
        return run_single_message(options, options.message)
    return _interactive_loop(options)


def chat_options_from_args(args: Any) -> ChatOptions:
    return ChatOptions(
        config_path=str(Path(args.config).expanduser().resolve()),
        message=args.message,
        auto_approve=bool(args.auto_approve),
        max_steps=int(args.max_steps),
        log_dir=args.log_dir,
        base_url=args.base_url,
        model=args.model,
        api_key_env=args.api_key_env,
        llm_config=args.llm_config,
    )
