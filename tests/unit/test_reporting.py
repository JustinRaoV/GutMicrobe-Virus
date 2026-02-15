import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.reporting.generator import generate_report


class ReportingTests(unittest.TestCase):
    def test_generate_report_outputs_files(self):
        run_id = "report-test"
        decision_dir = ROOT / "results" / run_id / "agent"
        decision_dir.mkdir(parents=True, exist_ok=True)
        decisions_file = decision_dir / "decisions.jsonl"
        decisions_file.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "step": "genomad",
                            "risk_level": "low",
                            "action": "increase_resources",
                            "auto_applied": True,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "step": "high_quality",
                            "risk_level": "high",
                            "action": "relax_quality_threshold",
                            "auto_applied": False,
                            "timestamp": "2026-01-01T00:01:00+00:00",
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        out = generate_report(results_dir=ROOT / "results", reports_dir=ROOT / "reports", run_id=run_id)
        for k in ("methods", "action_figure", "risk_figure", "table"):
            self.assertTrue(Path(out[k]).exists(), msg=f"missing output: {k}")


if __name__ == "__main__":
    unittest.main()
