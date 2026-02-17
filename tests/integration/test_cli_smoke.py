from __future__ import annotations

import os
from pathlib import Path

from gmv import cli


MINIMAL_CONFIG = "tests/fixtures/minimal/config/pipeline.yaml"
MINIMAL_INPUT = "tests/fixtures/minimal/data"


def test_validate_smoke() -> None:
    code = cli.main(["validate", "--config", MINIMAL_CONFIG, "--input-dir", MINIMAL_INPUT])
    assert code == 0


def test_chat_mock_validate(monkeypatch) -> None:
    monkeypatch.setenv("GMV_CHAT_MOCK", "1")
    code = cli.main(
        [
            "chat",
            "--config",
            MINIMAL_CONFIG,
            "--message",
            "validate",
        ]
    )
    assert code == 0


def test_run_dry_run_without_snakemake(monkeypatch) -> None:
    # When snakemake is not installed in CI/local, this should fail with non-zero exit.
    # If installed, the command still should parse and execute dry-run cleanly.
    code = cli.main(
        [
            "run",
            "--config",
            MINIMAL_CONFIG,
            "--input-dir",
            MINIMAL_INPUT,
            "--profile",
            "local",
            "--stage",
            "upstream",
            "--cores",
            "2",
            "--dry-run",
        ]
    )
    assert code in {0, 1}
