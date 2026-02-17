from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any


class LLMError(RuntimeError):
    """Raised when LLM API request fails."""


def _extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls = []
    for item in message.get("tool_calls", []) or []:
        fn = item.get("function", {})
        calls.append(
            {
                "id": item.get("id", ""),
                "name": fn.get("name", ""),
                "arguments": fn.get("arguments", "{}"),
            }
        )
    return calls


def chat_completion(
    settings: dict[str, Any],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    url = f"{settings['base_url'].rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings["model"],
        "messages": messages,
        "temperature": 0.1,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings['api_key']}",
    }

    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    context = None
    if not settings.get("verify_tls", True):
        context = ssl._create_unverified_context()  # noqa: SLF001

    try:
        with urllib.request.urlopen(request, timeout=int(settings.get("timeout_s", 60)), context=context) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"LLM HTTPError {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"LLM URLError: {exc}") from exc

    parsed = json.loads(body)
    if not parsed.get("choices"):
        raise LLMError("LLM response missing choices")

    message = parsed["choices"][0].get("message", {})
    return {
        "content": message.get("content", ""),
        "tool_calls": _extract_tool_calls(message),
        "raw": parsed,
    }
