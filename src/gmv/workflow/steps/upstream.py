"""Upstream step implementations."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import Dict, List

from gmv.workflow.steps.common import copy_file, read_fasta, run_shell, write_fasta, write_fasta_filtered


def step_preprocess(args: argparse.Namespace) -> None:
    if args.mock:
        copy_file(args.r1_in, args.r1_out)
        copy_file(args.r2_in, args.r2_out)
        return
    cmd = (
        f"{args.fastp_cmd} -i {args.r1_in} -I {args.r2_in} "
        f"-o {args.r1_out} -O {args.r2_out} -w {args.threads} {args.fastp_params}"
    ).strip()
    run_shell(cmd)


def step_host_removal(args: argparse.Namespace) -> None:
    if args.mock or not args.host:
        copy_file(args.r1_in, args.r1_out)
        copy_file(args.r2_in, args.r2_out)
        return

    cmd = (
        f"{args.bowtie2_cmd} -x {args.host_index} -1 {args.r1_in} -2 {args.r2_in} "
        f"--un-conc {args.prefix}.tmp.fq -S {args.prefix}.sam -p {args.threads}"
    )
    run_shell(cmd)
    copy_file(f"{args.prefix}.tmp.fq.1", args.r1_out)
    copy_file(f"{args.prefix}.tmp.fq.2", args.r2_out)


def step_assembly(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "contigs":
        copy_file(args.input1, args.out)
        return

    if args.mock:
        write_fasta(args.out, [(f"{args.sample}_contig1", "ATGCGT" * 600)])
        return

    temp_dir = out.parent / "megahit_out"
    cmd = (
        f"{args.megahit_cmd} -1 {args.input1} -2 {args.input2} "
        f"-o {temp_dir} -t {args.threads} {args.megahit_params}"
    ).strip()
    run_shell(cmd)
    copy_file(str(temp_dir / "final.contigs.fa"), args.out)


def step_vsearch(args: argparse.Namespace) -> None:
    if args.mock:
        kept = [(h, s) for h, s in read_fasta(args.input) if len(s) >= args.min_len]
        write_fasta(args.out, kept)
        return

    cmd = f"{args.vsearch_cmd} --sortbylength {args.input} --output {args.out} --minseqlength {args.min_len}"
    run_shell(cmd)


def step_detect(args: argparse.Namespace) -> None:
    if args.mock:
        suffix = "vs2" if args.tool == "virsorter" else "genomad"
        entries = [(f"{h}|{suffix}", s) for h, s in read_fasta(args.input)]
        write_fasta(args.out, entries)
        return

    if args.tool == "virsorter":
        cmd = f"{args.tool_cmd} run -i {args.input} -w {args.workdir} -j {args.threads} all"
        run_shell(cmd)
        copy_file(str(Path(args.workdir) / "final-viral-combined.fa"), args.out)
        return

    if args.tool == "genomad":
        cmd = f"{args.tool_cmd} end-to-end {args.input} {args.workdir} {args.db} -t {args.threads} --splits {args.threads}"
        run_shell(cmd)
        basename = Path(args.input).stem
        copy_file(str(Path(args.workdir) / f"{basename}_summary" / f"{basename}_virus.fna"), args.out)
        return

    raise ValueError(f"unsupported tool: {args.tool}")


def step_combine(args: argparse.Namespace) -> None:
    seen: Dict[str, str] = {}
    for path in args.inputs:
        file_path = Path(path)
        if not file_path.exists():
            continue
        for header, seq in read_fasta(str(file_path)):
            seen.setdefault(header, seq)
    write_fasta(args.out, sorted(seen.items()))


def step_checkv(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_fasta = out_dir / "contigs.fa"
    out_summary = out_dir / "quality_summary.tsv"

    if args.mock:
        entries = read_fasta(args.input)
        write_fasta(str(out_fasta), entries)
        with out_summary.open("w", encoding="utf-8") as fh:
            fh.write("contig_id\tcontig_length\tcheckv_quality\tcompleteness\n")
            for header, seq in entries:
                quality = "High-quality" if len(seq) >= 1500 else "Low-quality"
                completeness = 95.0 if quality == "High-quality" else 30.0
                fh.write(f"{header}\t{len(seq)}\t{quality}\t{completeness}\n")
        return

    cmd = f"{args.checkv_cmd} end_to_end {args.input} {args.out_dir} -d {args.db} -t {args.threads}"
    run_shell(cmd)
    copy_file(args.input, str(out_fasta))
    if not out_summary.exists():
        raise RuntimeError(f"CheckV 未生成 quality_summary.tsv: {out_summary}")


def step_high_quality(args: argparse.Namespace) -> None:
    keep: set[str] = set()
    with open(args.summary, "r", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            contig_id, _len, quality, _comp = line.rstrip("\n").split("\t")
            if quality in {"Complete", "High-quality", "Medium-quality"}:
                keep.add(contig_id)
    entries = [(h, s) for h, s in read_fasta(args.input) if h in keep]
    write_fasta(args.out, entries)


def step_busco(args: argparse.Namespace) -> None:
    if args.mock:
        copy_file(args.input, args.out)
        return

    out_dir = Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    busco_root = out_dir / "_busco"
    busco_root.mkdir(parents=True, exist_ok=True)

    cmd = (
        f"{args.busco_cmd} -f -i {shlex.quote(args.input)} -c {int(args.threads)} "
        f"-o busco -m geno -l {shlex.quote(args.busco_db)} --offline --out_path {shlex.quote(str(busco_root))}"
    )
    run_shell(cmd)

    predicted = next(busco_root.rglob("predicted.fna"), None)
    if predicted is None:
        raise RuntimeError(f"BUSCO 输出缺少 predicted.fna（目录: {busco_root}）")

    full_table = next(busco_root.rglob("full_table.tsv"), None)
    if full_table is None:
        raise RuntimeError(f"BUSCO 输出缺少 full_table.tsv（目录: {busco_root}）")

    gene_counts: Dict[str, int] = {}
    with predicted.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith(">"):
                continue
            record = line[1:].strip().split()[0]
            contig = record.rsplit("_", 1)[0] if "_" in record else record
            gene_counts[contig] = gene_counts.get(contig, 0) + 1

    busco_counts: Dict[str, int] = {}
    with full_table.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            status = parts[1].strip()
            if status not in {"Complete", "Fragmented"}:
                continue
            seq = parts[2].strip().split()[0]
            seq = seq.split(":", 1)[0]
            contig = seq.rsplit("_", 1)[0] if "_" in seq else seq
            busco_counts[contig] = busco_counts.get(contig, 0) + 1

    threshold = float(args.ratio_threshold)
    to_remove: set[str] = set()
    for contig, total in gene_counts.items():
        if total <= 0:
            continue
        if (busco_counts.get(contig, 0) / float(total)) > threshold:
            to_remove.add(contig)

    write_fasta_filtered(args.input, args.out, drop_ids=to_remove)


def register_upstream(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("preprocess")
    parser.add_argument("--r1-in", required=True)
    parser.add_argument("--r2-in", required=True)
    parser.add_argument("--r1-out", required=True)
    parser.add_argument("--r2-out", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--fastp-cmd", default="fastp")
    parser.add_argument("--fastp-params", default="")
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_preprocess)

    parser = subparsers.add_parser("host-removal")
    parser.add_argument("--r1-in", required=True)
    parser.add_argument("--r2-in", required=True)
    parser.add_argument("--r1-out", required=True)
    parser.add_argument("--r2-out", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--host", default="")
    parser.add_argument("--host-index", default="")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--bowtie2-cmd", default="bowtie2")
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_host_removal)

    parser = subparsers.add_parser("assembly")
    parser.add_argument("--mode", required=True, choices=["reads", "contigs"])
    parser.add_argument("--sample", required=True)
    parser.add_argument("--input1", required=True)
    parser.add_argument("--input2", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--megahit-cmd", default="megahit")
    parser.add_argument("--megahit-params", default="")
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_assembly)

    parser = subparsers.add_parser("vsearch")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-len", type=int, default=1500)
    parser.add_argument("--vsearch-cmd", default="vsearch")
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_vsearch)

    parser = subparsers.add_parser("detect")
    parser.add_argument("--tool", required=True, choices=["virsorter", "genomad"])
    parser.add_argument("--tool-cmd", required=True)
    parser.add_argument("--db", default="")
    parser.add_argument("--input", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_detect)

    parser = subparsers.add_parser("combine")
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.set_defaults(func=step_combine)

    parser = subparsers.add_parser("checkv")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--db", default="")
    parser.add_argument("--checkv-cmd", default="checkv")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_checkv)

    parser = subparsers.add_parser("high-quality")
    parser.add_argument("--input", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out", required=True)
    parser.set_defaults(func=step_high_quality)

    parser = subparsers.add_parser("busco")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--busco-cmd", default="busco")
    parser.add_argument("--busco-db", required=True)
    parser.add_argument("--ratio-threshold", type=float, default=0.05)
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_busco)
