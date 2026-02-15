import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ChatOpsIntegrationTests(unittest.TestCase):
    def test_chat_mock_validate(self):
        cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        cmd = [sys.executable, "-m", "gmv.cli", "chat", "--config", str(cfg), "--message", "validate"]
        env = {**os.environ, **{"PYTHONPATH": str(ROOT / "src"), "GMV_CHAT_MOCK": "1"}}
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("gmv_validate", proc.stdout + proc.stderr)
        self.assertIn("rc=0", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()

