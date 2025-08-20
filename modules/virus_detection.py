"""
病毒检测模块

本模块包含各种病毒识别工具，包括 VirSorter、DeepVirFinder 和 VIBRANT。
"""

import subprocess
import os
from core.config import get_config_manager
from utils.logging import setup_module_logger
from utils.tools import make_clean_dir
from utils.environment import EnvironmentManager


def run_virsorter(**context):
    """VirSorter 病毒识别

    使用 VirSorter2 进行病毒识别，包括两轮识别和中间的质量评估。
    """
    logger = setup_module_logger("virus_detection.virsorter")
    logger.info("开始执行VirSorter病毒识别")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)

    # 设置路径和参数
    input_fasta = os.path.join(
        context["paths"]["checkv_prefilter"], context["sample"], "filtered_contigs.fa"
    )
    virsorter_dir = os.path.join(context["paths"]["virsorter"], context["sample"])

    make_clean_dir(virsorter_dir)

    try:
        # 执行三个步骤
        logger.info("执行VirSorter第一轮识别")
        _run_virsorter_pass1(
            config, env_manager, input_fasta, virsorter_dir, context["threads"]
        )
        
        logger.info("执行CheckV质量评估")
        _run_checkv_in_virsorter(
            config, env_manager, virsorter_dir, context["db"], context["threads"]
        )

        logger.info("执行VirSorter第二轮识别")
        _run_virsorter_pass2(
            config, env_manager, virsorter_dir
        )
        
        logger.info("VirSorter病毒识别完成")
    except Exception as e:
        logger.error(f"VirSorter执行失败: {str(e)}")
        raise


def _run_virsorter_pass1(config, env_manager, input_fasta, virsorter_dir, threads):
    """运行 VirSorter 第一轮"""
    virsorter_path = config.get("software", "virsorter")
    virsorter_params = config.get("parameters", "virsorter_params")
    
    cmd = (
        f"{virsorter_path} run --prep-for-dramv -w {virsorter_dir}/vs2-pass1 "
        f"-i {input_fasta} -j {threads} {virsorter_params} "
        f"--keep-original-seq all"
    )
    
    env_manager.run_command(cmd, tool_name="virsorter")


def _run_checkv_in_virsorter(config, env_manager, virsorter_dir, db_root, threads):
    """在 VirSorter 中运行 CheckV"""
    checkv_path = config.get("software", "checkv")
    checkv_dir = os.path.join(virsorter_dir, "checkv")

    # 清理并创建目录
    make_clean_dir(checkv_dir)

    # 获取CheckV数据库路径
    checkv_db = config.get_database_path("checkv_database", db_root)
    
    # 运行 CheckV
    cmd = (
        f"{checkv_path} end_to_end {os.path.join(virsorter_dir, 'vs2-pass1/final-viral-combined.fa')} {checkv_dir} "
        f"-d {checkv_db} -t {threads}"
    )
    env_manager.run_command(cmd, tool_name="main")

    # 合并 proviruses.fna 和 viruses.fna
    with open(os.path.join(checkv_dir, "combined.fna"), "w") as out:
        for f in ["proviruses.fna", "viruses.fna"]:
            filepath = os.path.join(checkv_dir, f)
            if os.path.exists(filepath):
                with open(filepath) as infile:
                    out.write(infile.read())


def _run_virsorter_pass2(config, env_manager, virsorter_dir):
    """运行 VirSorter 第二轮"""
    virsorter_path = config.get("software", "virsorter")
    virsorter_params = config.get("parameters", "virsorter_params")
    
    cmd = (
        f"{virsorter_path} run -w {virsorter_dir} "
        f"-i {virsorter_dir}/checkv/combined.fna --prep-for-dramv "
        f"{virsorter_params} all"
    )
    
    env_manager.run_command(cmd, tool_name="virsorter")


def run_dvf(**context):
    """DeepVirFinder 病毒识别

    使用 DeepVirFinder 进行病毒序列预测，基于深度学习模型。
    """
    logger = setup_module_logger("virus_detection.dvf")
    logger.info("开始执行DeepVirFinder病毒识别")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    dvf_path = config.get("software", "dvf")
    sample = context["sample"]
    threads = context["threads"]
    paths = context["paths"]
    db_root = context["db"]
    
    # 获取DVF模型路径
    dvf_models = config.get_database_path("dvf_models", db_root)

    # 设置输入输出路径
    input_fasta = os.path.join(paths["checkv_prefilter"], sample, "filtered_contigs.fa")
    dvf_dir = os.path.join(paths["dvf"], sample)

    # 清理并创建目录
    make_clean_dir(dvf_dir)

    try:
        # 构建DeepVirFinder命令
        dvf_cmd = f"{dvf_path} -i {input_fasta} -o {dvf_dir} -c {threads} -m {dvf_models}"
        env_manager.run_command(dvf_cmd, tool_name="dvf")

        # 过滤结果：使用配置文件中的阈值
        dvf_score_threshold = config.get("parameters", "dvf_score_threshold")
        dvf_pvalue_threshold = config.get("parameters", "dvf_pvalue_threshold")
        
        filter_cmd = (
            f"awk 'NR>1 && $3 > {dvf_score_threshold} && $4 < {dvf_pvalue_threshold} "
            f"{{print $1}}' {dvf_dir}/*_dvfpred.txt > {dvf_dir}/virus_dvf.list"
        )
        env_manager.run_command(filter_cmd, tool_name="main")

        # 提取病毒序列
        seqkit_path = config.get("software", "seqkit")
        extract_cmd = f"{seqkit_path} grep -f {dvf_dir}/virus_dvf.list {input_fasta} > {dvf_dir}/dvf.fasta"
        env_manager.run_command(extract_cmd, tool_name="main")

        logger.info(f"DeepVirFinder分析完成，结果保存至: {dvf_dir}")
    except Exception as e:
        logger.error(f"DeepVirFinder执行失败: {str(e)}")
        raise


def run_vibrant(**context):
    """VIBRANT 病毒识别

    使用 VIBRANT 进行病毒序列预测和注释。
    """
    logger = setup_module_logger("virus_detection.vibrant")
    logger.info("开始执行VIBRANT病毒识别")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    vibrant_path = config.get("software", "vibrant")
    db_root = context["db"]
    
    # 获取VIBRANT数据库路径
    vibrant_database = config.get_database_path("vibrant_database", db_root)
    vibrant_files = config.get_database_path("vibrant_files", db_root)
    
    sample = context["sample"]
    threads = context["threads"]
    paths = context["paths"]

    # 设置输入输出路径
    input_fasta = os.path.join(paths["checkv_prefilter"], sample, "filtered_contigs.fa")
    vibrant_dir = os.path.join(paths["vibrant"], sample)

    # 清理并创建目录
    make_clean_dir(vibrant_dir)

    try:
        # 构建VIBRANT命令
        vibrant_cmd = (
            f"{vibrant_path} -i {input_fasta} -folder {vibrant_dir} "
            f"-t {threads} -d {vibrant_database} -m {vibrant_files}"
        )
        env_manager.run_command(vibrant_cmd, tool_name="vibrant")

        logger.info(f"VIBRANT分析完成，结果保存至: {vibrant_dir}")
    except Exception as e:
        logger.error(f"VIBRANT执行失败: {str(e)}")
        raise


def run_blastn(**context):
    """BLASTN 比对
    对过滤后的 contigs 进行 BLASTN 比对，搜索病毒数据库。
    """
    logger = setup_module_logger("virus_detection.blastn")
    logger.info("开始执行BLASTN病毒数据库比对")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    db_root = context["db"]
    blastn_db_root = config.get_database_path("blastn_database", db_root)
    blastn_dir = os.path.join(context["paths"]["blastn"], context["sample"])

    # 清理并创建目录
    make_clean_dir(blastn_dir)

    try:
        # 获取BLASTN数据库列表
        blastn_databases = config.get_constant("blastn_databases")
        
        # 对多个数据库进行比对
        for dbname in blastn_databases:
            out_path = f"{blastn_dir}/{dbname}.out"
            
            blastn_cmd = (
                f'blastn -query {context["paths"]["vsearch"]}/{context["sample"]}/contig.fasta '
                f'-db {blastn_db_root}/{dbname} -num_threads {context["threads"]} -max_target_seqs 1 '
                f'-outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " '
                f"-out {out_path}"
            )

            env_manager.run_command(blastn_cmd, tool_name="main")

        logger.info("BLASTN病毒数据库比对完成")
    except Exception as e:
        logger.error(f"BLASTN执行失败: {str(e)}")
        raise
