"""Configuration schema and validation for GutMicrobeVirus v2."""
from __future__ import annotations

import csv
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
    # Base results directory. Run-specific outputs live under `{results_dir}/{run_id}`.
    cfg["execution"].setdefault("results_dir", "results")
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
    cfg["resources"].setdefault("threads", {})
    cfg["resources"].setdefault("limits", {})
    cfg["resources"].setdefault("estimation", {})
    cfg["resources"]["estimation"].setdefault("enabled", True)
    cfg["resources"]["estimation"].setdefault("fudge", 1.2)
    cfg["resources"]["estimation"].setdefault("overrides", {})
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
        enabled = config["tools"].get("enabled", {}) or {}

        # Determine whether host-removal is requested by any sample.
        has_host = False
        with sample_sheet.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                if (row.get("host") or "").strip():
                    has_host = True
                    break

        required_images = {
            # Core steps (always in the DAG)
            "fastp",
            "megahit",
            "vsearch",
            "checkv",
            "busco",
            "vclust",
            "coverm",
        }
        if bool(enabled.get("virsorter", False)):
            required_images.add("virsorter")
        if bool(enabled.get("genomad", False)):
            required_images.add("genomad")
        if bool(enabled.get("phabox2", False)):
            required_images.add("phabox2")
        if has_host or bool(enabled.get("bowtie2_samtools", False)):
            required_images.add("bowtie2")
        if bool(enabled.get("bowtie2_samtools", False)):
            required_images.add("samtools")

        missing = [t for t in sorted(required_images) if t not in images]
        if missing:
            raise ConfigValidationError(f"containers.yaml 缺少必要镜像映射: {', '.join(missing)}")

    # Database requirements depend on enabled tools / sample sheet.
    enabled = config["tools"].get("enabled", {}) or {}
    required_dbs = {"checkv", "busco"}
    if bool(enabled.get("virsorter", False)):
        required_dbs.add("virsorter")
    if bool(enabled.get("genomad", False)):
        required_dbs.add("genomad")
    if bool(enabled.get("phabox2", False)):
        required_dbs.add("phabox2")
    # If any sample requests host-removal, bowtie2_index must exist.
    has_host = False
    with sample_sheet.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if (row.get("host") or "").strip():
                has_host = True
                break
    if has_host:
        required_dbs.add("bowtie2_index")

    db_cfg = config.get("database", {}) or {}
    missing_db = [k for k in sorted(required_dbs) if k not in db_cfg]
    if missing_db:
        raise ConfigValidationError(f"缺少必要数据库配置: {', '.join(missing_db)}")

    for db_name, db_path in db_cfg.items():
        resolved = _resolve(base, db_path)
        if not resolved.exists():
            raise ConfigValidationError(f"数据库路径不存在: {db_name} -> {resolved}")

    threads_cfg = config.get("resources", {}).get("threads", {})
    if not isinstance(threads_cfg, dict):
        raise ConfigValidationError("resources.threads 必须是字典（工具名->线程数）")
    for k, v in threads_cfg.items():
        try:
            n = int(v)
        except (TypeError, ValueError) as exc:
            raise ConfigValidationError(f"resources.threads.{k} 必须是整数: {v}") from exc
        if n <= 0:
            raise ConfigValidationError(f"resources.threads.{k} 必须 > 0: {n}")

    limits_cfg = config.get("resources", {}).get("limits", {})
    if not isinstance(limits_cfg, dict):
        raise ConfigValidationError("resources.limits 必须是字典（资源名->上限）")
    for k, v in limits_cfg.items():
        try:
            n = int(v)
        except (TypeError, ValueError) as exc:
            raise ConfigValidationError(f"resources.limits.{k} 必须是整数: {v}") from exc
        if n <= 0:
            raise ConfigValidationError(f"resources.limits.{k} 必须 > 0: {n}")

    est_cfg = config.get("resources", {}).get("estimation", {})
    if not isinstance(est_cfg, dict):
        raise ConfigValidationError("resources.estimation 必须是字典")
    enabled = est_cfg.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigValidationError("resources.estimation.enabled 必须是 bool")
    fudge = est_cfg.get("fudge", 1.2)
    try:
        fudge_f = float(fudge)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError("resources.estimation.fudge 必须是数字") from exc
    if fudge_f < 1.0:
        raise ConfigValidationError("resources.estimation.fudge 必须 >= 1")

    overrides = est_cfg.get("overrides", {}) or {}
    if not isinstance(overrides, dict):
        raise ConfigValidationError("resources.estimation.overrides 必须是字典（工具名->系数）")
    allowed_keys = {"mem_mb_base", "mem_mb_per_gb", "runtime_base", "runtime_per_gb", "mem_mb_max", "runtime_max"}
    for tool, ov in overrides.items():
        if not isinstance(ov, dict):
            raise ConfigValidationError(f"resources.estimation.overrides.{tool} 必须是字典")
        for k, v in ov.items():
            if k not in allowed_keys:
                raise ConfigValidationError(f"resources.estimation.overrides.{tool}.{k} 不支持（允许: {sorted(allowed_keys)}）")
            try:
                n = float(v)
            except (TypeError, ValueError) as exc:
                raise ConfigValidationError(f"resources.estimation.overrides.{tool}.{k} 必须是数字") from exc
            if n < 0:
                raise ConfigValidationError(f"resources.estimation.overrides.{tool}.{k} 必须 >= 0")

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
