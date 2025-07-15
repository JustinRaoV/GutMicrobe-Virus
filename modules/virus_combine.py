"""
病毒分析模块

本模块包含序列比对和结果整合功能。
"""

import os
from core.config_manager import get_config
from utils.common import create_simple_logger
from utils.tools import make_clean_dir
import pandas as pd


def run_combination(**context):
    """
    合并病毒识别和比对结果，生成候选病毒序列。
    支持的工具：VirSorter、DeepVirFinder、VIBRANT、BLASTN、CheckV预过滤
    用户可以通过配置选择使用哪些工具的结果。
    """
    logger = create_simple_logger("combination")
    logger.info("[combination] Combining all virus detection results")

    comb_dir = os.path.join(context["paths"]["combination"], context["sample"])
    make_clean_dir(comb_dir)

    # 读取配置
    config = get_config()

    # 获取工具选择配置
    use_blastn = config.getboolean("combination", "use_blastn", fallback=True)
    use_virsorter = config.getboolean("combination", "use_virsorter", fallback=True)
    use_dvf = config.getboolean("combination", "use_dvf", fallback=True)
    use_vibrant = config.getboolean("combination", "use_vibrant", fallback=True)
    use_checkv_prefilter = config.getboolean(
        "combination", "use_checkv_prefilter", fallback=True
    )

    logger.info(
        f"[combination] Tool selection: BLASTN={use_blastn}, VirSorter={use_virsorter}, DeepVirFinder={use_dvf}, VIBRANT={use_vibrant}, CheckV预过滤={use_checkv_prefilter}"
    )

    # 初始化结果容器
    blastn_contigs = []
    virsorter_contigs = []
    dvf_contigs = []
    vibrant_contigs = []
    checkv_viral_contigs = []

    # 1. 处理 BLASTN 结果
    if use_blastn:
        blastn_filtered = pd.DataFrame(
            columns=pd.Index(
                ["qseqid", "sseqid", "pident", "evalue", "qcovs", "database"]
            )
        )
        blastn_dir = os.path.join(context["paths"]["blastn"], context["sample"])
        blastn_files = [
            ("crass.out", "crass"),
            ("gpd.out", "gpd"),
            ("gvd.out", "gvd"),
            ("mgv.out", "mgv"),
            ("ncbi.out", "ncbi"),
        ]
        for fname, dbname in blastn_files:
            fpath = os.path.join(blastn_dir, fname)
            if os.path.exists(fpath) and os.path.getsize(fpath) != 0:
                blastn_filtered = pd.concat(
                    [
                        blastn_filtered,
                        _filter_blastn_file(fpath, dbname, blastn_contigs),
                    ],
                    axis=0,
                )

    # 2. 处理 VirSorter 结果
    if use_virsorter:
        virsorter_dir = os.path.join(context["paths"]["virsorter"], context["sample"])
        virsorter_file = os.path.join(virsorter_dir, "final-viral-score.tsv")
        if os.path.exists(virsorter_file) and os.path.getsize(virsorter_file) != 0:
            dat = pd.read_table(virsorter_file, header=0)
            for contig in dat.iloc[:, 0]:
                key = contig.split("|")[0]
                if key not in virsorter_contigs:
                    virsorter_contigs.append(key)

    # 3. 处理 DeepVirFinder 结果
    if use_dvf:
        dvf_dir = os.path.join(context["paths"]["dvf"], context["sample"])
        dvf_list_file = os.path.join(dvf_dir, "virus_dvf.list")
        if os.path.exists(dvf_list_file):
            with open(dvf_list_file, "r") as f:
                for line in f:
                    contig = line.strip()
                    if contig and contig not in dvf_contigs:
                        dvf_contigs.append(contig)

    # 4. 处理 VIBRANT 结果
    if use_vibrant:
        vibrant_dir = os.path.join(context["paths"]["vibrant"], context["sample"])
        vibrant_file = os.path.join(
            vibrant_dir,
            "VIBRANT_filtered_contigs",
            "VIBRANT_phages_filtered_contigs",
            "filtered_contigs.phages_combined.txt",
        )
        if os.path.exists(vibrant_file):
            with open(vibrant_file, "r") as f:
                for line in f:
                    contig = line.strip().split()[0]
                    if contig and contig not in vibrant_contigs:
                        vibrant_contigs.append(contig)

    # 5. 处理 CheckV 预过滤结果
    if use_checkv_prefilter:
        checkv_prefilter_dir = os.path.join(
            context["paths"]["checkv_prefilter"], context["sample"]
        )
        checkv_viral_file = os.path.join(checkv_prefilter_dir, "viral_contigs.list")
        if os.path.exists(checkv_viral_file):
            with open(checkv_viral_file, "r") as f:
                for line in f:
                    contig = line.strip()
                    if contig and contig not in checkv_viral_contigs:
                        checkv_viral_contigs.append(contig)

    # 合并所有病毒contigs
    all_viral_contigs = set()
    all_viral_contigs.update(blastn_contigs)
    all_viral_contigs.update(virsorter_contigs)
    all_viral_contigs.update(dvf_contigs)
    all_viral_contigs.update(vibrant_contigs)
    all_viral_contigs.update(checkv_viral_contigs)

    logger.info(
        f"[combination] Found viral contigs: BLASTN={len(blastn_contigs)}, VirSorter={len(virsorter_contigs)}, DeepVirFinder={len(dvf_contigs)}, VIBRANT={len(vibrant_contigs)}, CheckV预过滤={len(checkv_viral_contigs)}, 总计={len(all_viral_contigs)}"
    )

    min_tools_hit = int(config["combination"].get("min_tools_hit", 1))
    # 统计每个contig被多少工具命中
    contig_tool_hits = {}
    for contig in all_viral_contigs:
        hits = 0
        if contig in blastn_contigs:
            hits += 1
        if contig in virsorter_contigs:
            hits += 1
        if contig in dvf_contigs:
            hits += 1
        if contig in vibrant_contigs:
            hits += 1
        if contig in checkv_viral_contigs:
            hits += 1
        contig_tool_hits[contig] = hits

    # 只保留命中数大于等于min_tools_hit的contig
    final_contigs = set([c for c, n in contig_tool_hits.items() if n >= min_tools_hit])

    logger.info(
        f"[combination] min_tools_hit={min_tools_hit}, contigs passing filter: {len(final_contigs)}"
    )

    # 生成最终结果
    info = []
    vsearch_dir = os.path.join(context["paths"]["vsearch"], context["sample"])
    with open(f"{vsearch_dir}/contig.fasta") as f:
        line = f.readline()
        if line == "":
            logger.error("[combination] No contigs found in contig.fasta")
            return 1
        f1 = open(f"{comb_dir}/contigs.fa", "w")
        while line:
            contig = line[1:-1]
            out = [
                contig,
                0,
                0,
                0,
                0,
                0,
            ]  # [contig, blastn, virsorter, dvf, vibrant, checkv_viral]
            line = f.readline()
            seq = ""
            while line and line[0] != ">":
                seq += line[:-1]
                line = f.readline()
            if contig in final_contigs:
                f1.write(f">{contig}\n{seq}\n")
                if contig in blastn_contigs:
                    out[1] = 1
                if contig in virsorter_contigs:
                    out[2] = 1
                if contig in dvf_contigs:
                    out[3] = 1
                if contig in vibrant_contigs:
                    out[4] = 1
                if contig in checkv_viral_contigs:
                    out[5] = 1
                info.append(out)
            if not line:
                break
        f1.close()

    # 保存详细信息
    info_df = pd.DataFrame(
        info,
        columns=pd.Index(
            ["contig", "blastn", "virsorter", "dvf", "vibrant", "checkv_viral"]
        ),
    )
    info_df.to_csv(f"{comb_dir}/info.txt", header=True, index=False, sep="\t")

    # 保存 BLASTN 详细信息
    if not blastn_filtered.empty:
        blastn_filtered = blastn_filtered.sort_values(
            by=["qcovs", "pident", "evalue"], ascending=[False, False, True]
        )
        blastn_filtered = blastn_filtered.drop_duplicates(subset=["qseqid"])
        blastn_filtered.to_csv(
            f"{comb_dir}/blastn_info.txt", header=True, index=False, sep="\t"
        )

    # 保存各工具的contig列表
    tool_lists = {
        "blastn_contigs.list": blastn_contigs,
        "virsorter_contigs.list": virsorter_contigs,
        "dvf_contigs.list": dvf_contigs,
        "vibrant_contigs.list": vibrant_contigs,
        "checkv_viral_contigs.list": checkv_viral_contigs,
    }
    for filename, contig_list in tool_lists.items():
        with open(os.path.join(comb_dir, filename), "w") as f:
            for contig in contig_list:
                f.write(f"{contig}\n")
    logger.info(f"[combination] Results saved to: {comb_dir}")
    return 0


def _filter_blastn_file(filepath, dbname, blastn):
    config = get_config()
    pident = float(config["parameters"].get("blastn_pident", 50))
    evalue = float(config["parameters"].get("blastn_evalue", 1e-10))
    qcovs = float(config["parameters"].get("blastn_qcovs", 80))
    df = pd.read_table(filepath, header=None)
    df.columns = [
        "qseqid",
        "sseqid",
        "pident",
        "evalue",
        "qcovs",
        "nident",
        "qlen",
        "slen",
        "length",
        "mismatch",
        "positive",
        "ppos",
        "gapopen",
        "gaps",
        "qstart",
        "qend",
        "sstart",
        "send",
        "bitscore",
        "qcovhsp",
        "qcovus",
        "qseq",
        "sstrand",
        "frames",
    ]
    df = df[
        (df["pident"] >= pident) & (df["evalue"] <= evalue) & (df["qcovs"] >= qcovs)
    ]
    for qseqid in df["qseqid"]:
        if qseqid not in blastn:
            blastn.append(qseqid)
    df = df.iloc[:, :5]
    df["database"] = dbname
    return df
