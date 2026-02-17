from __future__ import annotations

import os
from pathlib import Path

import pytest

from gmv.config import ConfigError, discover_samples_from_input_dir, load_llm_settings, load_pipeline_config


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
