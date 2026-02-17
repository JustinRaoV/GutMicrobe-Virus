"""Unified configuration loaders for GMV v3.

This module centralizes both:
- pipeline config loading/validation (`config/pipeline.yaml`)
- LLM config loading for ChatOps (`~/.config/gmv/llm.yaml` + env + CLI)
"""

from __future__ import annotations

import csv
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import yaml


class ConfigError(ValueError):
    """Raised when configuration validation fails."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key_env: str
    api_key: str
    timeout_s: int
    verify_tls: bool

    def masked_api_key(self) -> str:
        key = self.api_key or ""
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}...{key[-4:]}"


_PIPELINE_DEFAULTS = {
    "execution": {
        "profile": "local",
        "run_id": "default-run",
        "raw_dir": "raw",
        "work_dir": "work",
        "cache_dir": "cache",
        "results_dir": "results",
        "reports_dir": "reports",
        "sample_sheet": "raw/samples.tsv",
        "use_singularity": True,
        "offline": True,
        "mock_mode": False,
    },
    "containers": {
        "mapping_file": "config/containers.yaml",
        "binds": [],
    },
    "tools": {
        "enabled": {},
        "params": {},
    },
    "agent": {
        "enabled": True,
        "auto_apply_risk_levels": ["low"],
        "retry_limit": 2,
        "low_yield_threshold": 5,
    },
    "reporting": {
        "language": "zh",
        "figure_language": "en",
    },
    "resources": {
        "default_threads": 8,
        "threads": {},
        "limits": {},
        "estimation": {
            "enabled": True,
            "fudge": 1.2,
            "overrides": {},
        },
        "slurm": {
            "account": "",
            "partition": "",
            "time": "24:00:00",
            "mem_mb": 64000,
        },
    },
    "database": {},
}

_LLM_DEFAULTS = {
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key_env": "GMV_API_KEY",
    "timeout_s": 60,
    "verify_tls": True,
}


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"配置文件不存在: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件必须是字典结构: {path}")
    return data


def _read_yaml_optional(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def _resolve(base: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _deep_defaults(config: Dict[str, Any], defaults: Mapping[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(config)
    for key, value in defaults.items():
        if key not in merged:
            merged[key] = deepcopy(value)
            continue
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_defaults(dict(merged[key]), value)
    return merged


def _ensure_sections(config: Dict[str, Any], sections: Iterable[str]) -> None:
    missing = [s for s in sections if s not in config]
    if missing:
        raise ConfigError(f"缺少必要配置段: {', '.join(missing)}")


def _validate_positive_int_map(value: Any, *, field_name: str) -> None:
    if not isinstance(value, dict):
        raise ConfigError(f"{field_name} 必须是字典")
    for key, raw in value.items():
        try:
            n = int(raw)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field_name}.{key} 必须是整数: {raw}") from exc
        if n <= 0:
            raise ConfigError(f"{field_name}.{key} 必须 > 0: {n}")


def _has_host_samples(sample_sheet: Path) -> bool:
    with sample_sheet.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if (row.get("host") or "").strip():
                return True
    return False


def _validate_estimation(cfg: Dict[str, Any]) -> None:
    est = cfg.get("resources", {}).get("estimation", {})
    if not isinstance(est, dict):
        raise ConfigError("resources.estimation 必须是字典")

    enabled = est.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError("resources.estimation.enabled 必须是 bool")

    try:
        fudge = float(est.get("fudge", 1.2))
    except (TypeError, ValueError) as exc:
        raise ConfigError("resources.estimation.fudge 必须是数字") from exc
    if fudge < 1.0:
        raise ConfigError("resources.estimation.fudge 必须 >= 1")

    overrides = est.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ConfigError("resources.estimation.overrides 必须是字典（工具名->系数）")

    allowed = {"mem_mb_base", "mem_mb_per_gb", "runtime_base", "runtime_per_gb", "mem_mb_max", "runtime_max"}
    for tool, tool_cfg in overrides.items():
        if not isinstance(tool_cfg, dict):
            raise ConfigError(f"resources.estimation.overrides.{tool} 必须是字典")
        for key, raw in tool_cfg.items():
            if key not in allowed:
                raise ConfigError(
                    f"resources.estimation.overrides.{tool}.{key} 不支持（允许: {sorted(allowed)}）"
                )
            try:
                n = float(raw)
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"resources.estimation.overrides.{tool}.{key} 必须是数字") from exc
            if n < 0:
                raise ConfigError(f"resources.estimation.overrides.{tool}.{key} 必须 >= 0")


def load_pipeline_config(config_path: str | Path) -> Dict[str, Any]:
    """Load and validate `config/pipeline.yaml`.

    Returns a normalized dict with `_meta` resolution info.
    """

    cfg_path = Path(config_path).expanduser().resolve()
    raw = _read_yaml(cfg_path)
    cfg = _deep_defaults(raw, _PIPELINE_DEFAULTS)

    _ensure_sections(cfg, ("execution", "containers", "tools", "agent", "reporting", "resources", "database"))

    base = cfg_path.parent
    sample_sheet = _resolve(base, cfg["execution"]["sample_sheet"])
    if not sample_sheet.exists():
        raise ConfigError(f"样本表不存在: {sample_sheet}")

    mapping_file = _resolve(base, cfg["containers"]["mapping_file"])
    if not mapping_file.exists():
        raise ConfigError(f"镜像映射文件不存在: {mapping_file}")

    containers_data = _read_yaml(mapping_file)
    images = containers_data.get("images", {})
    if not isinstance(images, dict):
        raise ConfigError("containers.yaml 中 images 必须是键值映射")

    use_singularity = bool(cfg["execution"].get("use_singularity", True))
    enabled_tools = cfg.get("tools", {}).get("enabled", {}) or {}
    has_host = _has_host_samples(sample_sheet)

    if use_singularity:
        required_images = {
            "fastp",
            "megahit",
            "vsearch",
            "checkv",
            "busco",
            "vclust",
            "coverm",
        }
        if bool(enabled_tools.get("virsorter", False)):
            required_images.add("virsorter")
        if bool(enabled_tools.get("genomad", False)):
            required_images.add("genomad")
        if bool(enabled_tools.get("phabox2", False)):
            required_images.add("phabox2")
        if has_host or bool(enabled_tools.get("bowtie2_samtools", False)):
            required_images.add("bowtie2")
        if bool(enabled_tools.get("bowtie2_samtools", False)):
            required_images.add("samtools")

        missing_images = [tool for tool in sorted(required_images) if tool not in images]
        if missing_images:
            raise ConfigError(f"containers.yaml 缺少必要镜像映射: {', '.join(missing_images)}")

    required_dbs = {"checkv", "busco"}
    if bool(enabled_tools.get("virsorter", False)):
        required_dbs.add("virsorter")
    if bool(enabled_tools.get("genomad", False)):
        required_dbs.add("genomad")
    if bool(enabled_tools.get("phabox2", False)):
        required_dbs.add("phabox2")
    if has_host:
        required_dbs.add("bowtie2_index")

    db_cfg = cfg.get("database", {}) or {}
    missing_db = [name for name in sorted(required_dbs) if name not in db_cfg]
    if missing_db:
        raise ConfigError(f"缺少必要数据库配置: {', '.join(missing_db)}")

    for name, raw_path in db_cfg.items():
        resolved = _resolve(base, raw_path)
        if not resolved.exists():
            raise ConfigError(f"数据库路径不存在: {name} -> {resolved}")

    _validate_positive_int_map(cfg.get("resources", {}).get("threads", {}), field_name="resources.threads")
    _validate_positive_int_map(cfg.get("resources", {}).get("limits", {}), field_name="resources.limits")
    _validate_estimation(cfg)

    normalized = deepcopy(cfg)
    normalized["_meta"] = {
        "config_path": str(cfg_path),
        "config_dir": str(base),
        "sample_sheet": str(sample_sheet),
        "mapping_file": str(mapping_file),
        "images": {name: str(_resolve(mapping_file.parent, image_path)) for name, image_path in images.items()},
    }
    return normalized


def _env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def load_llm_config(
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key_env: Optional[str] = None,
    llm_config: Optional[str] = None,
) -> LLMConfig:
    """Load ChatOps LLM config with precedence: CLI > ENV > llm.yaml > defaults."""

    cfg_path = Path(llm_config or "~/.config/gmv/llm.yaml").expanduser()
    file_cfg: Mapping[str, Any] = _read_yaml_optional(cfg_path)

    api_key_env_final = (
        api_key_env
        or _env("GMV_API_KEY_ENV")
        or str(file_cfg.get("api_key_env") or _LLM_DEFAULTS["api_key_env"])
    )
    base_url_final = base_url or _env("GMV_BASE_URL") or str(file_cfg.get("base_url") or _LLM_DEFAULTS["base_url"])
    model_final = model or _env("GMV_MODEL") or str(file_cfg.get("model") or _LLM_DEFAULTS["model"])

    timeout_raw = _env("GMV_TIMEOUT_S") or file_cfg.get("timeout_s") or _LLM_DEFAULTS["timeout_s"]
    try:
        timeout_s = int(timeout_raw)
    except (TypeError, ValueError):
        timeout_s = int(_LLM_DEFAULTS["timeout_s"])
    timeout_s = max(1, timeout_s)

    verify_raw = file_cfg.get("verify_tls")
    verify_tls = bool(_LLM_DEFAULTS["verify_tls"] if verify_raw is None else verify_raw)

    api_key = _env(api_key_env_final)
    if not api_key:
        api_key = str(file_cfg.get("api_key") or "").strip()

    if not api_key and _env("GMV_CHAT_MOCK") != "1":
        raise ValueError(
            f"缺少 API key：请设置环境变量 {api_key_env_final}=... "
            f"或在 {cfg_path} 中配置 api_key（不推荐，易泄漏）。"
        )

    return LLMConfig(
        base_url=base_url_final.rstrip("/"),
        model=model_final,
        api_key_env=api_key_env_final,
        api_key=api_key,
        timeout_s=timeout_s,
        verify_tls=verify_tls,
    )
