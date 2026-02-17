import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.workflow.steps import build_parser


class WorkflowStepsDispatchTests(unittest.TestCase):
    def test_required_step_commands_exist(self):
        parser = build_parser()
        actions = parser._subparsers._group_actions  # type: ignore[attr-defined]
        choices = {}
        for action in actions:
            if getattr(action, "choices", None):
                choices = action.choices
                break
        for step in ("preprocess", "assembly", "downstream", "agent"):
            self.assertIn(step, choices)


if __name__ == "__main__":
    unittest.main()
