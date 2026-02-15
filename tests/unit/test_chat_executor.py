import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.agent.chat.executor import execute_tool


class ChatExecutorTests(unittest.TestCase):
    def setUp(self):
        self.log_dir = ROOT / "results" / "chat-test" / "agent" / "chat"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def test_high_risk_blocked_in_non_interactive_without_auto_approve(self):
        cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        res = execute_tool(
            "gmv_run",
            {"config_path": str(cfg), "profile": "local", "stage": "upstream", "dry_run": False, "cores": None},
            config_path=str(cfg),
            auto_approve=False,
            interactive=False,
            dry_run_tools=True,
            log_dir=self.log_dir,
        )
        self.assertEqual(res.returncode, 3)
        self.assertIn("确认", res.stderr_tail)

    def test_sanitizer_rejects_shell_metacharacters(self):
        cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        with self.assertRaises(ValueError):
            execute_tool(
                "slurm_squeue",
                {"user": "bad;rm -rf /"},
                config_path=str(cfg),
                auto_approve=True,
                interactive=False,
                dry_run_tools=True,
                log_dir=self.log_dir,
            )


if __name__ == "__main__":
    unittest.main()

