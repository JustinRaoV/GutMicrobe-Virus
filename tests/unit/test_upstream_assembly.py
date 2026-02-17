from __future__ import annotations

import argparse
import gzip
from pathlib import Path

from gmv.workflow.steps import upstream


def _mk_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        r1_in=str(tmp_path / "in_R1.fq.gz"),
        r2_in=str(tmp_path / "in_R2.fq.gz"),
        contigs_out=str(tmp_path / "out" / "contigs.fa"),
        threads=8,
        megahit_cmd="megahit",
    )


def test_assembly_reuses_existing_final_contigs(tmp_path: Path, monkeypatch) -> None:
    args = _mk_args(tmp_path)
    out_dir = Path(args.contigs_out).parent / "_megahit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "final.contigs.fa").write_text(">c1\nACGT\n", encoding="utf-8")

    called = {"run": False}

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called["run"] = True

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)

    rc = upstream._assembly(args)

    assert rc == 0
    assert called["run"] is False
    assert Path(args.contigs_out).read_text(encoding="utf-8").startswith(">c1")


def test_assembly_cleans_stale_dir_then_runs(tmp_path: Path, monkeypatch) -> None:
    args = _mk_args(tmp_path)
    out_dir = Path(args.contigs_out).parent / "_megahit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stale.txt").write_text("x", encoding="utf-8")

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        (out_dir / "final.contigs.fa").write_text(">c2\nTGCA\n", encoding="utf-8")

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)

    rc = upstream._assembly(args)

    assert rc == 0
    assert Path(args.contigs_out).read_text(encoding="utf-8").startswith(">c2")


def test_assembly_fallback_when_no_reads_left(tmp_path: Path, monkeypatch) -> None:
    args = _mk_args(tmp_path)
    for fq in (Path(args.r1_in), Path(args.r2_in)):
        fq.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(fq, "wt", encoding="utf-8") as handle:
            handle.write("")

    called = {"run": False}

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called["run"] = True

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)
    rc = upstream._assembly(args)

    assert rc == 0
    assert called["run"] is False
    assert Path(args.contigs_out).exists()
    assert Path(args.contigs_out).read_text(encoding="utf-8").startswith(">contig_1")


def test_assembly_fallback_when_reads_too_short_for_megahit(tmp_path: Path, monkeypatch) -> None:
    args = _mk_args(tmp_path)
    short_record = "@r1\nACGTACGTAC\n+\nIIIIIIIIII\n"
    for fq in (Path(args.r1_in), Path(args.r2_in)):
        fq.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(fq, "wt", encoding="utf-8") as handle:
            handle.write(short_record)

    called = {"run": False}

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called["run"] = True

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)
    rc = upstream._assembly(args)

    assert rc == 0
    assert called["run"] is False
    assert Path(args.contigs_out).exists()
