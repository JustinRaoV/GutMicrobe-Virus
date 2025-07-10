"""
病毒质量评估模块

本模块包含质量评估和最终输出功能。
"""

import subprocess
import sys
import os
import shutil
from utils.tools import filter_checkv
from core.config_manager import get_config


def run_checkv(**context):
    """CheckV 质量评估
    
    对候选病毒序列进行质量评估，计算完整性和污染度。
    """
    print("[checkv] Running checkv...")
    
    config = get_config()
    checkv_dir = os.path.join(context['paths']["checkv"], context['sample'])
    db_root = context['db']
    # 优先用config.ini里的checkv_database，否则用--db拼接默认子路径
    if config.has_section('database') and config['database'].get('checkv_database'):
        checkv_db = config['database']['checkv_database']
    else:
        checkv_db = os.path.join(db_root, "checkvdb/checkv-db-v1.4")
    
    # 清理并创建目录
    if os.path.exists(checkv_dir):
        try:
            subprocess.call([f"rm -rf {checkv_dir}"], shell=True)
        except Exception as e:
            print(f"[checkv] Warning: Failed to remove {checkv_dir}: {e}")
    subprocess.call([f"mkdir -p {checkv_dir}"], shell=True)
    
    # 使用主环境运行CheckV
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"checkv end_to_end {context['paths']['combination']}/{context['sample']}/contigs.fa {checkv_dir} "
        f"-d {checkv_db} -t {context['threads']}"
    )
    print(f"[checkv] Running: {cmd}")
    ret = subprocess.call([cmd], shell=True)
    if ret != 0:
        sys.exit("ERROR: checkv error")


def high_quality_output(**context):
    """高质量病毒输出
    
    根据 CheckV 质量评估结果，输出高质量的病毒序列。
    """
    print("[high_quality] Generating high-quality viral contigs...")
    
    config = get_config()
    checkv_dir = os.path.join(context['paths']["checkv"], context['sample'])
    high_quality_dir = os.path.join(context['paths']["high_quality"], context['sample'])
    
    # 清理并创建目录
    if os.path.exists(high_quality_dir):
        try:
            shutil.rmtree(high_quality_dir)
        except Exception as e:
            print(f"[high_quality] Warning: Failed to remove {high_quality_dir}: {e}")
    os.makedirs(high_quality_dir, exist_ok=True)
    
    # 使用主环境运行过滤
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"python -c \"from utils.tools import filter_checkv; filter_checkv('{context['output']}', '{context['sample']}', {context['paths']})\""
    )
    print(f"[high_quality] Running: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("ERROR: high quality output error")
    
    print(f"[high_quality] High-quality viral contigs saved to: {high_quality_dir}") 