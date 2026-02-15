import subprocess
import sys
import unittest
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CliIntegrationTests(unittest.TestCase):
    def test_validate_command(self):
        cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        cmd = [sys.executable, "-m", "gmv.cli", "validate", "--config", str(cfg)]
        env = {**os.environ, **{"PYTHONPATH": str(ROOT / "src")}}
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("配置校验通过", proc.stdout)

    def test_agent_replay_command(self):
        replay_file = ROOT / "tests" / "fixtures" / "minimal" / "results" / "decisions.jsonl"
        replay_file.parent.mkdir(parents=True, exist_ok=True)
        replay_file.write_text(
            '{"step":"genomad","signal":{"status":"failed","error_type":"oom","attempt":1}}\n',
            encoding="utf-8",
        )
        cmd = [sys.executable, "-m", "gmv.cli", "agent", "replay", "--file", str(replay_file)]
        env = {**os.environ, **{"PYTHONPATH": str(ROOT / "src")}}
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("genomad", proc.stdout)

    def test_agent_harvest_command_creates_overrides_file(self):
        cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        out_file = ROOT / "results" / "test-run" / "agent" / "resources_overrides.yaml"
        if out_file.exists():
            out_file.unlink()

        cmd = [sys.executable, "-m", "gmv.cli", "agent", "harvest", "--config", str(cfg), "--run-id", "test-run"]
        env = {**os.environ, **{"PYTHONPATH": str(ROOT / "src")}}
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertTrue(out_file.exists(), msg="missing resources_overrides.yaml")


if __name__ == "__main__":
    unittest.main()
