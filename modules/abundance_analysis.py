"""
丰度分析模块

本模块包含使用coverm进行contig和基因丰度分析的功能。
"""

import os
from core.config import get_config_manager
from utils.logging import setup_module_logger
from utils.tools import make_clean_dir
from utils.environment import EnvironmentManager


def run_coverm_contig(**context):
    """使用coverm进行contig丰度分析

    对host_removed后的fastq文件进行contig丰度分析，使用vclust_dedup生成的viruslib_nr.fa作为参考。
    """
    logger = setup_module_logger("abundance_analysis.coverm_contig")
    logger.info("开始执行coverm contig丰度分析")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    r1 = context["input1"]
    r2 = context["input2"]
    viruslib_contig_path = context["viruslib_contig_path"]
    output_dir = context["output"]
    sample = context["sample"]
    threads = context["threads"]

    # 创建输出目录
    coverm_dir = os.path.join(output_dir, "coverm_contig")
    make_clean_dir(coverm_dir)

    try:
        # 构建coverm命令
        output_file = os.path.join(coverm_dir, f"{sample}_coverm.tsv")
        
        coverm_path = config.get("software", "coverm")
        coverm_contig_cmd = config.get("parameters", "coverm_contig_cmd")
        coverm_params = config.get("parameters", "coverm_params")
        
        coverm_cmd = (
            f"{coverm_path} {coverm_contig_cmd} "
            f"-1 {r1} -2 {r2} "
            f"--reference {viruslib_contig_path} "
            f"{coverm_params} "
            f"-t {threads} "
            f"-o {output_file}"
        )

        env_manager.run_command(coverm_cmd, tool_name="main")
        logger.info(f"Contig丰度分析完成: {output_file}")
    except Exception as e:
        logger.error(f"Contig丰度分析失败: {str(e)}")
        raise


def run_coverm_gene(**context):
    """使用coverm进行基因丰度分析

    对host_removed后的fastq文件进行基因丰度分析，使用cdhit_dedup生成的gene_cdhit.fq作为参考。
    """
    logger = setup_module_logger("abundance_analysis.coverm_gene")
    logger.info("开始执行coverm基因丰度分析")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    r1 = context["input1"]
    r2 = context["input2"]
    viruslib_gene_path = context["viruslib_gene_path"]
    output_dir = context["output"]
    sample = context["sample"]
    threads = context["threads"]

    # 创建输出目录
    coverm_dir = os.path.join(output_dir, "coverm_gene")
    make_clean_dir(coverm_dir)

    try:
        # 构建coverm命令
        output_file = os.path.join(coverm_dir, f"{sample}_gene_coverm.tsv")
        
        coverm_path = config.get("software", "coverm")
        coverm_gene_cmd = config.get("parameters", "coverm_gene_cmd")
        coverm_params = config.get("parameters", "coverm_params")
        
        coverm_cmd = (
            f"{coverm_path} {coverm_gene_cmd} "
            f"-1 {r1} -2 {r2} "
            f"--reference {viruslib_gene_path} "
            f"{coverm_params} "
            f"-t {threads} "
            f"-o {output_file}"
        )

        env_manager.run_command(coverm_cmd, tool_name="main")
        logger.info(f"基因丰度分析完成: {output_file}")
    except Exception as e:
        logger.error(f"基因丰度分析失败: {str(e)}")
        raise


def run_abundance_analysis(**context):
    """运行完整的丰度分析

    包括contig和基因丰度分析。
    """
    logger = setup_module_logger("abundance_analysis")
    logger.info("开始执行完整的丰度分析")

    try:
        # 运行contig丰度分析
        run_coverm_contig(**context)

        # 运行基因丰度分析
        run_coverm_gene(**context)

        logger.info("完整丰度分析成功完成")
    except Exception as e:
        logger.error(f"丰度分析失败: {str(e)}")
        raise
