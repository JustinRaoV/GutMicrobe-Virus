"""
病毒质量评估模块

本模块包含质量评估和最终输出功能。
"""

import os
import subprocess
import pandas as pd
from core.config import get_config_manager
from utils.logging import setup_module_logger
from utils.tools import make_clean_dir
from utils.environment import EnvironmentManager


def run_checkv(**context):
    """CheckV 质量评估

    对候选病毒序列进行质量评估，计算完整性和污染度。
    """
    logger = setup_module_logger("virus_quality.checkv")
    logger.info("开始执行CheckV质量评估")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    checkv_dir = os.path.join(context["paths"]["checkv"], context["sample"])
    db_root = context["db"]
    # 获取CheckV数据库路径
    checkv_db = config.get_database_path("checkv_database", db_root)

    # 清理并创建目录
    make_clean_dir(checkv_dir)

    try:
        # 构建CheckV命令
        checkv_path = config.get("software", "checkv")
        combination_path = f"{context['paths']['combination']}/{context['sample']}/contigs.fa"
        
        checkv_cmd = (
            f"{checkv_path} end_to_end {combination_path} {checkv_dir} "
            f"-d {checkv_db} -t {context['threads']}"
        )

        env_manager.run_command(checkv_cmd, tool_name="main")
        logger.info("CheckV质量评估完成")
    except Exception as e:
        logger.error(f"CheckV质量评估失败: {str(e)}")
        raise


def high_quality_output(**context):
    """高质量病毒输出

    根据 CheckV 质量评估结果，输出高质量的病毒序列。
    """
    logger = setup_module_logger("virus_quality.high_quality")
    logger.info("开始生成高质量病毒contigs")

    config = get_config_manager()
    high_quality_dir = os.path.join(context["paths"]["high_quality"], context["sample"])
    make_clean_dir(high_quality_dir)

    sample = context["sample"]
    paths = context["paths"]
    checkv_dir = os.path.join(paths["checkv"], sample)
    dat = pd.read_table(f"{checkv_dir}/quality_summary.tsv", header=0)
    checkv = dat[
        dat["checkv_quality"].isin(["Complete", "High-quality", "Medium-quality"])
    ]["contig_id"].tolist()
    final_dir = os.path.join(paths["combination"], sample)
    highq_dir = os.path.join(paths["high_quality"], sample)
    with open(f"{final_dir}/contigs.fa") as f, open(
        f"{highq_dir}/contigs.fa", "w"
    ) as f1:
        while True:
            line = f.readline()
            if not line:
                break
            contig = line[1:-1]
            seq = f.readline()[:-1]
            if contig in checkv:
                f1.write(f">{contig}\n{seq}\n")
    logger.info(f"High-quality viral contigs saved to: {high_quality_dir}")
    return True
