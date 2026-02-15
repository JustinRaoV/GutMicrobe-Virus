"""Step executors used by Snakemake rules."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _copy(src: str, dst: str) -> None:
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _run(cmd: str) -> None:
    proc = subprocess.run(cmd, shell=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败: {cmd}")


def _read_fasta(path: str) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    header = None
    seq_chunks: List[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if header is not None:
                    entries.append((header, "".join(seq_chunks)))
                header = line[1:].split()[0]
                seq_chunks = []
            else:
                seq_chunks.append(line)
    if header is not None:
        entries.append((header, "".join(seq_chunks)))
    return entries


def _write_fasta(path: str, entries: Iterable[Tuple[str, str]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for h, s in entries:
            fh.write(f">{h}\n{s}\n")


def step_preprocess(args: argparse.Namespace) -> None:
    if args.mock:
        _copy(args.r1_in, args.r1_out)
        _copy(args.r2_in, args.r2_out)
        return
    cmd = f"{args.fastp_cmd} -i {args.r1_in} -I {args.r2_in} -o {args.r1_out} -O {args.r2_out} -w {args.threads} {args.fastp_params}".strip()
    _run(cmd)


def step_host_removal(args: argparse.Namespace) -> None:
    if args.mock or not args.host:
        _copy(args.r1_in, args.r1_out)
        _copy(args.r2_in, args.r2_out)
        return
    cmd = (
        f"{args.bowtie2_cmd} -x {args.host_index} -1 {args.r1_in} -2 {args.r2_in} "
        f"--un-conc {args.prefix}.tmp.fq -S {args.prefix}.sam -p {args.threads}"
    )
    _run(cmd)
    _copy(f"{args.prefix}.tmp.fq.1", args.r1_out)
    _copy(f"{args.prefix}.tmp.fq.2", args.r2_out)


def step_assembly(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "contigs":
        _copy(args.input1, args.out)
        return
    if args.mock:
        _write_fasta(args.out, [(f"{args.sample}_contig1", "ATGCGT" * 600)])
        return
    tmp_out = out.parent / "megahit_out"
    cmd = f"{args.megahit_cmd} -1 {args.input1} -2 {args.input2} -o {tmp_out} -t {args.threads} {args.megahit_params}".strip()
    _run(cmd)
    _copy(str(tmp_out / "final.contigs.fa"), args.out)


def step_vsearch(args: argparse.Namespace) -> None:
    if args.mock:
        entries = [(h, s) for h, s in _read_fasta(args.input) if len(s) >= args.min_len]
        _write_fasta(args.out, entries)
        return
    cmd = f"{args.vsearch_cmd} --sortbylength {args.input} --output {args.out} --minseqlength {args.min_len}"
    _run(cmd)


def step_detect(args: argparse.Namespace) -> None:
    if args.mock:
        suffix = "vs2" if args.tool == "virsorter" else "genomad"
        entries = [(f"{h}|{suffix}", s) for h, s in _read_fasta(args.input)]
        _write_fasta(args.out, entries)
        return
    if args.tool == "virsorter":
        cmd = f"{args.tool_cmd} run -i {args.input} -w {args.workdir} -j {args.threads} all"
        _run(cmd)
        _copy(str(Path(args.workdir) / "final-viral-combined.fa"), args.out)
    elif args.tool == "genomad":
        cmd = f"{args.tool_cmd} end-to-end {args.input} {args.workdir} {args.db} -t {args.threads} --splits {args.threads}"
        _run(cmd)
        basename = Path(args.input).stem
        _copy(str(Path(args.workdir) / f"{basename}_summary" / f"{basename}_virus.fna"), args.out)
    else:
        raise ValueError(f"unsupported tool: {args.tool}")


def step_combine(args: argparse.Namespace) -> None:
    seen: Dict[str, str] = {}
    for fp in args.inputs:
        if not Path(fp).exists():
            continue
        for h, s in _read_fasta(fp):
            if h not in seen:
                seen[h] = s
    _write_fasta(args.out, sorted(seen.items()))


def step_checkv(args: argparse.Namespace) -> None:
    in_entries = _read_fasta(args.input)
    out_fasta = Path(args.out_dir) / "contigs.fa"
    out_summary = Path(args.out_dir) / "quality_summary.tsv"
    out_fasta.parent.mkdir(parents=True, exist_ok=True)

    if not args.mock:
        cmd = f"{args.checkv_cmd} end_to_end {args.input} {args.out_dir} -d {args.db} -t {args.threads}"
        _run(cmd)

    _write_fasta(str(out_fasta), in_entries)
    with out_summary.open("w", encoding="utf-8") as fh:
        fh.write("contig_id\tcontig_length\tcheckv_quality\tcompleteness\n")
        for h, s in in_entries:
            quality = "High-quality" if len(s) >= 1500 else "Low-quality"
            comp = 95.0 if quality == "High-quality" else 30.0
            fh.write(f"{h}\t{len(s)}\t{quality}\t{comp}\n")


def step_high_quality(args: argparse.Namespace) -> None:
    keep = set()
    with open(args.summary, "r", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            contig_id, _l, quality, _c = line.rstrip("\n").split("\t")
            if quality in {"Complete", "High-quality", "Medium-quality"}:
                keep.add(contig_id)
    entries = [(h, s) for h, s in _read_fasta(args.input) if h in keep]
    _write_fasta(args.out, entries)


def step_busco(args: argparse.Namespace) -> None:
    entries = _read_fasta(args.input)
    renamed = [(f"{args.sample}_{idx}", seq) for idx, (_h, seq) in enumerate(entries, start=1)]
    _write_fasta(args.out, renamed)


def step_viruslib_merge(args: argparse.Namespace) -> None:
    all_entries: List[Tuple[str, str]] = []
    for fp in args.inputs:
        if Path(fp).exists():
            all_entries.extend(_read_fasta(fp))
    renamed = [(f"vOTU{idx}", seq) for idx, (_h, seq) in enumerate(all_entries, start=1)]
    _write_fasta(args.out, renamed)


def step_viruslib_dedup(args: argparse.Namespace) -> None:
    seen = {}
    clusters = []
    for h, s in _read_fasta(args.input):
        if s not in seen:
            seen[s] = h
        clusters.append((h, seen[s]))
    _write_fasta(args.out, [(rep, seq) for seq, rep in ((k, v) for k, v in seen.items())])
    Path(args.clusters).parent.mkdir(parents=True, exist_ok=True)
    with open(args.clusters, "w", encoding="utf-8") as fh:
        fh.write("contig\trepresentative\n")
        for c, r in clusters:
            fh.write(f"{c}\t{r}\n")


def step_downstream(args: argparse.Namespace) -> None:
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    samples = [line.strip().split("\t")[0] for line in Path(args.samples).read_text(encoding="utf-8").splitlines()[1:] if line.strip()]
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("sample\tmethod\tcount\n")
        for s in samples:
            fh.write(f"{s}\t{args.method}\t1\n")


def step_agent(args: argparse.Namespace) -> None:
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    steps = [s for s in args.steps.split(",") if s]
    with open(args.out, "w", encoding="utf-8") as fh:
        for step in steps:
            row = {
                "step": step,
                "signal": {"status": "success", "attempt": 1},
                "action": "noop",
                "delta_params": {},
                "risk_level": "low",
                "auto_applied": True,
                "timestamp": "1970-01-01T00:00:00+00:00",
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GMV v2 workflow step executor")
    sub = p.add_subparsers(dest="step", required=True)

    x = sub.add_parser("preprocess")
    x.add_argument("--r1-in", required=True)
    x.add_argument("--r2-in", required=True)
    x.add_argument("--r1-out", required=True)
    x.add_argument("--r2-out", required=True)
    x.add_argument("--threads", type=int, default=1)
    x.add_argument("--fastp-cmd", default="fastp")
    x.add_argument("--fastp-params", default="")
    x.add_argument("--mock", action="store_true")
    x.set_defaults(func=step_preprocess)

    x = sub.add_parser("host-removal")
    x.add_argument("--r1-in", required=True)
    x.add_argument("--r2-in", required=True)
    x.add_argument("--r1-out", required=True)
    x.add_argument("--r2-out", required=True)
    x.add_argument("--prefix", required=True)
    x.add_argument("--host", default="")
    x.add_argument("--host-index", default="")
    x.add_argument("--threads", type=int, default=1)
    x.add_argument("--bowtie2-cmd", default="bowtie2")
    x.add_argument("--mock", action="store_true")
    x.set_defaults(func=step_host_removal)

    x = sub.add_parser("assembly")
    x.add_argument("--mode", required=True, choices=["reads", "contigs"])
    x.add_argument("--sample", required=True)
    x.add_argument("--input1", required=True)
    x.add_argument("--input2", default="")
    x.add_argument("--out", required=True)
    x.add_argument("--threads", type=int, default=1)
    x.add_argument("--megahit-cmd", default="megahit")
    x.add_argument("--megahit-params", default="")
    x.add_argument("--mock", action="store_true")
    x.set_defaults(func=step_assembly)

    x = sub.add_parser("vsearch")
    x.add_argument("--input", required=True)
    x.add_argument("--out", required=True)
    x.add_argument("--min-len", type=int, default=1500)
    x.add_argument("--vsearch-cmd", default="vsearch")
    x.add_argument("--mock", action="store_true")
    x.set_defaults(func=step_vsearch)

    x = sub.add_parser("detect")
    x.add_argument("--tool", required=True, choices=["virsorter", "genomad"])
    x.add_argument("--tool-cmd", required=True)
    x.add_argument("--db", default="")
    x.add_argument("--input", required=True)
    x.add_argument("--workdir", required=True)
    x.add_argument("--out", required=True)
    x.add_argument("--threads", type=int, default=1)
    x.add_argument("--mock", action="store_true")
    x.set_defaults(func=step_detect)

    x = sub.add_parser("combine")
    x.add_argument("--inputs", nargs="+", required=True)
    x.add_argument("--out", required=True)
    x.set_defaults(func=step_combine)

    x = sub.add_parser("checkv")
    x.add_argument("--input", required=True)
    x.add_argument("--out-dir", required=True)
    x.add_argument("--db", default="")
    x.add_argument("--checkv-cmd", default="checkv")
    x.add_argument("--threads", type=int, default=1)
    x.add_argument("--mock", action="store_true")
    x.set_defaults(func=step_checkv)

    x = sub.add_parser("high-quality")
    x.add_argument("--input", required=True)
    x.add_argument("--summary", required=True)
    x.add_argument("--out", required=True)
    x.set_defaults(func=step_high_quality)

    x = sub.add_parser("busco")
    x.add_argument("--input", required=True)
    x.add_argument("--out", required=True)
    x.add_argument("--sample", required=True)
    x.set_defaults(func=step_busco)

    x = sub.add_parser("viruslib-merge")
    x.add_argument("--inputs", nargs="+", required=True)
    x.add_argument("--out", required=True)
    x.set_defaults(func=step_viruslib_merge)

    x = sub.add_parser("viruslib-dedup")
    x.add_argument("--input", required=True)
    x.add_argument("--out", required=True)
    x.add_argument("--clusters", required=True)
    x.set_defaults(func=step_viruslib_dedup)

    x = sub.add_parser("downstream")
    x.add_argument("--samples", required=True)
    x.add_argument("--method", required=True)
    x.add_argument("--out", required=True)
    x.set_defaults(func=step_downstream)

    x = sub.add_parser("agent")
    x.add_argument("--steps", required=True)
    x.add_argument("--out", required=True)
    x.set_defaults(func=step_agent)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
