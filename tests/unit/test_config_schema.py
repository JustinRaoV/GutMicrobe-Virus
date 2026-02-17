import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.config import ConfigError, load_pipeline_config


class ConfigSchemaTests(unittest.TestCase):
    def test_valid_pipeline_config_loads(self):
        cfg_path = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        config = load_pipeline_config(cfg_path)
        self.assertEqual(config["execution"]["run_id"], "test-run")
        self.assertTrue(config["execution"]["mock_mode"])
        self.assertIn("virsorter", config["tools"]["enabled"])

    def test_missing_required_section_raises(self):
        bad_cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "bad_missing_execution.yaml"
        bad_cfg.write_text("tools:\n  enabled: {}\n", encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_pipeline_config(bad_cfg)

    def test_estimation_fudge_must_be_ge_1(self):
        bad_cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "bad_estimation_fudge.yaml"
        bad_cfg.write_text(
            """
execution:
  run_id: x
  profile: local
  sample_sheet: ../raw/samples.tsv
containers:
  mapping_file: containers.yaml
tools:
  enabled: {}
resources:
  default_threads: 1
  estimation:
    enabled: true
    fudge: 0.9
database:
  checkv: ../db/checkv
  busco: ../db/busco
""".strip()
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(ConfigError):
            load_pipeline_config(bad_cfg)


if __name__ == "__main__":
    unittest.main()
