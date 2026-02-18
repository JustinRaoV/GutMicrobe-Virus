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
    assert "--use-conda-off" in tokens
    assert "all" in tokens
    assert tokens.index("-d") < tokens.index("all")
    assert tokens.index("--use-conda-off") < tokens.index("all")
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
    assert "--use-conda-off" in tokens
    assert "all" in tokens
    assert Path(args.out_fa).exists()


def test_detect_virsorter_retries_with_conda_when_no_conda_mode_lacks_modules(
    tmp_path: Path, monkeypatch
) -> None:
    args = _mk_args(tmp_path)
    called: list[str] = []

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called.append(cmd)
        if "--use-conda-off" in cmd:
            raise RuntimeError("命令失败(1): virsorter\nModuleNotFoundError: No module named 'screed'")
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "final-viral-combined.fa").write_text(">v3\nAAAA\n", encoding="utf-8")

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)
    rc = upstream._detect_virsorter(args)

    assert rc == 0
    assert len(called) == 2
    first = shlex.split(called[0])
    second = shlex.split(called[1])
    assert "--use-conda-off" in first
    assert "all" in first
    assert "--use-conda-off" not in second
    assert "all" in second
    assert "--conda-prefix" in second
    assert Path(args.out_fa).exists()
