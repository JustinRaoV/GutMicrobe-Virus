import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.workflow.resources import DEFAULT_TOOL_ESTIMATES, estimate_tool_resources


class ResourceEstimationTests(unittest.TestCase):
    def test_zero_input_size_still_returns_base_like_resources(self):
        cfg = {"enabled": True, "fudge": 1.2, "overrides": {}}
        mem_mb, runtime = estimate_tool_resources("fastp", size_mb=0.0, estimation_cfg=cfg)
        self.assertGreaterEqual(mem_mb, DEFAULT_TOOL_ESTIMATES["fastp"]["mem_mb_base"])
        self.assertGreaterEqual(runtime, DEFAULT_TOOL_ESTIMATES["fastp"]["runtime_base"])

    def test_clamp_applies(self):
        cfg = {
            "enabled": True,
            "fudge": 10.0,
            "overrides": {
                "fastp": {
                    "mem_mb_base": 100,
                    "mem_mb_per_gb": 100000,
                    "runtime_base": 10,
                    "runtime_per_gb": 10000,
                    "mem_mb_max": 1000,
                    "runtime_max": 100,
                }
            },
        }
        mem_mb, runtime = estimate_tool_resources("fastp", size_mb=1024.0, estimation_cfg=cfg)
        self.assertEqual(mem_mb, 1000)
        self.assertEqual(runtime, 100)

    def test_estimation_disabled_falls_back_to_small_defaults(self):
        cfg = {"enabled": False, "fudge": 1.2, "overrides": {}}
        mem_mb, runtime = estimate_tool_resources("fastp", size_mb=1024.0, estimation_cfg=cfg)
        self.assertEqual(mem_mb, DEFAULT_TOOL_ESTIMATES["fastp"]["mem_mb_base"])
        self.assertEqual(runtime, DEFAULT_TOOL_ESTIMATES["fastp"]["runtime_base"])


if __name__ == "__main__":
    unittest.main()

