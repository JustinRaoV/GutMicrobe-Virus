import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.agent.policy_engine import PolicyEngine


class PolicyEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = PolicyEngine(auto_apply_risk_levels={"low"}, retry_limit=2, low_yield_threshold=5)

    def test_low_risk_decision_auto_applied(self):
        decision = self.engine.evaluate(
            step="genomad",
            signal={"status": "failed", "error_type": "oom", "attempt": 1},
        )
        self.assertEqual(decision["risk_level"], "low")
        self.assertTrue(decision["auto_applied"])
        self.assertEqual(decision["action"], "increase_resources")

    def test_high_risk_decision_not_auto_applied(self):
        decision = self.engine.evaluate(
            step="high_quality",
            signal={"status": "low_yield", "yield_count": 0, "attempt": 1},
        )
        self.assertEqual(decision["risk_level"], "high")
        self.assertFalse(decision["auto_applied"])
        self.assertEqual(decision["action"], "relax_quality_threshold")


if __name__ == "__main__":
    unittest.main()
