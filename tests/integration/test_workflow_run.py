import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class WorkflowRunTests(unittest.TestCase):
    def test_gmv_run_dry_run_handles_missing_snakemake(self):
        cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        cmd = [sys.executable, "-m", "gmv.cli", "run", "--config", str(cfg), "--dry-run"]
        env = {**os.environ, **{"PYTHONPATH": str(ROOT / "src")}}
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        if shutil.which("snakemake"):
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        else:
            self.assertEqual(proc.returncode, 2, msg=proc.stdout + proc.stderr)
            self.assertIn("snakemake", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
