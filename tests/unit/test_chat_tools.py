from __future__ import annotations

import pytest

from gmv.chat.session import _is_high_risk
from gmv.chat.tools import parse_tool_arguments, tool_registry


def test_tool_registry_contains_required_tools() -> None:
    registry = tool_registry()
    assert "gmv_validate" in registry
    assert "gmv_run" in registry
    assert "slurm_scancel" in registry


def test_high_risk_detection() -> None:
    assert _is_high_risk("gmv_run", {"dry_run": False})
    assert not _is_high_risk("gmv_run", {"dry_run": True})
    assert _is_high_risk("slurm_scancel", {"job_id": "123"})


def test_parse_tool_arguments_invalid_json() -> None:
    with pytest.raises(ValueError):
        parse_tool_arguments("{bad json")
