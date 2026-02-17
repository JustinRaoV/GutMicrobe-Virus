"""Shared helpers for workflow step executors."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def copy_file(src: str, dst: str) -> None:
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_bytes(Path(src).read_bytes())


def run_shell(cmd: str) -> None:
    proc = subprocess.run(cmd, shell=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败: {cmd}")


def read_fasta(path: str) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    header = None
    chunks: List[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if header is not None:
                    entries.append((header, "".join(chunks)))
                header = line[1:].split()[0]
                chunks = []
            else:
                chunks.append(line)
    if header is not None:
        entries.append((header, "".join(chunks)))
    return entries


def write_fasta(path: str, entries: Iterable[Tuple[str, str]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for header, seq in entries:
            fh.write(f">{header}\n{seq}\n")


def write_fasta_filtered(
    input_fasta: str,
    output_fasta: str,
    *,
    keep_ids: set[str] | None = None,
    drop_ids: set[str] | None = None,
) -> None:
    if keep_ids is not None and drop_ids is not None:
        raise ValueError("keep_ids 和 drop_ids 不能同时提供")

    Path(output_fasta).parent.mkdir(parents=True, exist_ok=True)
    write = False
    with open(input_fasta, "r", encoding="utf-8") as fin, open(output_fasta, "w", encoding="utf-8") as fout:
        for line in fin:
            if line.startswith(">"):
                seq_id = line[1:].strip().split()[0]
                if keep_ids is not None:
                    write = seq_id in keep_ids
                elif drop_ids is not None:
                    write = seq_id not in drop_ids
                else:
                    write = True
            if write:
                fout.write(line)


def fasta_to_dict(path: str) -> Dict[str, str]:
    return {h: s for h, s in read_fasta(path)}
