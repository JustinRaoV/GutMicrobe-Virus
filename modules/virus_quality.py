"""
病毒质量评估模块

本模块包含质量评估和最终输出功能。
"""

import os
import subprocess
import pandas as pd
from core.config_manager import get_config
from utils.common import create_simple_logger
from utils.tools import make_clean_dir


def run_checkv(**context):
    """CheckV 质量评估

    对候选病毒序列进行质量评估，计算完整性和污染度。
    """
    logger = create_simple_logger("virus_quality")
    logger.info("Running checkv...")

    config = get_config()
    checkv_dir = os.path.join(context["paths"]["checkv"], context["sample"])
    db_root = context["db"]
    # 优先用config.ini里的checkv_database，否则用--db拼接默认子路径
    if config.has_section("database") and config["database"].get("checkv_database"):
        checkv_db = config["database"]["checkv_database"]
    else:
        checkv_db = os.path.join(db_root, "checkvdb/checkv-db-v1.4")

    # 清理并创建目录
    make_clean_dir(checkv_dir)

    # 使用主环境运行CheckV
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"checkv end_to_end {context['paths']['combination']}/{context['sample']}/contigs.fa {checkv_dir} "
        f"-d {checkv_db} -t {context['threads']}"
    )

    subprocess.run(cmd, shell=True, check=True)
    logger.info("checkv analysis completed successfully")


def high_quality_output(**context):
    """高质量病毒输出

    根据 CheckV 质量评估结果，输出高质量的病毒序列。
    """

    logger = create_simple_logger("virus_quality")
    logger.info("Generating high-quality viral contigs...")

    config = get_config()
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
