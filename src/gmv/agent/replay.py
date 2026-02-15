"""Replay recorded signals through the policy engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from gmv.agent.policy_engine import PolicyEngine


def replay_decisions(signal_file: str | Path, engine: PolicyEngine) -> List[Dict[str, Any]]:
    path = Path(signal_file)
    if not path.exists():
        raise FileNotFoundError(f"信号文件不存在: {path}")

    decisions: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            step = payload.get("step", "unknown")
            signal = payload.get("signal", {})
            decisions.append(engine.evaluate(step=step, signal=signal))
    return decisions
