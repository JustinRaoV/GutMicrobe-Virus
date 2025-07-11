"""
病毒质量评估模块

本模块包含质量评估和最终输出功能。
"""

import os
from utils.tools import filter_checkv
from core.config_manager import get_config
from utils.common import create_simple_logger, ensure_directory_clean, run_command


def run_checkv(**context):
    """CheckV 质量评估
    
    对候选病毒序列进行质量评估，计算完整性和污染度。
    """
    logger = create_simple_logger("virus_quality")
    logger.info("Running checkv...")
    
    config = get_config()
    checkv_dir = os.path.join(context['paths']["checkv"], context['sample'])
    db_root = context['db']
    # 优先用config.ini里的checkv_database，否则用--db拼接默认子路径
    if config.has_section('database') and config['database'].get('checkv_database'):
        checkv_db = config['database']['checkv_database']
    else:
        checkv_db = os.path.join(db_root, "checkvdb/checkv-db-v1.4")
    
    # 清理并创建目录
    if not ensure_directory_clean(checkv_dir, logger):
        logger.error(f"Failed to prepare directory: {checkv_dir}")
        return False
    
    # 使用主环境运行CheckV
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"checkv end_to_end {context['paths']['combination']}/{context['sample']}/contigs.fa {checkv_dir} "
        f"-d {checkv_db} -t {context['threads']}"
    )
    
    ret = run_command(cmd, logger, "checkv")
    if ret != 0:
        logger.error("checkv analysis failed")
        return False
    
    logger.info("checkv analysis completed successfully")
    return True


def high_quality_output(**context):
    """高质量病毒输出
    
    根据 CheckV 质量评估结果，输出高质量的病毒序列。
    """
    logger = create_simple_logger("virus_quality")
    logger.info("Generating high-quality viral contigs...")
    
    config = get_config()
    high_quality_dir = os.path.join(context['paths']["high_quality"], context['sample'])
    
    # 清理并创建目录
    if not ensure_directory_clean(high_quality_dir, logger):
        logger.error(f"Failed to prepare directory: {high_quality_dir}")
        return False
    
    # 直接调用filter_checkv函数
    try:
        filter_checkv(context['output'], context['sample'], context['paths'])
        logger.info(f"High-quality viral contigs saved to: {high_quality_dir}")
        return True
    except Exception as e:
        logger.error(f"high quality output failed: {e}")
        return False 