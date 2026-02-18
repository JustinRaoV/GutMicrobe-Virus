from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from gmv.workflow.steps import upstream


def _mk_args(tmp_path: Path) -> argparse.Namespace:
    contigs_in = tmp_path / "in.fa"
    contigs_in.write_text(">c1\nACGT\n", encoding="utf-8")
    db = tmp_path / "db"
    db.mkdir(parents=True, exist_ok=True)
    return argparse.Namespace(
        contigs_in=str(contigs_in),
        out_fa=str(tmp_path / "out" / "contigs.fa"),
        work_dir=str(tmp_path / "work"),
        threads=2,
        virsorter_cmd="virsorter",
        db=str(db),
        enabled="1",
    )


def test_detect_virsorter_command_uses_offline_container_pattern(tmp_path: Path, monkeypatch) -> None:
    args = _mk_args(tmp_path)
    called: list[str] = []

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called.append(cmd)
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "final-viral-combined.fa").write_text(">v1\nACGT\n", encoding="utf-8")

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)
    rc = upstream._detect_virsorter(args)

    assert rc == 0
    assert len(called) == 1
    tokens = shlex.split(called[0])
    assert "-d" in tokens
    assert "all" in tokens
    assert tokens.index("-d") < tokens.index("all")
    assert Path(args.out_fa).exists()


def test_detect_virsorter_runs_without_d_when_db_missing(tmp_path: Path, monkeypatch) -> None:
    args = _mk_args(tmp_path)
    args.db = str(tmp_path / "missing-db")
    called: list[str] = []

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called.append(cmd)
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "final-viral-combined.fa").write_text(">v2\nTGCA\n", encoding="utf-8")

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)
    rc = upstream._detect_virsorter(args)

    assert rc == 0
    assert len(called) == 1
    tokens = shlex.split(called[0])
    assert "-d" not in tokens
    assert "all" in tokens
    assert Path(args.out_fa).exists()


def test_detect_virsorter_container_mode_ignores_external_db(tmp_path: Path, monkeypatch) -> None:
    args = _mk_args(tmp_path)
    args.virsorter_cmd = "singularity exec /x/virsorter2.sif virsorter"
    called: list[str] = []

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called.append(cmd)
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "final-viral-combined.fa").write_text(">v3\nAAAA\n", encoding="utf-8")

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)
    rc = upstream._detect_virsorter(args)

    assert rc == 0
    assert len(called) == 1
    tokens = shlex.split(called[0])
    assert "-d" not in tokens
    assert "all" in tokens
    assert Path(args.out_fa).exists()
