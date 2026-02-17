from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ConfigError, load_pipeline_config, load_sample_sheet


def _count_fasta(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith(">"):
                count += 1
    return count


def generate_report(config_path: str, run_id: str | None = None) -> dict[str, Any]:
    cfg = load_pipeline_config(config_path)
    if run_id:
        cfg["execution"]["run_id"] = run_id

    rid = cfg["execution"]["run_id"]
    results_root = Path(cfg["execution"]["results_dir"]) / rid
    reports_root = Path(cfg["execution"]["reports_dir"]) / rid / "manuscript"
    figures_dir = reports_root / "figures"
    tables_dir = reports_root / "tables"
    reports_root.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    sample_sheet = Path(cfg["execution"]["sample_sheet"])
    if not sample_sheet.exists():
        raise ConfigError(f"sample_sheet 不存在，无法生成报告: {sample_sheet}")

    samples = load_sample_sheet(str(sample_sheet))

    rows: list[dict[str, Any]] = []
    for row in samples:
        sample = row["sample"]
        busco_out = Path(cfg["execution"]["work_dir"]) / rid / "upstream" / sample / "10.busco_filter" / "contigs.fa"
        high_out = Path(cfg["execution"]["work_dir"]) / rid / "upstream" / sample / "9.high_quality" / "contigs.fa"
        combine_out = Path(cfg["execution"]["work_dir"]) / rid / "upstream" / sample / "7.combine" / "contigs.fa"
        rows.append(
            {
                "sample": sample,
                "combined_contigs": _count_fasta(combine_out),
                "high_quality_contigs": _count_fasta(high_out),
                "final_contigs": _count_fasta(busco_out),
            }
        )

    summary_table = tables_dir / "sample_summary.tsv"
    with summary_table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["sample", "combined_contigs", "high_quality_contigs", "final_contigs"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)

    total_final = sum(item["final_contigs"] for item in rows)
    viruslib_path = results_root / "viruslib" / "viruslib_nr.fa"
    viruslib_count = _count_fasta(viruslib_path)

    methods_zh = reports_root / "methods_zh.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    methods_zh.write_text(
        "\n".join(
            [
                "# GMV v4 方法学报告（中文）",
                "",
                f"- 生成时间: {now}",
                f"- run_id: {rid}",
                "- 编排引擎: Snakemake",
                "- 环境模型: Offline + Singularity + Local/SLURM profile",
                "- 病毒识别策略: VirSorter2 + geNomad 平衡集成，输出 core/high/loose 层级",
                "",
                "## 流程概述",
                "1. Fastp 读长质控",
                "2. Bowtie2 去宿主",
                "3. Megahit 装配",
                "4. Vsearch 长度过滤",
                "5. VirSorter2 与 geNomad 并行检测",
                "6. CheckV 质量筛选 + 高质量提取",
                "7. 项目级去冗余与全样本定量",
                "",
                "## 关键统计",
                f"- 总样本数: {len(rows)}",
                f"- BUSCO 过滤后 contig 总数: {total_final}",
                f"- 非冗余病毒库序列数: {viruslib_count}",
                "",
                "## 输出位置",
                f"- 样本统计表: {summary_table}",
                f"- 非冗余病毒库: {viruslib_path}",
            ]
        ),
        encoding="utf-8",
    )

    # Keep placeholders so manuscript packaging is deterministic.
    (figures_dir / "README.txt").write_text(
        "Figure placeholders. Replace with publication-grade plots after final run.",
        encoding="utf-8",
    )

    return {
        "run_id": rid,
        "methods": str(methods_zh),
        "table": str(summary_table),
        "viruslib": str(viruslib_path),
        "sample_count": len(rows),
    }
