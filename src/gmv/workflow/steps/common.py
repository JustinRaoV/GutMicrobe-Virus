from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable


def ensure_parent(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def ensure_dir(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def run_cmd(cmd: str, cwd: str | None = None) -> None:
    completed = subprocess.run(cmd, shell=True, cwd=cwd)
    if completed.returncode != 0:
        raise RuntimeError(f"命令失败({completed.returncode}): {cmd}")


def copy_or_decompress(src: str | Path, dest: str | Path) -> None:
    src_path = Path(src).expanduser().resolve()
    dest_path = ensure_parent(dest)
    src_is_gz = src_path.suffix == ".gz"
    dest_is_gz = dest_path.suffix == ".gz"

    if src_is_gz and not dest_is_gz:
        with gzip.open(src_path, "rb") as fin, dest_path.open("wb") as fout:
            shutil.copyfileobj(fin, fout)
        return

    if not src_is_gz and dest_is_gz:
        with src_path.open("rb") as fin, gzip.open(dest_path, "wb") as fout:
            shutil.copyfileobj(fin, fout)
        return

    shutil.copy2(src_path, dest_path)


def open_text_auto(path: str | Path, mode: str = "rt"):
    target = Path(path).expanduser().resolve()
    if str(target).endswith(".gz"):
        return gzip.open(target, mode)
    return target.open(mode, encoding="utf-8")


def read_fasta(path: str | Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    header = ""
    chunks: list[str] = []
    with open_text_auto(path, "rt") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header:
                    records.append((header, "".join(chunks)))
                header = line[1:]
                chunks = []
            else:
                chunks.append(line)
    if header:
        records.append((header, "".join(chunks)))
    return records


def write_fasta(records: Iterable[tuple[str, str]], out_path: str | Path) -> None:
    target = ensure_parent(out_path)
    with target.open("w", encoding="utf-8") as handle:
        for header, seq in records:
            handle.write(f">{header}\n")
            for i in range(0, len(seq), 80):
                handle.write(seq[i : i + 80] + "\n")


def dedup_by_sequence(records: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for header, seq in records:
        if seq in seen:
            continue
        seen.add(seq)
        deduped.append((header, seq))
    return deduped


def safe_json_dump(path: str | Path, payload: object) -> None:
    target = ensure_parent(path)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
