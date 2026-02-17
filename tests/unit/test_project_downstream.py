from __future__ import annotations

import argparse
from pathlib import Path

from gmv.workflow.steps import project


def test_downstream_quant_uses_coverm_short_output_flag(tmp_path: Path, monkeypatch) -> None:
    sample_sheet = tmp_path / "samples.tsv"
    sample_sheet.write_text(
        "sample\tinput1\tinput2\ns1\t/r1.fq.gz\t/r2.fq.gz\n",
        encoding="utf-8",
    )
    viruslib = tmp_path / "viruslib.fa"
    viruslib.write_text(">v1\nACGT\n", encoding="utf-8")
    abundance = tmp_path / "abundance.tsv"

    args = argparse.Namespace(
        viruslib_fa=str(viruslib),
        sample_sheet=str(sample_sheet),
        abundance_out=str(abundance),
        threads=4,
        coverm_cmd="coverm",
        coverm_params="",
        enabled="1",
    )

    called: list[str] = []

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called.append(cmd)
        abundance.write_text("genome\ts1\nv1\t1\n", encoding="utf-8")

    monkeypatch.setattr(project, "run_cmd", _fake_run)
    rc = project._downstream_quant(args)

    assert rc == 0
    assert len(called) == 1
    assert " -o " in called[0]
    assert "--output-file" not in called[0]
