import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.chat.tools import TOOL_SPECS, sanitize_args, tool_risk


class ChatExecutorTests(unittest.TestCase):
    def test_whitelist_contains_expected_tools(self):
        for name in (
            "gmv_validate",
            "gmv_run",
            "gmv_report",
            "slurm_squeue",
            "slurm_sacct",
            "slurm_scontrol_show_job",
            "slurm_scancel",
            "tail_file",
            "show_latest_snakemake_log",
        ):
            self.assertIn(name, TOOL_SPECS)

    def test_high_risk_classification(self):
        self.assertEqual(
            tool_risk("gmv_run", {"config_path": "x", "profile": "local", "stage": "all", "dry_run": False}),
            "high",
        )
        self.assertEqual(tool_risk("slurm_scancel", {"job_id": "1"}), "high")
        self.assertEqual(
            tool_risk("gmv_run", {"config_path": "x", "profile": "local", "stage": "all", "dry_run": True}),
            "low",
        )

    def test_sanitizer_rejects_shell_metacharacters(self):
        with self.assertRaises(ValueError):
            sanitize_args("slurm_squeue", {"user": "bad;rm -rf /"})


if __name__ == "__main__":
    unittest.main()
