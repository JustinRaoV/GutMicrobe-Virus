"""Configuration schema and validation for GutMicrobeVirus v2."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


class ConfigValidationError(ValueError):
    """Raised when configuration validation fails."""


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigValidationError(f"配置文件必须是字典结构: {path}")
    return data


def _resolve(base: Path, maybe_path: str | Path) -> Path:
    p = Path(maybe_path)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def _ensure_sections(config: Dict[str, Any], sections: Iterable[str]) -> None:
    missing = [s for s in sections if s not in config]
    if missing:
        raise ConfigValidationError(f"缺少必要配置段: {', '.join(missing)}")


def _apply_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    cfg = deepcopy(config)
    cfg.setdefault("execution", {})
    cfg["execution"].setdefault("profile", "local")
    cfg["execution"].setdefault("run_id", "default-run")
    cfg["execution"].setdefault("raw_dir", "raw")
    cfg["execution"].setdefault("work_dir", "work")
    cfg["execution"].setdefault("cache_dir", "cache")
    cfg["execution"].setdefault("results_dir", f"results/{cfg['execution']['run_id']}")
    cfg["execution"].setdefault("reports_dir", "reports")
    cfg["execution"].setdefault("sample_sheet", "raw/samples.tsv")
    cfg["execution"].setdefault("use_singularity", True)
    cfg["execution"].setdefault("offline", True)
    cfg["execution"].setdefault("mock_mode", False)

    cfg.setdefault("containers", {})
    cfg["containers"].setdefault("mapping_file", "config/containers.yaml")

    cfg.setdefault("tools", {})
    cfg["tools"].setdefault("enabled", {})
    cfg["tools"].setdefault("params", {})

    cfg.setdefault("agent", {})
    cfg["agent"].setdefault("enabled", True)
    cfg["agent"].setdefault("auto_apply_risk_levels", ["low"])
    cfg["agent"].setdefault("retry_limit", 2)
    cfg["agent"].setdefault("low_yield_threshold", 5)

    cfg.setdefault("reporting", {})
    cfg["reporting"].setdefault("language", "zh")
    cfg["reporting"].setdefault("figure_language", "en")

    cfg.setdefault("resources", {})
    cfg["resources"].setdefault("default_threads", 8)
    cfg["resources"].setdefault("slurm", {})
    cfg["resources"]["slurm"].setdefault("account", "")
    cfg["resources"]["slurm"].setdefault("partition", "")
    cfg["resources"]["slurm"].setdefault("time", "24:00:00")
    cfg["resources"]["slurm"].setdefault("mem_mb", 64000)

    cfg.setdefault("database", {})
    return cfg


def load_pipeline_config(config_path: str | Path) -> Dict[str, Any]:
    """Load and validate pipeline config, and return normalized dict."""
    cfg_path = Path(config_path).resolve()
    if not cfg_path.exists():
        raise ConfigValidationError(f"配置文件不存在: {cfg_path}")

    config = _apply_defaults(_read_yaml(cfg_path))
    _ensure_sections(config, ["execution", "containers", "tools", "agent", "reporting", "resources", "database"])

    base = cfg_path.parent
    sample_sheet = _resolve(base, config["execution"]["sample_sheet"])
    if not sample_sheet.exists():
        raise ConfigValidationError(f"样本表不存在: {sample_sheet}")

    mapping_file = _resolve(base, config["containers"]["mapping_file"])
    if not mapping_file.exists():
        raise ConfigValidationError(f"镜像映射文件不存在: {mapping_file}")

    containers_data = _read_yaml(mapping_file)
    images = containers_data.get("images", {})
    if not isinstance(images, dict):
        raise ConfigValidationError("containers.yaml 中 images 必须是键值映射")

    use_singularity = bool(config["execution"].get("use_singularity", True))
    if use_singularity:
        for tool, enabled in config["tools"].get("enabled", {}).items():
            if enabled and tool not in images and tool != "bowtie2_samtools":
                raise ConfigValidationError(f"启用工具 {tool} 缺少镜像映射")
        if config["tools"].get("enabled", {}).get("bowtie2_samtools"):
            for required in ("bowtie2", "samtools"):
                if required not in images:
                    raise ConfigValidationError("bowtie2_samtools 启用时必须映射 bowtie2 和 samtools")

    for db_name, db_path in config.get("database", {}).items():
        resolved = _resolve(base, db_path)
        if not resolved.exists():
            raise ConfigValidationError(f"数据库路径不存在: {db_name} -> {resolved}")

    normalized = deepcopy(config)
    normalized["_meta"] = {
        "config_path": str(cfg_path),
        "config_dir": str(base),
        "sample_sheet": str(sample_sheet),
        "mapping_file": str(mapping_file),
        "images": {k: str(_resolve(mapping_file.parent, v)) for k, v in images.items()},
    }
    return normalized


def enabled_tools(config: Dict[str, Any]) -> Dict[str, bool]:
    return {k: bool(v) for k, v in config.get("tools", {}).get("enabled", {}).items()}
