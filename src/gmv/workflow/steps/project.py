"""Project-level (cross-sample) step implementations."""

from __future__ import annotations

import argparse
import csv
import shlex
from pathlib import Path
from typing import Dict, List, Tuple

from gmv.workflow.steps.common import read_fasta, run_shell, write_fasta, write_fasta_filtered


def step_viruslib_merge(args: argparse.Namespace) -> None:
    all_entries: List[Tuple[str, str]] = []
    for fp in args.inputs:
        path = Path(fp)
        if not path.exists():
            continue
        all_entries.extend(read_fasta(str(path)))
    renamed = [(f"vOTU{idx}", seq) for idx, (_header, seq) in enumerate(all_entries, start=1)]
    write_fasta(args.out, renamed)


def step_viruslib_dedup(args: argparse.Namespace) -> None:
    if args.mock:
        representatives: Dict[str, str] = {}
        cluster_map: List[Tuple[str, str]] = []
        for header, seq in read_fasta(args.input):
            if seq not in representatives:
                representatives[seq] = header
            cluster_map.append((header, representatives[seq]))

        write_fasta(args.out, [(rep, seq) for seq, rep in representatives.items()])
        Path(args.clusters).parent.mkdir(parents=True, exist_ok=True)
        with open(args.clusters, "w", encoding="utf-8") as fh:
            fh.write("contig\trepresentative\n")
            for contig, rep in cluster_map:
                fh.write(f"{contig}\t{rep}\n")
        return

    temp_dir = Path(args.workdir or (Path(args.clusters).parent / "_vclust"))
    temp_dir.mkdir(parents=True, exist_ok=True)

    fltr_file = temp_dir / "fltr.txt"
    ani_file = temp_dir / "ani.tsv"
    raw_clusters = temp_dir / "clusters.raw.tsv"
    ids_file = temp_dir / "ani.ids.tsv"

    run_shell(
        f"{args.vclust_cmd} prefilter -i {shlex.quote(args.input)} -o {shlex.quote(str(fltr_file))} "
        f"--min-ident {float(args.min_ident)}"
    )
    run_shell(
        f"{args.vclust_cmd} align -i {shlex.quote(args.input)} -o {shlex.quote(str(ani_file))} "
        f"--filter {shlex.quote(str(fltr_file))}"
    )
    run_shell(
        f"{args.vclust_cmd} cluster -i {shlex.quote(str(ani_file))} -o {shlex.quote(str(raw_clusters))} "
        f"--ids {shlex.quote(str(ids_file))} --algorithm leiden --metric ani "
        f"--ani {float(args.ani)} --qcov {float(args.qcov)}"
    )

    representative_by_cluster: Dict[str, str] = {}
    mapping: List[Tuple[str, str]] = []
    with raw_clusters.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) < 2:
                continue
            if fields[0].lower() in {"id", "contig", "sequence"} and "cluster" in fields[1].lower():
                continue
            contig = fields[0].strip()
            cluster = fields[1].strip()
            if not contig or not cluster:
                continue
            representative_by_cluster.setdefault(cluster, contig)
            mapping.append((contig, representative_by_cluster[cluster]))

    reps = set(representative_by_cluster.values())
    if not reps:
        raise RuntimeError(f"vclust cluster 输出为空: {raw_clusters}")

    Path(args.clusters).parent.mkdir(parents=True, exist_ok=True)
    with open(args.clusters, "w", encoding="utf-8") as fh:
        fh.write("contig\trepresentative\n")
        for contig, rep in mapping:
            fh.write(f"{contig}\t{rep}\n")

    write_fasta_filtered(args.input, args.out, keep_ids=reps)


def step_viruslib_annotate(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "summary.tsv"

    if args.mock:
        summary.write_text("votu\tannotation\n", encoding="utf-8")
        return

    cmd = (
        f"{args.phabox2_cmd} --contigs {shlex.quote(args.input)} --threads {int(args.threads)} "
        f"--out {shlex.quote(str(out_dir))} --database {shlex.quote(args.db)}"
    )
    run_shell(cmd)

    if not summary.exists():
        summary.write_text("votu\tannotation\n", encoding="utf-8")


def step_downstream(args: argparse.Namespace) -> None:
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.mock:
        sample_ids = [
            line.strip().split("\t")[0]
            for line in Path(args.samples).read_text(encoding="utf-8").splitlines()[1:]
            if line.strip()
        ]
        with out_path.open("w", encoding="utf-8") as fh:
            fh.write("sample\tmethod\tcount\n")
            for sample in sample_ids:
                fh.write(f"{sample}\t{args.method}\t1\n")
        return

    if args.method != "coverm":
        raise RuntimeError(f"暂不支持的 downstream method: {args.method}")

    sample_sheet = Path(args.samples).resolve()
    coupled: List[str] = []
    with sample_sheet.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            r1 = (row.get("input1") or "").strip()
            r2 = (row.get("input2") or "").strip()
            if not r1 or not r2:
                continue
            p1 = Path(r1).expanduser()
            p2 = Path(r2).expanduser()
            if not p1.is_absolute():
                p1 = (sample_sheet.parent / p1).resolve()
            if not p2.is_absolute():
                p2 = (sample_sheet.parent / p2).resolve()
            coupled.extend([str(p1), str(p2)])

    if not coupled:
        raise RuntimeError(f"CoverM 需要 paired reads，但样本表未提供 input1/input2: {sample_sheet}")

    coupled_args = " ".join([shlex.quote(x) for x in coupled])
    coverm_params = (args.coverm_params or "").strip()
    cmd = (
        f"{args.coverm_cmd} contig --coupled {coupled_args} "
        f"--reference {shlex.quote(args.viruslib)} -t {int(args.threads)} -m count "
        f"-o {shlex.quote(str(out_path))} {coverm_params}"
    ).strip()
    run_shell(cmd)


def register_project(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("viruslib-merge")
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.set_defaults(func=step_viruslib_merge)

    parser = subparsers.add_parser("viruslib-dedup")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--clusters", required=True)
    parser.add_argument("--workdir", default="")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--vclust-cmd", default="vclust")
    parser.add_argument("--min-ident", type=float, default=0.95)
    parser.add_argument("--ani", type=float, default=0.95)
    parser.add_argument("--qcov", type=float, default=0.85)
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_viruslib_dedup)

    parser = subparsers.add_parser("viruslib-annotate")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--phabox2-cmd", default="phabox2")
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_viruslib_annotate)

    parser = subparsers.add_parser("downstream")
    parser.add_argument("--samples", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--viruslib", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--coverm-cmd", default="coverm")
    parser.add_argument("--coverm-params", default="")
    parser.add_argument("--mock", action="store_true")
    parser.set_defaults(func=step_downstream)
