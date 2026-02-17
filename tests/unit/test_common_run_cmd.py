from __future__ import annotations

from pathlib import Path

import pytest

from gmv.workflow.steps.common import run_cmd


def test_run_cmd_includes_stderr_tail_on_failure() -> None:
    with pytest.raises(RuntimeError) as exc:
        run_cmd("sh -c 'echo boom 1>&2; exit 7'")

    message = str(exc.value)
    assert "命令失败(7)" in message
    assert "[tool output tail]" in message
    assert "boom" in message


def test_run_cmd_persists_full_log_when_log_path_given(tmp_path: Path) -> None:
    log_path = tmp_path / "cmd.log"
    with pytest.raises(RuntimeError) as exc:
        run_cmd("sh -c 'echo boom2 1>&2; exit 9'", log_path=log_path)

    message = str(exc.value)
    assert "命令失败(9)" in message
    assert str(log_path) in message
    assert log_path.exists()
    assert "boom2" in log_path.read_text(encoding="utf-8")
