"""
丰度分析模块

本模块包含使用coverm进行contig和基因丰度分析的功能。
"""

import os
from core.config_manager import get_config
from utils.common import create_simple_logger
from utils.tools import make_clean_dir
import subprocess


def run_coverm_contig(**context):
    """使用coverm进行contig丰度分析

    对host_removed后的fastq文件进行contig丰度分析，使用vclust_dedup生成的viruslib_nr.fa作为参考。
    """
    logger = create_simple_logger("abundance_analysis")
    logger.info("Running coverm contig abundance analysis...")

    config = get_config()
    r1 = context["input1"]
    r2 = context["input2"]
    viruslib_contig_path = context["viruslib_contig_path"]
    output_dir = context["output"]
    sample = context["sample"]
    threads = context["threads"]

    # 创建输出目录
    coverm_dir = os.path.join(output_dir, "coverm_contig")
    make_clean_dir(coverm_dir)

    # 构建coverm命令
    output_file = os.path.join(coverm_dir, f"{sample}_coverm.tsv")
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{config['software']['coverm']} {config['parameters']['coverm_contig_cmd']} "
        f"-1 {r1} -2 {r2} "
        f"--reference {viruslib_contig_path} "
        f"{config['parameters']['coverm_params']} "
        f"-t {threads} "
        f"-o {output_file}"
    )

    subprocess.run(cmd, shell=True, check=True)

    logger.info(f"Contig abundance analysis completed: {output_file}")


def run_coverm_gene(**context):
    """使用coverm进行基因丰度分析

    对host_removed后的fastq文件进行基因丰度分析，使用cdhit_dedup生成的gene_cdhit.fq作为参考。
    """
    logger = create_simple_logger("abundance_analysis")
    logger.info("Running coverm gene abundance analysis...")

    config = get_config()
    r1 = context["input1"]
    r2 = context["input2"]
    viruslib_gene_path = context["viruslib_gene_path"]
    output_dir = context["output"]
    sample = context["sample"]
    threads = context["threads"]

    # 创建输出目录
    coverm_dir = os.path.join(output_dir, "coverm_gene")
    make_clean_dir(coverm_dir)

    # 构建coverm命令
    output_file = os.path.join(coverm_dir, f"{sample}_gene_coverm.tsv")
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{config['software']['coverm']} {config['parameters']['coverm_gene_cmd']} "
        f"-1 {r1} -2 {r2} "
        f"--reference {viruslib_gene_path} "
        f"{config['parameters']['coverm_params']} "
        f"-t {threads} "
        f"-o {output_file}"
    )

    subprocess.run(cmd, shell=True, check=True)

    logger.info(f"Gene abundance analysis completed: {output_file}")


def run_abundance_analysis(**context):
    """运行完整的丰度分析

    包括contig和基因丰度分析。
    """
    logger = create_simple_logger("abundance_analysis")
    logger.info("Running complete abundance analysis...")

    # 运行contig丰度分析
    run_coverm_contig(**context)

    # 运行基因丰度分析
    run_coverm_gene(**context)

    logger.info("Complete abundance analysis finished successfully")
