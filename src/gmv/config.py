from __future__ import annotations

import csv
import os
import re
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """Raised when config loading or validation fails."""


FASTQ_EXTENSIONS = (".fastq.gz", ".fq.gz", ".fastq", ".fq")


DEFAULT_PIPELINE_CONFIG: dict[str, Any] = {
    "execution": {
        "run_id": "gmv-run",
        "profile": "local",
        "raw_dir": "raw",
        "work_dir": "work",
        "cache_dir": "cache",
        "results_dir": "results",
        "reports_dir": "reports",
        "sample_sheet": "samples.tsv",
        "use_singularity": True,
        "container_runtime": "auto",
        "offline": True,
    },
    "paths": {
        "data_dir": "",
        "sif_dir": "",
        "db_dir": "",
    },
    "containers": {
        "mapping_file": "containers.yaml",
        "images": {},
        "binds": [],
    },
    "tools": {
        "enabled": {
            "virsorter": True,
            "genomad": True,
            "coverm": True,
            "vclust": True,
            "phabox2": False,
        },
        "params": {
            "vsearch_min_len": 1500,
            "busco_ratio_threshold": 0.05,
            "coverm": "--min-read-percent-identity 95 --min-read-aligned-percent 75 --output-format dense",
            "vclust_min_ident": 0.95,
            "vclust_ani": 0.95,
            "vclust_qcov": 0.85,
        },
        "binary": {
            "fastp": "fastp",
            "bowtie2": "bowtie2",
            "megahit": "megahit",
            "vsearch": "vsearch",
            "virsorter": "virsorter",
            "genomad": "genomad",
            "checkv": "checkv",
            "coverm": "coverm",
            "vclust": "vclust",
            "seqkit": "seqkit",
        },
    },
    "resources": {
        "default_threads": 8,
        "threads": {
            "fastp": 8,
            "bowtie2": 8,
            "megahit": 16,
            "vsearch": 4,
            "virsorter": 8,
            "genomad": 8,
            "checkv": 8,
            "coverm": 16,
            "vclust": 8,
            "project": 8,
        },
        "limits": {
            "checkv": 1,
            "virsorter": 1,
            "busco": 1,
        },
        "estimation": {
            "enabled": True,
            "fudge": 1.2,
            "overrides": {},
        },
    },
    "agent": {
        "enabled": True,
        "auto_apply_risk_levels": ["low"],
        "retry_limit": 1,
    },
    "reporting": {
        "language": "zh",
        "figure_language": "en",
    },
    "database": {
        "bowtie2_index": "",
        "checkv": "",
        "virsorter": "",
        "genomad": "",
        "busco": "",
        "phabox2": "",
        "blastn": "",
    },
    "chat": {
        "max_steps": 8,
    },
}


DEFAULT_LLM_CONFIG: dict[str, Any] = {
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key_env": "GMV_API_KEY",
    "timeout_s": 60,
    "verify_tls": True,
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ConfigError(f"配置文件不存在: {path}")
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"配置格式错误(必须是 YAML map): {path}")
    return data


def _resolve_path(raw: str | Path, base: Path) -> str:
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    return str((base / candidate).resolve())


def load_pipeline_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path).expanduser().resolve()
    raw = _read_yaml(path)
    cfg = _deep_merge(DEFAULT_PIPELINE_CONFIG, raw)
    cfg["_meta"] = {
        "config_path": str(path),
        "config_dir": str(path.parent),
        "project_root": str(Path.cwd().resolve()),
    }

    config_dir = path.parent

    execution = cfg["execution"]
    for key in ("raw_dir", "work_dir", "cache_dir", "results_dir", "reports_dir"):
        execution[key] = _resolve_path(execution[key], Path(cfg["_meta"]["project_root"]))

    if execution.get("sample_sheet"):
        execution["sample_sheet"] = _resolve_path(execution["sample_sheet"], config_dir)

    paths = cfg.get("paths", {})
    for key in ("data_dir", "sif_dir", "db_dir"):
        if paths.get(key):
            paths[key] = _resolve_path(paths[key], Path(cfg["_meta"]["project_root"]))

    database = cfg.get("database", {})
    for key, value in list(database.items()):
        if isinstance(value, str) and value:
            database[key] = _resolve_path(value, Path(cfg["_meta"]["project_root"]))

    containers = cfg.get("containers", {})
    if containers.get("mapping_file"):
        mapping_file = Path(_resolve_path(containers["mapping_file"], config_dir))
        containers["mapping_file"] = str(mapping_file)
        if mapping_file.exists() and not containers.get("images"):
            mapping = _read_yaml(mapping_file)
            if "images" in mapping and isinstance(mapping["images"], dict):
                containers["images"] = mapping["images"]

    images = containers.get("images", {})
    if isinstance(images, dict):
        for tool, image in list(images.items()):
            if isinstance(image, str) and image:
                images[tool] = _resolve_path(image, Path(cfg["_meta"]["project_root"]))

    binds = containers.get("binds", [])
    normalized_binds = []
    for item in binds:
        if isinstance(item, str) and item:
            normalized_binds.append(_resolve_path(item, Path(cfg["_meta"]["project_root"])))
    containers["binds"] = normalized_binds

    estimation = cfg.get("resources", {}).get("estimation", {})
    fudge = estimation.get("fudge", 1.2)
    if fudge < 1:
        raise ConfigError("resources.estimation.fudge 必须 >= 1")

    return cfg


def _split_fastq_name(file_name: str) -> tuple[str, str] | None:
    for ext in FASTQ_EXTENSIONS:
        if file_name.endswith(ext):
            return file_name[: -len(ext)], ext
    return None


def _pair_tokens(primary_r1: str, primary_r2: str) -> list[tuple[str, str]]:
    pairs = [(primary_r1, primary_r2), ("R1", "R2"), ("_R1", "_R2"), ("_1", "_2"), (".1", ".2")]
    seen = set()
    ordered = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            ordered.append(pair)
    return ordered


def discover_samples_from_input_dir(
    input_dir: str,
    pair_r1: str = "_R1",
    pair_r2: str = "_R2",
    default_host: str = "",
) -> list[dict[str, str]]:
    data_dir = Path(input_dir).expanduser().resolve()
    if not data_dir.exists() or not data_dir.is_dir():
        raise ConfigError(f"输入目录不存在: {data_dir}")

    files = sorted(p.name for p in data_dir.iterdir() if p.is_file())
    file_set = set(files)

    records: dict[str, dict[str, str]] = {}
    used_r1: set[str] = set()
    token_pairs = _pair_tokens(pair_r1, pair_r2)

    for name in files:
        split = _split_fastq_name(name)
        if not split:
            continue
        stem, ext = split
        for token_r1, token_r2 in token_pairs:
            if not token_r1 or token_r1 == token_r2:
                continue
            if not stem.endswith(token_r1):
                continue
            sample_raw = stem[: -len(token_r1)]
            sample = re.sub(r"[_\-.]+$", "", sample_raw)
            if not sample:
                sample = sample_raw
            r2_name = f"{sample_raw}{token_r2}{ext}"
            if r2_name not in file_set:
                continue
            if name in used_r1:
                continue
            used_r1.add(name)
            records[sample] = {
                "sample": sample,
                "mode": "reads",
                "input1": str((data_dir / name).resolve()),
                "input2": str((data_dir / r2_name).resolve()),
                "host": default_host.strip(),
            }
            break

    if not records:
        raise ConfigError(
            f"在目录中未识别到配对 reads: {data_dir}。可通过 --pair-r1/--pair-r2 调整配对规则。"
        )

    return [records[key] for key in sorted(records.keys())]


def load_sample_sheet(sample_sheet: str) -> list[dict[str, str]]:
    path = Path(sample_sheet).expanduser().resolve()
    if not path.exists():
        raise ConfigError(f"sample_sheet 不存在: {path}")

    with path.open("r", encoding="utf-8") as handle:
        head = handle.readline()
    delimiter = "\t" if "\t" in head else ","

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        rows = [
            {
                "sample": (row.get("sample") or "").strip(),
                "mode": (row.get("mode") or "reads").strip() or "reads",
                "input1": (row.get("input1") or "").strip(),
                "input2": (row.get("input2") or "").strip(),
                "host": (row.get("host") or "").strip(),
            }
            for row in reader
        ]

    if not rows:
        raise ConfigError(f"sample_sheet 为空: {path}")

    for row in rows:
        if not row["sample"]:
            raise ConfigError(f"sample_sheet 存在空 sample: {path}")
        if not row["input1"]:
            raise ConfigError(f"sample_sheet 行缺少 input1: sample={row['sample']}")

    return rows


def write_sample_sheet(records: list[dict[str, str]], out_path: str) -> str:
    path = Path(out_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample", "mode", "input1", "input2", "host"], delimiter="\t")
        writer.writeheader()
        for row in records:
            writer.writerow(row)
    return str(path)


def prepare_sample_sheet(
    cfg: dict[str, Any],
    input_dir: str | None,
    sample_sheet: str | None,
    pair_r1: str,
    pair_r2: str,
    host: str | None = None,
) -> tuple[str, list[dict[str, str]], bool]:
    if input_dir and sample_sheet:
        raise ConfigError("--input-dir 与 --sample-sheet 只能二选一")

    generated = False
    if input_dir:
        records = discover_samples_from_input_dir(
            input_dir,
            pair_r1=pair_r1,
            pair_r2=pair_r2,
            default_host=(host or ""),
        )
        run_id = cfg["execution"]["run_id"]
        out_sheet = Path(cfg["execution"]["raw_dir"]) / run_id / "samples.auto.tsv"
        sheet_path = write_sample_sheet(records, str(out_sheet))
        generated = True
    else:
        sheet_path = sample_sheet or cfg["execution"].get("sample_sheet")
        if not sheet_path:
            raise ConfigError("缺少 sample_sheet。请提供 --input-dir 或 --sample-sheet")
        records = load_sample_sheet(sheet_path)
        if host:
            for row in records:
                row["host"] = host.strip()

    cfg["execution"]["sample_sheet"] = str(Path(sheet_path).expanduser().resolve())
    return cfg["execution"]["sample_sheet"], records, generated


def validate_runtime(
    cfg: dict[str, Any],
    samples: list[dict[str, str]],
    strict: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    optional_db_keys = {"virsorter"}

    for key in ("raw_dir", "work_dir", "results_dir", "reports_dir"):
        value = cfg["execution"].get(key)
        if not value:
            errors.append(f"execution.{key} 缺失")

    for row in samples:
        input1 = Path(row["input1"]).expanduser().resolve()
        input2 = Path(row["input2"]).expanduser().resolve() if row.get("input2") else None
        if not input1.exists():
            errors.append(f"样本输入不存在: {row['sample']} -> {input1}")
        if row.get("mode", "reads") == "reads" and (not input2 or not input2.exists()):
            errors.append(f"样本 input2 不存在: {row['sample']} -> {input2}")

    for db_name, db_path in cfg.get("database", {}).items():
        if not db_path:
            if db_name not in optional_db_keys:
                warnings.append(f"数据库未设置: {db_name}")
            continue
        if not Path(db_path).exists():
            if db_name in optional_db_keys:
                warnings.append(f"数据库路径不存在(将回退工具默认): {db_name} -> {db_path}")
            else:
                errors.append(f"数据库路径不存在: {db_name} -> {db_path}")

    def _bowtie2_prefix_exists(prefix: str) -> bool:
        base = Path(prefix)
        bt2 = [f"{base}.{idx}.bt2" for idx in ("1", "2", "3", "4", "rev.1", "rev.2")]
        bt2l = [f"{base}.{idx}.bt2l" for idx in ("1", "2", "3", "4", "rev.1", "rev.2")]
        return all(Path(p).exists() for p in bt2) or all(Path(p).exists() for p in bt2l)

    bowtie_root = cfg.get("database", {}).get("bowtie2_index", "")
    if bowtie_root:
        root = Path(bowtie_root).expanduser().resolve()
        for row in samples:
            host = (row.get("host") or "").strip()
            if not host:
                continue
            candidates = []
            if root.is_dir():
                candidates.extend([root / host / host, root / host, root / f"{host}_index"])
            else:
                candidates.append(root)
            if not any(_bowtie2_prefix_exists(str(item)) for item in candidates):
                errors.append(
                    f"样本 {row['sample']} 指定 host={host}，但未找到可用 Bowtie2 index 前缀（base={root}）"
                )

    def _resolve_container_runtime(preferred: str | None) -> str:
        pref = (preferred or "auto").strip()
        if pref in {"", "auto"}:
            return shutil.which("singularity") or shutil.which("apptainer") or ""
        if Path(pref).exists():
            return pref
        return shutil.which(pref) or ""

    execution_cfg = cfg.get("execution", {})
    use_singularity = bool(execution_cfg.get("use_singularity", True))
    if use_singularity:
        runtime = _resolve_container_runtime(str(execution_cfg.get("container_runtime", "auto")))
        if strict and not runtime:
            errors.append("未找到容器运行时命令（singularity/apptainer）。请先 module load 或在 execution.container_runtime 指定绝对路径。")
        if not strict and not runtime:
            warnings.append("未检测到 singularity/apptainer；若直接运行将失败。建议先 module load 或设置 execution.container_runtime。")
        images = cfg.get("containers", {}).get("images", {})
        for tool_name, image_path in images.items():
            if not Path(image_path).exists():
                errors.append(f"容器镜像不存在: {tool_name} -> {image_path}")
    else:
        binaries = cfg.get("tools", {}).get("binary", {})
        for tool_name, binary in binaries.items():
            if cfg.get("tools", {}).get("enabled", {}).get(tool_name, True) and strict and shutil.which(binary) is None:
                warnings.append(f"本地工具未找到: {tool_name} ({binary})")

    return errors, warnings


def load_llm_settings(
    llm_config_path: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key_env: str | None = None,
    require_api_key: bool = True,
) -> dict[str, Any]:
    config_file = Path(llm_config_path or "~/.config/gmv/llm.yaml").expanduser().resolve()
    file_data = _read_yaml(config_file, required=False)

    merged = _deep_merge(DEFAULT_LLM_CONFIG, file_data)

    merged["base_url"] = base_url or os.environ.get("GMV_BASE_URL") or merged["base_url"]
    merged["model"] = model or os.environ.get("GMV_MODEL") or merged["model"]
    merged["api_key_env"] = api_key_env or os.environ.get("GMV_API_KEY_ENV") or merged.get("api_key_env", "GMV_API_KEY")

    api_key = os.environ.get(merged["api_key_env"], "")
    if not api_key and file_data.get("api_key"):
        api_key = str(file_data["api_key"])

    merged["api_key"] = api_key
    merged["llm_config_path"] = str(config_file)

    if require_api_key and not os.environ.get("GMV_CHAT_MOCK") and not api_key:
        raise ConfigError(
            f"缺少 API key。请设置环境变量 {merged['api_key_env']} 或在 {config_file} 中配置 api_key。"
        )

    return merged


def dump_yaml(path: str, data: dict[str, Any]) -> str:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
    return str(target)
