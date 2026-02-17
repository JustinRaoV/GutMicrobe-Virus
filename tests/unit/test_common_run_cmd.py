from __future__ import annotations

import pytest

from gmv.workflow.steps.common import run_cmd


def test_run_cmd_includes_stderr_tail_on_failure() -> None:
    with pytest.raises(RuntimeError) as exc:
        run_cmd("sh -c 'echo boom 1>&2; exit 7'")

    message = str(exc.value)
    assert "命令失败(7)" in message
    assert "[tool output tail]" in message
    assert "boom" in message
