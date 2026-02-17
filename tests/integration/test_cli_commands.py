import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CliIntegrationTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, **{"PYTHONPATH": str(ROOT / "src")}}
        return subprocess.run(
            [sys.executable, "-m", "gmv.cli", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_validate_command(self):
        cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        proc = self._run("validate", "--config", str(cfg))
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("配置校验通过", proc.stdout + proc.stderr)

    def test_cli_help_only_exposes_v3_commands(self):
        proc = self._run("--help")
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        help_text = proc.stdout + proc.stderr
        for cmd in ("validate", "run", "report", "chat"):
            self.assertIn(cmd, help_text)
        for removed in ("profile", "agent replay", "agent harvest", "agent chat"):
            self.assertNotIn(removed, help_text)


if __name__ == "__main__":
    unittest.main()
