"""LLM settings loader for GMV ChatOps.

Precedence (highest to lowest):
1) CLI overrides
2) Environment variables
3) ~/.config/gmv/llm.yaml (or --llm-config)
4) Built-in defaults

By default, the API key is read from an environment variable and is not stored on disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    model: str
    api_key_env: str
    api_key: str
    timeout_s: int
    verify_tls: bool

    def masked_api_key(self) -> str:
        k = self.api_key or ""
        if not k:
            return ""
        if len(k) <= 8:
            return "*" * len(k)
        return f"{k[:4]}...{k[-4:]}"


DEFAULTS = {
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key_env": "GMV_API_KEY",
    "timeout_s": 60,
    "verify_tls": True,
}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _env(name: str) -> Optional[str]:
    v = os.environ.get(name)
    return v if (v is not None and str(v).strip() != "") else None


def load_llm_settings(
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key_env: Optional[str] = None,
    llm_config: Optional[str] = None,
) -> LLMSettings:
    cfg_path = Path(llm_config or "~/.config/gmv/llm.yaml").expanduser()
    file_cfg: Mapping[str, Any] = _read_yaml(cfg_path)

    # Defaults -> file -> env -> cli
    api_key_env_final = (
        api_key_env
        or _env("GMV_API_KEY_ENV")
        or str(file_cfg.get("api_key_env") or DEFAULTS["api_key_env"])
    )
    base_url_final = base_url or _env("GMV_BASE_URL") or str(file_cfg.get("base_url") or DEFAULTS["base_url"])
    model_final = model or _env("GMV_MODEL") or str(file_cfg.get("model") or DEFAULTS["model"])

    timeout_raw = _env("GMV_TIMEOUT_S") or file_cfg.get("timeout_s") or DEFAULTS["timeout_s"]
    try:
        timeout_s_final = int(timeout_raw)
    except Exception:
        timeout_s_final = int(DEFAULTS["timeout_s"])
    timeout_s_final = max(1, timeout_s_final)

    verify_tls_raw = file_cfg.get("verify_tls")
    verify_tls_final = bool(DEFAULTS["verify_tls"] if verify_tls_raw is None else verify_tls_raw)

    # API key: env wins, but allow file as a last resort (with warning elsewhere).
    api_key = _env("GMV_API_KEY") if api_key_env_final == "GMV_API_KEY" else _env(api_key_env_final)
    if not api_key:
        api_key = str(file_cfg.get("api_key") or "").strip()

    # In mock mode we allow missing keys (offline tests).
    if not api_key and os.environ.get("GMV_CHAT_MOCK", "").strip() != "1":
        raise ValueError(
            f"缺少 API key：请设置环境变量 {api_key_env_final}=... "
            f"或在 {cfg_path} 中配置 api_key（不推荐，易泄漏）。"
        )

    return LLMSettings(
        base_url=base_url_final.rstrip("/"),
        model=model_final,
        api_key_env=api_key_env_final,
        api_key=api_key,
        timeout_s=timeout_s_final,
        verify_tls=verify_tls_final,
    )

