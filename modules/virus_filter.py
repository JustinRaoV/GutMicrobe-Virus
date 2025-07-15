"""
病毒序列过滤和预处理模块

本模块包含病毒发现流程中的序列过滤和预处理步骤。
"""

import os
import pandas as pd
from core.config_manager import get_config
from utils.common import create_simple_logger, safe_remove_directory
from utils.tools import make_clean_dir
import subprocess
import csv


def run_vsearch(**context):
    """VSEARCH 过滤和排序

    对组装的 contigs 进行长度过滤和排序，移除过短的序列。
    """
    logger = create_simple_logger("virus_filter")
    logger.info("Running VSEARCH filtering and sorting...")

    config = get_config()
    vsearch_path = config["software"]["vsearch"]
    vsearch_params = config["parameters"]["vsearch_params"]

    filter_dir = os.path.join(context["paths"]["vsearch"], context["sample"])
    assembly_dir = os.path.join(context["paths"]["assembly"], context["sample"])

    # 清理并创建目录
    make_clean_dir(filter_dir)

    # 使用主环境运行vsearch
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{vsearch_path} --sortbylength "
        f"{os.path.join(assembly_dir, 'final.contigs.fa')} "
        f"{vsearch_params} --relabel s{context['sample']}.contig "
        f"--output {os.path.join(filter_dir, 'contig.fasta')}"
    )
    logger.info(f"Running vsearch command: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

    # 清理组装目录
    safe_remove_directory(assembly_dir, logger)

    logger.info("VSEARCH filtering completed successfully")


def run_checkv_prefilter(**context):
    """CheckV 预过滤：过滤包含过多宿主基因的 contigs，保存病毒基因计数更高的 contigs

    使用 CheckV 评估 contigs 的病毒性：
    1. 移除包含过多宿主基因的序列（宿主基因 > 10 且宿主基因 > 病毒基因 * 5）
    2. 剩下的全部 contig 保存供下一步使用
    3. 在剩下的 contig 里，病毒基因 > 宿主基因 的 contig 单独保存供后续合并
    """
    logger = create_simple_logger("virus_filter")
    logger.info("Running CheckV pre-filter...")

    config = get_config()
    checkv_path = config["software"]["checkv"]
    db_root = context["db"]
    # 优先用config.ini里的checkv_database，否则用--db拼接默认子路径
    checkv_db = None
    if config.has_section("database") and config["database"].get("checkv_database"):
        checkv_db = config["database"]["checkv_database"]
    else:
        checkv_db = os.path.join(db_root, "checkvdb/checkv-db-v1.4")
    sample = context["sample"]
    threads = context["threads"]
    paths = context["paths"]

    # 设置输入输出路径
    input_fasta = os.path.join(paths["vsearch"], sample, "contig.fasta")
    checkv_dir = os.path.join(paths["checkv_prefilter"], sample)

    # 清理并创建目录
    make_clean_dir(checkv_dir)

    # 使用主环境运行CheckV
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{checkv_path} end_to_end {input_fasta} {checkv_dir} "
        f"-d {checkv_db} -t {threads}"
    )
    logger.info(f"Running checkv command: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

    # 解析结果并过滤
    quality_file = os.path.join(checkv_dir, "quality_summary.tsv")

    # 读取 CheckV 结果
    df = pd.read_table(quality_file, header=0)

    # 定义过滤和保存的 contigs
    contigs_to_remove = []
    viral_contigs = []

    for _, row in df.iterrows():
        contig = row.get("contig_id", 0)
        viral_genes = row.get("viral_genes", 0) or 0
        host_genes = row.get("host_genes", 0) or 0

        # 过滤条件：宿主基因 > 10 且宿主基因 > 病毒基因 * 5
        if host_genes > 10 and host_genes > viral_genes * 5:
            contigs_to_remove.append(contig)
        # 保存条件：病毒基因 > 宿主基因
        elif viral_genes > host_genes:
            viral_contigs.append(contig)

    logger.info(
        f"Contigs to remove (host genes > viral genes * 5): {len(contigs_to_remove)}"
    )
    logger.info(
        f"Viral contigs to keep (viral genes > host genes): {len(viral_contigs)}"
    )

    # 合并所有要保留的 contigs（剩下的全部保存）
    all_keep_contigs = [
        row["contig_id"]
        for _, row in df.iterrows()
        if row["contig_id"] not in contigs_to_remove
    ]
    logger.info(f"Total contigs to keep: {len(all_keep_contigs)}")

    # 保存 all_keep_contigs.list
    all_keep_list = os.path.join(checkv_dir, "all_keep_contigs.list")
    with open(all_keep_list, "w") as f:
        for contig in all_keep_contigs:
            f.write(f"{contig}\n")

    # 提取 all_keep_contigs 的序列
    all_keep_fasta = os.path.join(checkv_dir, "filtered_contigs.fa")
    seqkit_path = config["software"]["seqkit"]
    cmd = f"{seqkit_path} grep -f {all_keep_list} " f"{input_fasta} -o {all_keep_fasta}"
    subprocess.run(cmd, shell=True, check=True)

    # 保存病毒 contigs 列表（单独保存供后续合并）
    viral_list = os.path.join(checkv_dir, "viral_contigs.list")
    with open(viral_list, "w") as f:
        for contig in viral_contigs:
            f.write(f"{contig}\n")

    # 提取病毒 contigs 的序列
    viral_fasta = os.path.join(checkv_dir, "viral_contigs.fa")
    cmd = f"{seqkit_path} grep -f {viral_list} " f"{input_fasta} -o {viral_fasta}"

    subprocess.run(cmd, shell=True, check=True)

    logger.info(f"All keep contigs saved to: {all_keep_fasta}")
    logger.info(f"Viral contigs saved to: {viral_fasta}")
    logger.info("CheckV pre-filter completed successfully")


def run_busco_filter(**context):
    """BUSCO 过滤细菌污染"""
    logger = create_simple_logger("virus_filter")
    logger.info("[busco_filter] Running BUSCO filter...")
    sample = context["sample"]
    db_root = context["db"]
    threads = context["threads"]
    paths = context["paths"]

    abs_busco_dir = os.path.join(paths["busco_filter"], sample)  # 绝对路径
    busco_dir = os.path.relpath(abs_busco_dir, start=os.getcwd())  # 相对路径用于 BUSCO
    input_fasta = os.path.join(paths["high_quality"], sample, "contigs.fa")

    # 清理并创建目录（用绝对路径）
    make_clean_dir(abs_busco_dir)

    # Step 1: 使用BUSCO（用相对路径）
    config = get_config()
    env = config["environment"]
    busco_module_unload = env.get("busco_module_unload", "")
    busco_conda_activate = env.get("busco_conda_activate", "")
    # 优先用config.ini里的busco_database，否则用--db拼接默认子路径
    if config.has_section("database") and config["database"].get("busco_database"):
        busco_db = config["database"]["busco_database"]
    else:
        busco_db = os.path.join(db_root, "bacteria_odb12")
    cmd = (
        f"{busco_module_unload} && "
        f"{busco_conda_activate} && "
        f"busco -f -i {input_fasta} -c {threads} -o {busco_dir} -m geno -l {busco_db} --offline"
    )
    logger.info(f"[busco_filter] Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

    # Step 2: 解析基因预测结果统计总基因数（用绝对路径）
    predicted_file = os.path.join(
        abs_busco_dir, r"prodigal_output/predicted_genes/predicted.fna"
    )
    # Count genes per contig
    predicted_counts = {}
    with open(predicted_file, "r") as pf:
        for line in pf:
            if line.startswith(">"):
                header = line[1:].split()[0]
                contig = "_".join(
                    header.split("_")[:-1]
                )  # contig = part before first underscore
                predicted_counts[contig] = predicted_counts.get(contig, 0) + 1
    if not predicted_counts:
        logger.error("No predicted genes found in predicted.fna.")
        raise RuntimeError("No predicted genes found in predicted.fna.")
    logger.info(f"Total contigs with predicted genes: {len(predicted_counts)}")
    total_genes = sum(predicted_counts.values())
    logger.info(f"Total predicted genes: {total_genes}")

    full_table = os.path.join(abs_busco_dir, r"run_bacteria_odb12/full_table.tsv")
    busco_counts = {}
    with open(full_table, "r") as ft:
        reader = csv.reader(ft, delimiter="\t")
        headers = next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            status = row[1].strip()
            if status in ("Complete", "Fragmented"):
                seq_field = row[2]
                # If sequence field includes "file:contig:start-end", extract contig
                if ":" in seq_field:
                    parts = seq_field.split(":")
                    contig_name = parts[-2] if len(parts) >= 2 else parts[0]
                else:
                    contig_name = seq_field
                contig_name = contig_name.split()[0]
                busco_counts[contig_name] = busco_counts.get(contig_name, 0) + 1

    total_busco_hits = sum(busco_counts.values()) if busco_counts else 0
    logger.info(f"Total BUSCO genes (Complete/Frag): {total_busco_hits}")
    logger.info(f"Contigs with BUSCO hits: {len(busco_counts)}")

    contigs_to_remove = []
    for contig, gene_count in predicted_counts.items():
        if gene_count == 0:
            continue
        busco_genes = busco_counts.get(contig, 0)
        ratio = busco_genes / gene_count
        logger.info(
            f"Contig {contig}: {busco_genes}/{gene_count} BUSCO genes (ratio {ratio:.2%})"
        )
        config = get_config()
        filter_threshold = float(config["parameters"]["filter_ratio_threshold"])
        if ratio > filter_threshold:
            contigs_to_remove.append(contig)

    if contigs_to_remove:
        logger.info(
            f"Removing {len(contigs_to_remove)} contigs with BUSCO ratio > {filter_threshold*100:.0f}%: {contigs_to_remove}"
        )
    else:
        logger.info(
            f"No contigs exceed BUSCO ratio threshold ({filter_threshold*100:.0f}%)."
        )

    input_fasta = os.path.join(paths["high_quality"], sample, "contigs.fa")
    output_fasta = os.path.join(abs_busco_dir, "filtered_contigs.fa")

    # Read input FASTA sequences
    contig_seqs = {}
    with open(input_fasta, "r") as f:
        header = None
        seq_lines = []
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if header:
                    contig_seqs[header] = "".join(seq_lines)
                header = line[1:].split()[0]
                seq_lines = []
            else:
                seq_lines.append(line)
        if header:
            contig_seqs[header] = "".join(seq_lines)

    # Write filtered sequences
    with open(output_fasta, "w") as out:
        for hdr, seq in contig_seqs.items():
            if hdr not in contigs_to_remove:
                out.write(f">{hdr}\n{seq}\n")
    logger.info(f"Filtered contigs saved to: {output_fasta}")
