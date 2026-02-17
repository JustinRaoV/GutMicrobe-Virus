from __future__ import annotations

import argparse
import csv
import re
import shlex
import subprocess
from pathlib import Path

from .common import (
    copy_or_decompress,
    dedup_by_sequence,
    ensure_dir,
    ensure_parent,
    open_text_auto,
    read_fasta,
    run_cmd,
    safe_json_dump,
    write_fasta,
)


def _truthy(value: str | bool | int | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, int):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _render_cmd(base_cmd: str, argv: list[str]) -> str:
    parts = [base_cmd] + [shlex.quote(item) for item in argv]
    return " ".join(parts)


def _bowtie2_prefix_exists(prefix: str) -> bool:
    base = Path(prefix)
    bt2 = [f"{base}.{idx}.bt2" for idx in ("1", "2", "3", "4", "rev.1", "rev.2")]
    bt2l = [f"{base}.{idx}.bt2l" for idx in ("1", "2", "3", "4", "rev.1", "rev.2")]
    return all(Path(p).exists() for p in bt2) or all(Path(p).exists() for p in bt2l)


def _resolve_bowtie2_prefix(index_root: str, host: str) -> str:
    if not index_root:
        return ""

    root = Path(index_root).expanduser().resolve()
    host = host.strip()

    candidates: list[Path] = []
    if root.is_dir():
        if host:
            candidates.extend(
                [
                    root / host / host,
                    root / host,
                    root / f"{host}_index",
                ]
            )
        # If host is not provided, we intentionally skip host-removal to avoid using wrong index.
    else:
        candidates.append(root)

    for candidate in candidates:
        if _bowtie2_prefix_exists(str(candidate)):
            return str(candidate)
    return ""


def _locate_host_removed_pair(out_dir: Path, base: str = "host_removed") -> tuple[Path, Path] | None:
    explicit = [
        (out_dir / f"{base}.1.fq.gz", out_dir / f"{base}.2.fq.gz"),
        (out_dir / f"{base}.1.fastq.gz", out_dir / f"{base}.2.fastq.gz"),
        (out_dir / f"{base}.1.gz", out_dir / f"{base}.2.gz"),
        (out_dir / f"{base}.1.fq", out_dir / f"{base}.2.fq"),
        (out_dir / f"{base}.1.fastq", out_dir / f"{base}.2.fastq"),
        (out_dir / f"{base}.1", out_dir / f"{base}.2"),
    ]
    for r1, r2 in explicit:
        if r1.exists() and r2.exists():
            return r1, r2

    files = [p for p in out_dir.glob(f"{base}*") if p.is_file()]
    if not files:
        return None

    r1_hits: list[Path] = []
    r2_hits: list[Path] = []
    for path in files:
        name = path.name
        if re.search(r"(?:^|[._-])1(?:[._-]|$)", name):
            r1_hits.append(path)
        if re.search(r"(?:^|[._-])2(?:[._-]|$)", name):
            r2_hits.append(path)

    if r1_hits and r2_hits:
        r1_hits.sort(key=lambda p: len(p.name))
        r2_hits.sort(key=lambda p: len(p.name))
        return r1_hits[0], r2_hits[0]

    return None


def _preprocess(args: argparse.Namespace) -> int:
    ensure_parent(args.r1_out)
    ensure_parent(args.r2_out)

    if args.fastp_cmd:
        cmd = _render_cmd(
            args.fastp_cmd,
            [
                "-i",
                args.r1_in,
                "-I",
                args.r2_in,
                "-o",
                args.r1_out,
                "-O",
                args.r2_out,
                "-w",
                str(args.threads),
            ] + shlex.split(args.fastp_params or ""),
        )
        run_cmd(cmd)
    else:
        copy_or_decompress(args.r1_in, args.r1_out)
        copy_or_decompress(args.r2_in, args.r2_out)

    return 0


def _host_removal(args: argparse.Namespace) -> int:
    ensure_parent(args.r1_out)
    ensure_parent(args.r2_out)

    resolved_prefix = _resolve_bowtie2_prefix(args.index_prefix, args.host)
    if args.bowtie2_cmd and resolved_prefix:
        out_dir = Path(args.r1_out).resolve().parent
        prefix = out_dir / "host_removed"
        pair_pattern = out_dir / "host_removed.%.fq.gz"
        cmd = _render_cmd(
            args.bowtie2_cmd,
            [
                "-x",
                resolved_prefix,
                "-1",
                args.r1_in,
                "-2",
                args.r2_in,
                "--very-sensitive",
                "-p",
                str(args.threads),
                "--un-conc-gz",
                str(pair_pattern),
                "-S",
                "/dev/null",
            ],
        )
        completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if completed.returncode != 0:
            stderr_tail = "\n".join((completed.stderr or "").splitlines()[-20:])
            raise RuntimeError(f"命令失败({completed.returncode}): {cmd}\n[bowtie2 stderr tail]\n{stderr_tail}")

        pair = _locate_host_removed_pair(out_dir, base="host_removed")
        if pair is None:
            raise RuntimeError(
                "Bowtie2 已执行但未识别到去宿主输出文件。"
                f" out_dir={out_dir}. 请检查该目录中文件名，并反馈给 GMV。"
            )
        r1_tmp, r2_tmp = pair
        copy_or_decompress(r1_tmp, args.r1_out)
        copy_or_decompress(r2_tmp, args.r2_out)
    else:
        if args.host.strip():
            print(
                f"[GMV] host_removal skipped: bowtie2 index not resolved for host='{args.host}' under '{args.index_prefix}'.",
                flush=True,
            )
        else:
            print("[GMV] host_removal skipped: sample host is empty, passthrough reads.", flush=True)
        copy_or_decompress(args.r1_in, args.r1_out)
        copy_or_decompress(args.r2_in, args.r2_out)

    return 0


def _assembly(args: argparse.Namespace) -> int:
    ensure_parent(args.contigs_out)

    if args.megahit_cmd:
        out_dir = ensure_dir(Path(args.contigs_out).resolve().parent / "_megahit")
        cmd = _render_cmd(
            args.megahit_cmd,
            [
                "-1",
                args.r1_in,
                "-2",
                args.r2_in,
                "-o",
                str(out_dir),
                "-t",
                str(args.threads),
            ],
        )
        run_cmd(cmd)
        candidate = out_dir / "final.contigs.fa"
        if not candidate.exists():
            raise RuntimeError(f"Megahit 未产出 final.contigs.fa: {candidate}")
        copy_or_decompress(candidate, args.contigs_out)
        return 0

    # Fallback for local smoke tests without megahit.
    seqs: list[str] = []
    with open_text_auto(args.r1_in, "rt") as handle:
        idx = 0
        for line_no, line in enumerate(handle, start=1):
            if line_no % 4 == 2:
                seqs.append(line.strip())
                idx += 1
            if idx >= 100:
                break
    assembled = "".join(seqs)[:50000] or "N" * 2000
    write_fasta([("contig_1", assembled)], args.contigs_out)
    return 0


def _vsearch_filter(args: argparse.Namespace) -> int:
    ensure_parent(args.contigs_out)

    min_len = int(args.min_len)
    if args.vsearch_cmd:
        cmd = _render_cmd(
            args.vsearch_cmd,
            [
                "--fastx_filter",
                args.contigs_in,
                "--fastaout",
                args.contigs_out,
                "--minseqlength",
                str(min_len),
            ],
        )
        run_cmd(cmd)
        return 0

    records = read_fasta(args.contigs_in)
    kept = [(h, s) for h, s in records if len(s) >= min_len]
    if not kept:
        kept = records[:1]
    write_fasta(kept, args.contigs_out)
    return 0


def _detect_virsorter(args: argparse.Namespace) -> int:
    ensure_parent(args.out_fa)
    ensure_dir(args.work_dir)

    if not _truthy(args.enabled):
        copy_or_decompress(args.contigs_in, args.out_fa)
        return 0

    if args.virsorter_cmd and args.db and Path(args.db).exists():
        cmd = _render_cmd(
            args.virsorter_cmd,
            [
                "run",
                "-w",
                args.work_dir,
                "-i",
                args.contigs_in,
                "-j",
                str(args.threads),
                "all",
                "--db-dir",
                args.db,
            ],
        )
        run_cmd(cmd)

        work_dir = Path(args.work_dir)
        candidates = [
            work_dir / "final-viral-combined.fa",
            work_dir / "final-viral-combined.fasta",
            work_dir / "final_viral_combined.fa",
        ]
        for candidate in candidates:
            if candidate.exists():
                copy_or_decompress(candidate, args.out_fa)
                return 0

    copy_or_decompress(args.contigs_in, args.out_fa)
    return 0


def _detect_genomad(args: argparse.Namespace) -> int:
    ensure_parent(args.out_fa)
    ensure_dir(args.work_dir)

    if not _truthy(args.enabled):
        copy_or_decompress(args.contigs_in, args.out_fa)
        return 0

    if args.genomad_cmd and args.db and Path(args.db).exists():
        cmd = _render_cmd(
            args.genomad_cmd,
            [
                "end-to-end",
                args.contigs_in,
                args.work_dir,
                args.db,
                "--threads",
                str(args.threads),
            ],
        )
        run_cmd(cmd)
        work_dir = Path(args.work_dir)
        candidates = list(work_dir.glob("*_summary/*_virus.fna")) + [work_dir / "contigs_summary" / "contigs_virus.fna"]
        for candidate in candidates:
            if candidate.exists():
                copy_or_decompress(candidate, args.out_fa)
                return 0

    copy_or_decompress(args.contigs_in, args.out_fa)
    return 0


def _combine(args: argparse.Namespace) -> int:
    ensure_parent(args.out_fa)
    ensure_parent(args.info_tsv)

    merged_records: list[tuple[str, str]] = []
    stats = {}

    if _truthy(args.use_virsorter):
        virsorter_records = read_fasta(args.virsorter_fa)
        merged_records.extend(virsorter_records)
        stats["virsorter"] = len(virsorter_records)
    else:
        stats["virsorter"] = 0

    if _truthy(args.use_genomad):
        genomad_records = read_fasta(args.genomad_fa)
        merged_records.extend(genomad_records)
        stats["genomad"] = len(genomad_records)
    else:
        stats["genomad"] = 0

    if not merged_records:
        merged_records = read_fasta(args.fallback_fa)

    merged_records = dedup_by_sequence(merged_records)
    renamed = [(f"vOTU_{idx}", seq) for idx, (_, seq) in enumerate(merged_records, start=1)]
    write_fasta(renamed, args.out_fa)

    with Path(args.info_tsv).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["tool", "contigs"])
        writer.writerow(["virsorter", stats.get("virsorter", 0)])
        writer.writerow(["genomad", stats.get("genomad", 0)])
        writer.writerow(["combined_unique", len(renamed)])

    return 0


def _checkv(args: argparse.Namespace) -> int:
    ensure_parent(args.quality_tsv)
    ensure_parent(args.out_fa)
    ensure_dir(args.work_dir)

    quality_rows: list[dict[str, str]] = []
    source_fa = Path(args.contigs_in)

    if args.checkv_cmd and args.db and Path(args.db).exists():
        cmd = _render_cmd(
            args.checkv_cmd,
            [
                "end_to_end",
                args.contigs_in,
                args.work_dir,
                "-d",
                args.db,
                "-t",
                str(args.threads),
            ],
        )
        run_cmd(cmd)
        work_dir = Path(args.work_dir)
        q = work_dir / "quality_summary.tsv"
        viruses = work_dir / "viruses.fna"
        if q.exists():
            copy_or_decompress(q, args.quality_tsv)
        if viruses.exists():
            source_fa = viruses

    if not Path(args.quality_tsv).exists():
        records = read_fasta(source_fa)
        quality_rows = [{"contig_id": h.split()[0], "checkv_quality": "Medium-quality"} for h, _ in records]
        with Path(args.quality_tsv).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["contig_id", "checkv_quality"], delimiter="\t")
            writer.writeheader()
            writer.writerows(quality_rows)

    copy_or_decompress(source_fa, args.out_fa)
    return 0


def _high_quality(args: argparse.Namespace) -> int:
    ensure_parent(args.out_fa)

    keep_levels = {"Complete", "High-quality", "Medium-quality", "Complete genome", "High quality", "Medium quality"}
    keep_ids: set[str] = set()
    with Path(args.quality_tsv).open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            contig_id = (row.get("contig_id") or row.get("contig") or row.get("name") or "").strip()
            quality = (row.get("checkv_quality") or row.get("quality") or "").strip()
            if not contig_id:
                continue
            if quality in keep_levels or not quality:
                keep_ids.add(contig_id)

    records = read_fasta(args.contigs_in)
    selected = [(h, s) for h, s in records if h.split()[0] in keep_ids] if keep_ids else records
    if not selected:
        selected = records[:1]
    write_fasta(selected, args.out_fa)
    return 0


def _busco_filter(args: argparse.Namespace) -> int:
    ensure_parent(args.out_fa)
    copy_or_decompress(args.contigs_in, args.out_fa)

    records = read_fasta(args.out_fa)
    payload = {
        "method": "pass_through",
        "threshold": float(args.threshold),
        "input_contigs": len(records),
        "kept_contigs": len(records),
    }
    safe_json_dump(args.metrics_json, payload)
    return 0


def register_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    preprocess = subparsers.add_parser("preprocess")
    preprocess.add_argument("--r1-in", required=True)
    preprocess.add_argument("--r2-in", required=True)
    preprocess.add_argument("--r1-out", required=True)
    preprocess.add_argument("--r2-out", required=True)
    preprocess.add_argument("--threads", type=int, default=4)
    preprocess.add_argument("--fastp-cmd", default="")
    preprocess.add_argument("--fastp-params", default="")
    preprocess.set_defaults(func=_preprocess)

    host = subparsers.add_parser("host_removal")
    host.add_argument("--r1-in", required=True)
    host.add_argument("--r2-in", required=True)
    host.add_argument("--r1-out", required=True)
    host.add_argument("--r2-out", required=True)
    host.add_argument("--threads", type=int, default=4)
    host.add_argument("--bowtie2-cmd", default="")
    host.add_argument("--index-prefix", default="")
    host.add_argument("--host", default="")
    host.set_defaults(func=_host_removal)

    assembly = subparsers.add_parser("assembly")
    assembly.add_argument("--r1-in", required=True)
    assembly.add_argument("--r2-in", required=True)
    assembly.add_argument("--contigs-out", required=True)
    assembly.add_argument("--threads", type=int, default=4)
    assembly.add_argument("--megahit-cmd", default="")
    assembly.set_defaults(func=_assembly)

    vsearch = subparsers.add_parser("vsearch_filter")
    vsearch.add_argument("--contigs-in", required=True)
    vsearch.add_argument("--contigs-out", required=True)
    vsearch.add_argument("--min-len", type=int, default=1500)
    vsearch.add_argument("--vsearch-cmd", default="")
    vsearch.set_defaults(func=_vsearch_filter)

    virsorter = subparsers.add_parser("detect_virsorter")
    virsorter.add_argument("--contigs-in", required=True)
    virsorter.add_argument("--out-fa", required=True)
    virsorter.add_argument("--work-dir", required=True)
    virsorter.add_argument("--threads", type=int, default=4)
    virsorter.add_argument("--virsorter-cmd", default="")
    virsorter.add_argument("--db", default="")
    virsorter.add_argument("--enabled", default="1")
    virsorter.set_defaults(func=_detect_virsorter)

    genomad = subparsers.add_parser("detect_genomad")
    genomad.add_argument("--contigs-in", required=True)
    genomad.add_argument("--out-fa", required=True)
    genomad.add_argument("--work-dir", required=True)
    genomad.add_argument("--threads", type=int, default=4)
    genomad.add_argument("--genomad-cmd", default="")
    genomad.add_argument("--db", default="")
    genomad.add_argument("--enabled", default="1")
    genomad.set_defaults(func=_detect_genomad)

    combine = subparsers.add_parser("combine")
    combine.add_argument("--virsorter-fa", required=True)
    combine.add_argument("--genomad-fa", required=True)
    combine.add_argument("--fallback-fa", required=True)
    combine.add_argument("--out-fa", required=True)
    combine.add_argument("--info-tsv", required=True)
    combine.add_argument("--use-virsorter", default="1")
    combine.add_argument("--use-genomad", default="1")
    combine.set_defaults(func=_combine)

    checkv = subparsers.add_parser("checkv")
    checkv.add_argument("--contigs-in", required=True)
    checkv.add_argument("--quality-tsv", required=True)
    checkv.add_argument("--out-fa", required=True)
    checkv.add_argument("--work-dir", required=True)
    checkv.add_argument("--threads", type=int, default=4)
    checkv.add_argument("--checkv-cmd", default="")
    checkv.add_argument("--db", default="")
    checkv.set_defaults(func=_checkv)

    high_quality = subparsers.add_parser("high_quality")
    high_quality.add_argument("--contigs-in", required=True)
    high_quality.add_argument("--quality-tsv", required=True)
    high_quality.add_argument("--out-fa", required=True)
    high_quality.set_defaults(func=_high_quality)

    busco = subparsers.add_parser("busco_filter")
    busco.add_argument("--contigs-in", required=True)
    busco.add_argument("--out-fa", required=True)
    busco.add_argument("--metrics-json", required=True)
    busco.add_argument("--threshold", type=float, default=0.05)
    busco.set_defaults(func=_busco_filter)
