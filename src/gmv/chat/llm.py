"""OpenAI-compatible Chat Completions client (stdlib only)."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urljoin

from gmv.config import LLMConfig


@dataclass(frozen=True)
class ChatCompletionResponse:
    raw: Dict[str, Any]

    def assistant_message(self) -> Dict[str, Any]:
        choices = self.raw.get("choices") or []
        if not choices:
            return {"role": "assistant", "content": ""}
        msg = (choices[0] or {}).get("message") or {}
        return msg if isinstance(msg, dict) else {"role": "assistant", "content": ""}


def _build_chat_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return normalized + "/chat/completions"
    return urljoin(normalized + "/", "chat/completions").rstrip("/")


def chat_completions(
    *,
    settings: LLMConfig,
    messages: List[Mapping[str, Any]],
    tools: Optional[List[Mapping[str, Any]]] = None,
    tool_choice: Optional[Any] = "auto",
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> ChatCompletionResponse:
    url = _build_chat_url(settings.base_url)
    payload: Dict[str, Any] = {
        "model": settings.model,
        "messages": list(messages),
        "temperature": float(temperature),
    }
    if tools:
        payload["tools"] = list(tools)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.api_key}",
    }

    context = None
    if not settings.verify_tls:
        context = ssl._create_unverified_context()  # noqa: SLF001 - user opted out.

    req = urllib.request.Request(url=url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=settings.timeout_s, context=context) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body.strip() else {}
            if not isinstance(parsed, dict):
                raise RuntimeError(f"LLM 返回非 JSON 对象: {type(parsed)}")
            return ChatCompletionResponse(raw=parsed)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise RuntimeError(f"LLM HTTPError {exc.code}: {body[:2000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM URLError: {exc}") from exc
