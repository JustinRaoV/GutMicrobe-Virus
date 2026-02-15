"""Signal parsing utilities for policy engine inputs."""
from __future__ import annotations

from typing import Any, Dict


def build_signal_from_step_metrics(status: str, attempt: int = 1, **kwargs: Any) -> Dict[str, Any]:
    signal = {"status": status, "attempt": attempt}
    signal.update(kwargs)
    return signal
