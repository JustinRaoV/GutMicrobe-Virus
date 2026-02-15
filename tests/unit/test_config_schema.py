import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.config_schema import ConfigValidationError, load_pipeline_config


class ConfigSchemaTests(unittest.TestCase):
    def test_valid_pipeline_config_loads(self):
        cfg_path = ROOT / "tests" / "fixtures" / "minimal" / "config" / "pipeline.yaml"
        config = load_pipeline_config(cfg_path)
        self.assertEqual(config["execution"]["run_id"], "test-run")
        self.assertTrue(config["execution"]["mock_mode"])
        self.assertIn("virsorter", config["tools"]["enabled"])
        # defaults
        self.assertIn("estimation", config["resources"])
        self.assertTrue(config["resources"]["estimation"]["enabled"])
        self.assertGreaterEqual(config["resources"]["estimation"]["fudge"], 1.0)

    def test_missing_required_section_raises(self):
        bad_cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "bad_missing_execution.yaml"
        bad_cfg.write_text("tools:\n  enabled: {}\n", encoding="utf-8")
        with self.assertRaises(ConfigValidationError):
            load_pipeline_config(bad_cfg)

    def test_enabled_tool_requires_container_mapping(self):
        bad_cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "bad_missing_tool_image.yaml"
        bad_cfg.write_text(
            """
execution:
  run_id: x
  profile: local
  raw_dir: ../raw
  work_dir: work
  cache_dir: cache
  results_dir: results
  reports_dir: reports
  sample_sheet: ../raw/samples.tsv
  use_singularity: true
  offline: true
  mock_mode: true
containers:
  mapping_file: bad_containers.yaml
tools:
  enabled:
    virsorter: true
agent:
  enabled: true
  auto_apply_risk_levels: [\"low\"]
  retry_limit: 1
  low_yield_threshold: 2
reporting:
  language: zh
  figure_language: en
resources:
  default_threads: 2
  slurm:
    account: \"\"
    partition: \"\"
    time: \"1:00:00\"
    mem_mb: 1024
database:
  virsorter: ../db/virsorter
""".strip()
            + "\n",
            encoding="utf-8",
        )
        (ROOT / "tests" / "fixtures" / "minimal" / "config" / "bad_containers.yaml").write_text(
            "images: {}\n", encoding="utf-8"
        )
        with self.assertRaises(ConfigValidationError):
            load_pipeline_config(bad_cfg)

    def test_estimation_fudge_must_be_ge_1(self):
        bad_cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "bad_estimation_fudge.yaml"
        bad_cfg.write_text(
            """
execution:
  run_id: x
  profile: local
  raw_dir: ../raw
  work_dir: work
  cache_dir: cache
  results_dir: results
  reports_dir: reports
  sample_sheet: ../raw/samples.tsv
  use_singularity: true
  offline: true
  mock_mode: true
containers:
  mapping_file: containers.yaml
tools:
  enabled: {}
agent:
  enabled: true
reporting:
  language: zh
  figure_language: en
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
        with self.assertRaises(ConfigValidationError):
            load_pipeline_config(bad_cfg)

    def test_estimation_overrides_must_be_mapping(self):
        bad_cfg = ROOT / "tests" / "fixtures" / "minimal" / "config" / "bad_estimation_overrides.yaml"
        bad_cfg.write_text(
            """
execution:
  run_id: x
  profile: local
  raw_dir: ../raw
  work_dir: work
  cache_dir: cache
  results_dir: results
  reports_dir: reports
  sample_sheet: ../raw/samples.tsv
  use_singularity: true
  offline: true
  mock_mode: true
containers:
  mapping_file: containers.yaml
tools:
  enabled: {}
agent:
  enabled: true
reporting:
  language: zh
  figure_language: en
resources:
  default_threads: 1
  estimation:
    enabled: true
    fudge: 1.2
    overrides: []
database:
  checkv: ../db/checkv
  busco: ../db/busco
""".strip()
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(ConfigValidationError):
            load_pipeline_config(bad_cfg)


if __name__ == "__main__":
    unittest.main()
