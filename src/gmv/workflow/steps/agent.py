from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .common import ensure_parent, read_fasta


def _count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(read_fasta(path))


def _read_sample_sheet(path: str) -> list[dict[str, str]]:
    sample_path = Path(path).expanduser().resolve()
    with sample_path.open("r", encoding="utf-8") as handle:
        head = handle.readline()
    delimiter = "\t" if "\t" in head else ","
    with sample_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return [dict(row) for row in reader]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _agent_decision_log(args: argparse.Namespace) -> int:
    out_jsonl = ensure_parent(args.out_jsonl)
    out_report = ensure_parent(args.out_report)

    sample_rows = _read_sample_sheet(args.sample_sheet)
    work_root = Path(args.work_root).expanduser().resolve()

    entries: list[dict[str, object]] = []
    sample_summaries: list[dict[str, object]] = []

    for row in sample_rows:
        sample = (row.get("sample") or "sample").strip()
        sample_root = work_root / "upstream" / sample

        combined = _count(sample_root / "7.combine" / "contigs.fa")
        high = _count(sample_root / "9.high_quality" / "contigs.fa")
        final = _count(sample_root / "10.busco_filter" / "contigs.fa")

        if final == 0:
            signal = "empty_final_contigs"
            action = "retry_recommended"
            risk_level = "low"
            auto = True
        elif final < 5:
            signal = "low_yield"
            action = "suggest_relax_threshold"
            risk_level = "high"
            auto = False
        else:
            signal = "healthy"
            action = "keep_params"
            risk_level = "low"
            auto = True

        entry = {
            "step": f"sample:{sample}",
            "signal": signal,
            "action": action,
            "delta_params": {},
            "risk_level": risk_level,
            "auto_applied": auto,
            "timestamp": _now_iso(),
            "stats": {
                "combined": combined,
                "high_quality": high,
                "final": final,
            },
        }
        entries.append(entry)
        sample_summaries.append({"sample": sample, "combined": combined, "high": high, "final": final, "signal": signal})

    with out_jsonl.open("w", encoding="utf-8") as handle:
        for item in entries:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    total_samples = len(sample_summaries)
    low_yield = sum(1 for item in sample_summaries if item["signal"] == "low_yield")
    out_report.write_text(
        "\n".join(
            [
                "# GMV Agent 决策摘要",
                "",
                f"- run_id: {args.run_id}",
                f"- 样本数: {total_samples}",
                f"- 低产出样本: {low_yield}",
                "",
                "## 样本统计",
                "| sample | combined | high | final | signal |",
                "|---|---:|---:|---:|---|",
                *[
                    f"| {item['sample']} | {item['combined']} | {item['high']} | {item['final']} | {item['signal']} |"
                    for item in sample_summaries
                ],
            ]
        ),
        encoding="utf-8",
    )

    return 0


def register_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    agent = subparsers.add_parser("agent_decision_log")
    agent.add_argument("--run-id", required=True)
    agent.add_argument("--sample-sheet", required=True)
    agent.add_argument("--work-root", required=True)
    agent.add_argument("--results-root", required=True)
    agent.add_argument("--out-jsonl", required=True)
    agent.add_argument("--out-report", required=True)
    agent.set_defaults(func=_agent_decision_log)
