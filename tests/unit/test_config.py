from __future__ import annotations

import os
from pathlib import Path

import pytest

from gmv.config import ConfigError, discover_samples_from_input_dir, load_llm_settings, load_pipeline_config, validate_runtime


def test_discover_samples_supports_r1_without_underscore(tmp_path: Path) -> None:
    (tmp_path / "myR1.fq").write_text("@r1\nACGT\n+\nIIII\n", encoding="utf-8")
    (tmp_path / "myR2.fq").write_text("@r2\nTGCA\n+\nIIII\n", encoding="utf-8")

    rows = discover_samples_from_input_dir(str(tmp_path), pair_r1="_R1", pair_r2="_R2")
    assert len(rows) == 1
    assert rows[0]["sample"] == "my"


def test_load_llm_settings_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "llm.yaml"
    cfg.write_text(
        "\n".join(
            [
                "base_url: https://file.example/v1",
                "model: file-model",
                "api_key_env: FILE_KEY",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("GMV_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("GMV_MODEL", "env-model")
    monkeypatch.setenv("GMV_API_KEY", "env-key")

    settings = load_llm_settings(
        llm_config_path=str(cfg),
        base_url="https://cli.example/v1",
        model="cli-model",
        api_key_env="GMV_API_KEY",
    )

    assert settings["base_url"] == "https://cli.example/v1"
    assert settings["model"] == "cli-model"
    assert settings["api_key"] == "env-key"


def test_pipeline_rejects_low_fudge(tmp_path: Path) -> None:
    cfg = tmp_path / "pipeline.yaml"
    cfg.write_text(
        "\n".join(
            [
                "execution:",
                "  run_id: bad",
                "resources:",
                "  estimation:",
                "    fudge: 0.5",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_pipeline_config(str(cfg))


def test_validate_runtime_treats_virsorter_db_as_optional() -> None:
    cfg = load_pipeline_config("tests/fixtures/minimal/config/pipeline.yaml")
    cfg["database"]["virsorter"] = ""
    samples = [
        {
            "sample": "alpha",
            "mode": "reads",
            "input1": str(Path("tests/fixtures/minimal/data/alpha_R1.fq").resolve()),
            "input2": str(Path("tests/fixtures/minimal/data/alpha_R2.fq").resolve()),
            "host": "",
        }
    ]
    errors, warnings = validate_runtime(cfg, samples, strict=False)
    assert not any("数据库未设置: virsorter" in item for item in warnings)
    assert not any("virsorter" in item for item in errors)


def test_validate_runtime_warns_not_errors_for_missing_virsorter_db_path() -> None:
    cfg = load_pipeline_config("tests/fixtures/minimal/config/pipeline.yaml")
    cfg["database"]["virsorter"] = str(Path("tests/fixtures/minimal/db/not-exist").resolve())
    samples = [
        {
            "sample": "alpha",
            "mode": "reads",
            "input1": str(Path("tests/fixtures/minimal/data/alpha_R1.fq").resolve()),
            "input2": str(Path("tests/fixtures/minimal/data/alpha_R2.fq").resolve()),
            "host": "",
        }
    ]
    errors, warnings = validate_runtime(cfg, samples, strict=False)
    assert any("数据库路径不存在(将回退工具默认): virsorter" in item for item in warnings)
    assert not any("数据库路径不存在: virsorter" in item for item in errors)
