"""Generate manuscript-friendly report artifacts."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from gmv.reporting.plots import write_bar_svg


def _read_decisions(decisions_file: Path) -> List[dict]:
    if not decisions_file.exists():
        return []
    rows = []
    with decisions_file.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def generate_report(results_dir: str | Path, reports_dir: str | Path, run_id: str) -> Dict[str, str]:
    results = Path(results_dir)
    reports = Path(reports_dir)

    manuscript_dir = reports / "manuscript"
    fig_dir = manuscript_dir / "figures"
    table_dir = manuscript_dir / "tables"
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    decisions_file = results / run_id / "agent" / "decisions.jsonl"
    decisions = _read_decisions(decisions_file)

    action_counter = Counter(d.get("action", "unknown") for d in decisions)
    risk_counter = Counter(d.get("risk_level", "unknown") for d in decisions)

    action_data: List[Tuple[str, float]] = [(k, float(v)) for k, v in sorted(action_counter.items())]
    risk_data: List[Tuple[str, float]] = [(k, float(v)) for k, v in sorted(risk_counter.items())]

    write_bar_svg(
        fig_dir / "agent_actions.svg",
        title="Agent Action Distribution",
        x_label="Action",
        y_label="Count",
        data=action_data or [("noop", 0.0)],
    )

    write_bar_svg(
        fig_dir / "agent_risk_levels.svg",
        title="Agent Risk-Level Distribution",
        x_label="Risk Level",
        y_label="Count",
        data=risk_data or [("low", 0.0)],
    )

    table_file = table_dir / "agent_decisions.tsv"
    with table_file.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["step", "risk_level", "action", "auto_applied", "timestamp"])
        for d in decisions:
            writer.writerow([
                d.get("step", ""),
                d.get("risk_level", ""),
                d.get("action", ""),
                d.get("auto_applied", ""),
                d.get("timestamp", ""),
            ])

    methods_file = manuscript_dir / "methods_zh.md"
    methods_file.write_text(
        "\n".join(
            [
                "# GutMicrobeVirus v2 方法学说明",
                "",
                "## 流程概述",
                "本流程采用 Snakemake 作为主编排，Singularity 容器作为离线执行单元，支持 SLURM 与本地两种运行模式。",
                "",
                "## Agent 策略",
                "采用分级自治机制：低风险策略自动执行，高风险策略仅建议并记录在决策日志。",
                "",
                "## 输出说明",
                "图表英文标注，正文中文说明。图表位于 `reports/manuscript/figures`，表格位于 `reports/manuscript/tables`。",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "methods": str(methods_file),
        "action_figure": str(fig_dir / "agent_actions.svg"),
        "risk_figure": str(fig_dir / "agent_risk_levels.svg"),
        "table": str(table_file),
    }
