from __future__ import annotations

import argparse
from pathlib import Path

from gmv.workflow.steps import upstream


def _mk_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        contigs_in=str(tmp_path / "in.fa"),
        contigs_out=str(tmp_path / "out" / "contigs.fa"),
        min_len=1500,
        vsearch_cmd="vsearch",
    )


def test_vsearch_filter_prefers_fastq_minlen(tmp_path: Path, monkeypatch) -> None:
    args = _mk_args(tmp_path)
    called: list[str] = []

    def _fake_run(cmd: str, cwd: str | None = None, log_path: str | None = None) -> None:
        called.append(cmd)

    monkeypatch.setattr(upstream, "run_cmd", _fake_run)
    rc = upstream._vsearch_filter(args)

    assert rc == 0
    assert len(called) == 1
    assert "--fastq_minlen" in called[0]
