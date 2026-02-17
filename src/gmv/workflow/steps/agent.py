"""Agent-related workflow steps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def step_agent(args: argparse.Namespace) -> None:
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    steps = [item for item in args.steps.split(",") if item]
    with open(args.out, "w", encoding="utf-8") as fh:
        for step in steps:
            payload = {
                "step": step,
                "signal": {"status": "success", "attempt": 1},
                "action": "noop",
                "delta_params": {},
                "risk_level": "low",
                "auto_applied": True,
                "timestamp": "1970-01-01T00:00:00+00:00",
            }
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def register_agent(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("agent")
    parser.add_argument("--steps", required=True)
    parser.add_argument("--out", required=True)
    parser.set_defaults(func=step_agent)
