"""Environment validation for offline/server deployment."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List


def _cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def validate_environment(config: Dict[str, Any], strict: bool = False) -> Dict[str, List[str]]:
    mock_mode = bool(config["execution"].get("mock_mode", False))
    use_singularity = bool(config["execution"].get("use_singularity", True))
    profile = str(config["execution"].get("profile", "local"))

    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []

    images = config.get("_meta", {}).get("images", {})

    if use_singularity:
        has_singularity = _cmd_exists("singularity") or _cmd_exists("apptainer")
        if not has_singularity:
            message = "未检测到 singularity/apptainer"
            if mock_mode:
                warnings.append(f"{message}（mock_mode=true，允许）")
            else:
                errors.append(message)

    if profile == "slurm" and not _cmd_exists("sbatch"):
        message = "未检测到 sbatch（SLURM 提交命令）"
        if mock_mode:
            warnings.append(f"{message}（mock_mode=true，允许）")
        else:
            errors.append(message)

    for tool, image_path in images.items():
        if not Path(image_path).exists():
            errors.append(f"镜像不存在: {tool} -> {image_path}")

    if strict and warnings:
        errors.extend([f"STRICT模式视为错误: {w}" for w in warnings])
        warnings = []

    if not errors:
        info.append("配置校验通过")

    return {"errors": errors, "warnings": warnings, "info": info}
