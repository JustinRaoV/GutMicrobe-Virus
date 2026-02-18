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


def test_downstream_quant_writes_failure_note_and_fallback_table(tmp_path: Path, monkeypatch) -> None:
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
        threads=2,
        coverm_cmd="coverm",
        coverm_params="--methods count",
        enabled="1",
    )

    def _fake_run(_cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        raise RuntimeError("coverm failed")

    monkeypatch.setattr(project, "run_cmd", _fake_run)
    rc = project._downstream_quant(args)

    assert rc == 0
    assert abundance.exists()
    failure_note = abundance.with_name("coverm.failure.txt")
    assert failure_note.exists()
    assert "coverm failed" in failure_note.read_text(encoding="utf-8")


def test_downstream_quant_splits_coverm_prefix_and_params(tmp_path: Path, monkeypatch) -> None:
    sample_sheet = tmp_path / "samples.tsv"
    sample_sheet.write_text(
        "sample\tinput1\tinput2\ns1\t/a/r1.fq.gz\t/a/r2.fq.gz\n",
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
        coverm_cmd="singularity exec -B /db /sif/coverm.sif coverm",
        coverm_params="--methods count --output-format dense",
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
    assert "singularity exec -B /db /sif/coverm.sif coverm genome" in called[0]
    assert "--methods count --output-format dense" in called[0]
