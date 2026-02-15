"""Policy engine for risk-graded autonomous decisions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Set


@dataclass
class PolicyEngine:
    auto_apply_risk_levels: Set[str]
    retry_limit: int
    low_yield_threshold: int

    def evaluate(self, step: str, signal: Mapping[str, Any]) -> Dict[str, Any]:
        status = str(signal.get("status", "unknown"))
        error_type = str(signal.get("error_type", ""))
        attempt = int(signal.get("attempt", 1))
        yield_count = int(signal.get("yield_count", 0))

        action = "noop"
        risk_level = "low"
        delta_params: Dict[str, Any] = {}

        if status == "failed" and error_type in {"oom", "memory", "timeout"}:
            action = "increase_resources"
            risk_level = "low"
            delta_params = {"threads_scale": 1.5, "mem_scale": 1.5}
        elif status == "failed" and attempt <= self.retry_limit:
            action = "retry"
            risk_level = "low"
            delta_params = {"retry": attempt}
        elif status == "low_yield" and yield_count < self.low_yield_threshold:
            action = "relax_quality_threshold"
            risk_level = "high"
            delta_params = {"checkv_quality": "allow_low", "busco_ratio_threshold": 0.1}
        elif status == "failed" and attempt > self.retry_limit:
            action = "request_manual_review"
            risk_level = "medium"
            delta_params = {"reason": "retry_limit_exceeded"}

        auto_applied = risk_level in self.auto_apply_risk_levels and action != "request_manual_review"

        return {
            "step": step,
            "signal": dict(signal),
            "action": action,
            "delta_params": delta_params,
            "risk_level": risk_level,
            "auto_applied": auto_applied,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
