"""
病毒序列过滤和预处理模块

本模块包含病毒发现流程中的序列过滤和预处理步骤。
"""

import os
import pandas as pd
import subprocess
import csv
from core.config import get_config_manager
from utils.logging import setup_module_logger
from utils.tools import make_clean_dir
from utils.environment import EnvironmentManager
from utils.common import safe_remove_directory


def run_vsearch(**context):
    """VSEARCH 过滤和排序

    对组装的 contigs 进行长度过滤和排序，移除过短的序列。
    """
    logger = setup_module_logger("virus_filter.vsearch")
    logger.info("开始执行VSEARCH序列过滤和排序")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    vsearch_path = config.get("software", "vsearch")
    vsearch_params = config.get("parameters", "vsearch_params")

    filter_dir = os.path.join(context["paths"]["vsearch"], context["sample"])
    assembly_dir = os.path.join(context["paths"]["assembly"], context["sample"])

    # 清理并创建目录
    make_clean_dir(filter_dir)

    try:
        # 构建vsearch命令
        vsearch_cmd = (
            f"{vsearch_path} --sortbylength "
            f"{os.path.join(assembly_dir, 'final.contigs.fa')} "
            f"{vsearch_params} --relabel s{context['sample']}.contig "
            f"--output {os.path.join(filter_dir, 'contig.fasta')}"
        )
        
        env_manager.run_command(vsearch_cmd, tool_name="main")

        # 清理组装目录
        safe_remove_directory(assembly_dir, logger)

        logger.info("VSEARCH序列过滤和排序完成")
    except Exception as e:
        logger.error(f"VSEARCH执行失败: {str(e)}")
        raise


def run_checkv_prefilter(**context):
    """CheckV 预过滤：过滤包含过多宿主基因的 contigs，保存病毒基因计数更高的 contigs

    使用 CheckV 评估 contigs 的病毒性：
    1. 移除包含过多宿主基因的序列（宿主基因 > 阈值 且宿主基因 > 病毒基因 * 比例）
    2. 剩下的全部 contig 保存供下一步使用
    3. 在剩下的 contig 里，病毒基因 > 宿主基因 的 contig 单独保存供后续合并
    """
    logger = setup_module_logger("virus_filter.checkv_prefilter")
    logger.info("开始执行CheckV预过滤")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    checkv_path = config.get("software", "checkv")
    seqkit_path = config.get("software", "seqkit")
    db_root = context["db"]
    sample = context["sample"]
    threads = context["threads"]
    paths = context["paths"]
    
    # 获取CheckV数据库路径
    checkv_db = config.get_database_path("checkv_database", db_root)

    # 设置输入输出路径
    input_fasta = os.path.join(paths["vsearch"], sample, "contig.fasta")
    checkv_dir = os.path.join(paths["checkv_prefilter"], sample)

    # 清理并创建目录
    make_clean_dir(checkv_dir)

    try:
        # 构建CheckV命令
        checkv_cmd = f"{checkv_path} end_to_end {input_fasta} {checkv_dir} -d {checkv_db} -t {threads}"
        env_manager.run_command(checkv_cmd, tool_name="main")

        # 解析结果并过滤
        quality_file = os.path.join(checkv_dir, "quality_summary.tsv")

        # 读取 CheckV 结果
        df = pd.read_table(quality_file, header=0)

        # 获取过滤阈值
        host_gene_threshold = config.get_int("constants", "checkv_host_gene_threshold")
        host_viral_ratio = config.get_int("constants", "checkv_host_viral_ratio")

        # 定义过滤和保存的 contigs
        contigs_to_remove = []
        viral_contigs = []

        for _, row in df.iterrows():
            contig = row.get("contig_id", 0)
            viral_genes = row.get("viral_genes", 0) or 0
            host_genes = row.get("host_genes", 0) or 0

            # 过滤条件：宿主基因 > 阈值 且宿主基因 > 病毒基因 * 比例
            if host_genes > host_gene_threshold and host_genes > viral_genes * host_viral_ratio:
                contigs_to_remove.append(contig)
            # 保存条件：病毒基因 > 宿主基因
            elif viral_genes > host_genes:
                viral_contigs.append(contig)

        logger.info(f"待移除contigs (宿主基因过多): {len(contigs_to_remove)}")
        logger.info(f"病毒contigs (病毒基因>宿主基因): {len(viral_contigs)}")

        # 合并所有要保留的 contigs（剩下的全部保存）
        all_keep_contigs = [
            row["contig_id"]
            for _, row in df.iterrows()
            if row["contig_id"] not in contigs_to_remove
        ]
        logger.info(f"总共保留contigs: {len(all_keep_contigs)}")

        # 保存 all_keep_contigs.list
        all_keep_list = os.path.join(checkv_dir, "all_keep_contigs.list")
        with open(all_keep_list, "w") as f:
            for contig in all_keep_contigs:
                f.write(f"{contig}\n")

        # 提取 all_keep_contigs 的序列
        all_keep_fasta = os.path.join(checkv_dir, "filtered_contigs.fa")
        extract_cmd = f"{seqkit_path} grep -f {all_keep_list} {input_fasta} -o {all_keep_fasta}"
        env_manager.run_command(extract_cmd, tool_name="main")

        # 保存病毒 contigs 列表（单独保存供后续合并）
        viral_list = os.path.join(checkv_dir, "viral_contigs.list")
        with open(viral_list, "w") as f:
            for contig in viral_contigs:
                f.write(f"{contig}\n")

        # 提取病毒 contigs 的序列
        viral_fasta = os.path.join(checkv_dir, "viral_contigs.fa")
        viral_extract_cmd = f"{seqkit_path} grep -f {viral_list} {input_fasta} -o {viral_fasta}"
        env_manager.run_command(viral_extract_cmd, tool_name="main")

        logger.info(f"所有保留contigs保存至: {all_keep_fasta}")
        logger.info(f"病毒contigs保存至: {viral_fasta}")
        logger.info("CheckV预过滤完成")
    except Exception as e:
        logger.error(f"CheckV预过滤执行失败: {str(e)}")
        raise


def run_busco_filter(**context):
    """BUSCO 过滤细菌污染"""
    logger = setup_module_logger("virus_filter.busco_filter")
    logger.info("开始执行BUSCO细菌污染过滤")
    
    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    sample = context["sample"]
    db_root = context["db"]
    threads = context["threads"]
    paths = context["paths"]

    abs_busco_dir = os.path.join(paths["busco_filter"], sample)  # 绝对路径
    busco_dir = os.path.relpath(abs_busco_dir, start=os.getcwd())  # 相对路径用于 BUSCO
    input_fasta = os.path.join(paths["high_quality"], sample, "contigs.fa")

    # 清理并创建目录（用绝对路径）
    make_clean_dir(abs_busco_dir)

    try:
        # Step 1: 使用BUSCO（用相对路径）
        busco_db = config.get_database_path("busco_database", db_root)
        
        busco_cmd = f"busco -f -i {input_fasta} -c {threads} -o {busco_dir} -m geno -l {busco_db} --offline"
        env_manager.run_command(busco_cmd, tool_name="busco")

        # Step 2: 解析基因预测结果统计总基因数（用绝对路径）
        predicted_file = os.path.join(abs_busco_dir, "prodigal_output/predicted_genes/predicted.fna")
        
        # Count genes per contig
        predicted_counts = {}
        with open(predicted_file, "r") as pf:
            for line in pf:
                if line.startswith(">"):
                    header = line[1:].split()[0]
                    contig = "_".join(header.split("_")[:-1])  # contig = part before first underscore
                    predicted_counts[contig] = predicted_counts.get(contig, 0) + 1
        
        if not predicted_counts:
            logger.error("预测基因文件中未找到基因")
            raise RuntimeError("预测基因文件中未找到基因")
        
        logger.info(f"含有预测基因的contigs总数: {len(predicted_counts)}")
        total_genes = sum(predicted_counts.values())
        logger.info(f"预测基因总数: {total_genes}")

        # 获取BUSCO运行目录和表格文件名
        busco_run_dir = config.get_constant("busco_run_dir")
        busco_table_file = config.get_constant("busco_table_file")
        full_table = os.path.join(abs_busco_dir, busco_run_dir, busco_table_file)
        
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
        logger.info(f"BUSCO基因总数 (Complete/Frag): {total_busco_hits}")
        logger.info(f"含有BUSCO基因的contigs: {len(busco_counts)}")

        # 获取过滤阈值
        filter_threshold = config.get_float("parameters", "filter_ratio_threshold")
        
        contigs_to_remove = []
        for contig, gene_count in predicted_counts.items():
            if gene_count == 0:
                continue
            busco_genes = busco_counts.get(contig, 0)
            ratio = busco_genes / gene_count
            logger.info(f"Contig {contig}: {busco_genes}/{gene_count} BUSCO基因 (比例 {ratio:.2%})")
            
            if ratio > filter_threshold:
                contigs_to_remove.append(contig)

        if contigs_to_remove:
            logger.info(f"移除 {len(contigs_to_remove)} 个BUSCO比例 > {filter_threshold*100:.0f}% 的contigs")
        else:
            logger.info(f"没有contigs超过BUSCO比例阈值 ({filter_threshold*100:.0f}%)")

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
        
        logger.info(f"过滤后的contigs保存至: {output_fasta}")
        logger.info("BUSCO细菌污染过滤完成")
    except Exception as e:
        logger.error(f"BUSCO过滤执行失败: {str(e)}")
        raise
