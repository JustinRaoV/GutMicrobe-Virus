"""
病毒检测模块

本模块包含各种病毒识别工具，包括 VirSorter、DeepVirFinder 和 VIBRANT。
"""

import subprocess
import sys
import os
import shutil
from core.config_manager import get_config


def run_virsorter(**context):
    """VirSorter 病毒识别
    
    使用 VirSorter2 进行病毒识别，包括两轮识别和中间的质量评估。
    """
    print("[virsorter] Running VirSorter...")
    
    # 设置路径和参数
    input_fasta = os.path.join(context['paths']["checkv_prefilter"], context['sample'], "filtered_contigs.fa")
    virsorter_dir = os.path.join(context['paths']["virsorter"], context['sample'])
    config = get_config()
    env_config = config['environment']
    
    # 清理并创建目录
    if os.path.exists(virsorter_dir):
        try:
            shutil.rmtree(virsorter_dir)
        except Exception as e:
            print(f"[virsorter] Warning: Failed to remove {virsorter_dir}: {e}")
    os.makedirs(virsorter_dir, exist_ok=True)
    
    try:
        # 执行三个步骤
        _run_virsorter_pass1(config['software']['virsorter'], input_fasta, virsorter_dir, 
                           context['threads'], config['parameters']['virsorter_params'], env_config)
        _run_checkv_in_virsorter(config['software']['checkv'], virsorter_dir, 
                                context['db'], context['threads'])
        _run_virsorter_pass2(config['software']['virsorter'], virsorter_dir, 
                           config['parameters']['virsorter_params'], env_config)
        
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: VirSorter error: {e}")


def _run_virsorter_pass1(virsorter_path, input_fasta, virsorter_dir, threads, virsorter_params, env_config):
    """运行 VirSorter 第一轮"""
    cmd = (
        f"{env_config['virsorter_module_unload']} && "
        f"{env_config['virsorter_conda_activate']} && "
        f"{virsorter_path} run --prep-for-dramv -w {virsorter_dir}/vs2-pass1 "
        f"-i {input_fasta} -j {threads} {virsorter_params} "
        f"--keep-original-seq all")
    print(f"[virsorter] Running pass1: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit(f"ERROR: VirSorter pass1 failed: {ret}")


def _run_checkv_in_virsorter(checkv_path, virsorter_dir, db, threads):
    """在 VirSorter 中运行 CheckV"""
    checkv_dir = os.path.join(virsorter_dir, "checkv")
    
    # 清理并创建目录
    if os.path.exists(checkv_dir):
        try:
            shutil.rmtree(checkv_dir)
        except Exception as e:
            print(f"[virsorter] Warning: Failed to remove {checkv_dir}: {e}")
    os.makedirs(checkv_dir, exist_ok=True)
    
    # 运行 CheckV
    cmd = (
        f"{checkv_path} end_to_end {os.path.join(virsorter_dir, 'vs2-pass1/final-viral-combined.fa')} {checkv_dir} "
        f"-d {os.path.join(db, 'checkvdb/checkv-db-v1.4')} -t {threads}"
    )
    print(f"[virsorter] Running CheckV: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("ERROR: CheckV in VirSorter failed")
    
    # 合并 proviruses.fna 和 viruses.fna
    with open(os.path.join(checkv_dir, "combined.fna"), "w") as out:
        for f in ["proviruses.fna", "viruses.fna"]:
            with open(os.path.join(checkv_dir, f)) as infile:
                out.write(infile.read())


def _run_virsorter_pass2(virsorter_path, virsorter_dir, virsorter_params, env_config):
    """运行 VirSorter 第二轮"""
    cmd = (
        f"{env_config['virsorter_module_unload']} && "
        f"{env_config['virsorter_conda_activate']} && "
        f"{virsorter_path} run -w {virsorter_dir} "
        f"-i {virsorter_dir}/checkv/combined.fna --prep-for-dramv "
        f"{virsorter_params} all"
    )
    print(f"[virsorter] Running pass2: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("ERROR: VirSorter pass2 failed")


def run_dvf(**context):
    """DeepVirFinder 病毒识别
    
    使用 DeepVirFinder 进行病毒序列预测，基于深度学习模型。
    """
    print("[dvf] Running DeepVirFinder...")
    
    config = get_config()
    env = config['environment']
    dvf_module_unload = env.get('dvf_module_unload', '')
    dvf_conda_activate = env.get('dvf_conda_activate', '')
    dvf_path = config['software']['dvf']
    sample = context['sample']
    threads = context['threads']
    paths = context['paths']
    db_root = context['db']
    # 优先用config.ini里的dvf_models，否则用--db拼接默认子路径
    if config.has_section('database') and config['database'].get('dvf_models'):
        dvf_models = config['database']['dvf_models']
    else:
        dvf_models = os.path.join(db_root, "dvf/models")
    
    # 设置输入输出路径
    input_fasta = os.path.join(paths["checkv_prefilter"], sample, "filtered_contigs.fa")
    dvf_dir = os.path.join(paths["dvf"], sample)
    
    # 清理并创建目录
    if os.path.exists(dvf_dir):
        try:
            shutil.rmtree(dvf_dir)
        except Exception as e:
            print(f"[dvf] Warning: Failed to remove {dvf_dir}: {e}")
    os.makedirs(dvf_dir, exist_ok=True)
    
    # 运行 DeepVirFinder
    cmd = f"""
    {dvf_module_unload} &&
    {dvf_conda_activate} &&
    {dvf_path} -i {input_fasta} -o {dvf_dir} -c {threads} \
    -m {dvf_models}
    """
    print(f"[dvf] Running: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit(f"ERROR: DeepVirFinder failed: {ret}")
    
    # 过滤结果：使用配置文件中的阈值
    config = get_config()
    dvf_score_threshold = config['parameters']['dvf_score_threshold']
    dvf_pvalue_threshold = config['parameters']['dvf_pvalue_threshold']
    cmd = f"awk 'NR>1 && $3 > {dvf_score_threshold} && $4 < {dvf_pvalue_threshold} {{print $1}}' {dvf_dir}/*_dvfpred.txt > {dvf_dir}/virus_dvf.list"
    print(f"[dvf] Filtering results...")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        print(f"[dvf] Warning: Filtering failed: {ret}")
    
    # 提取病毒序列
    cmd = f"seqkit grep -f {dvf_dir}/virus_dvf.list {input_fasta} > {dvf_dir}/dvf.fasta"
    print(f"[dvf] Extracting viral sequences...")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        print(f"[dvf] Warning: Sequence extraction failed: {ret}")
    
    print(f"[dvf] DeepVirFinder analysis completed. Results saved to: {dvf_dir}")


def run_vibrant(**context):
    """VIBRANT 病毒识别
    
    使用 VIBRANT 进行病毒序列预测和注释。
    """
    print("[vibrant] Running VIBRANT...")
    
    config = get_config()
    env = config['environment']
    vibrant_module_unload = env.get('vibrant_module_unload', '')
    vibrant_conda_activate = env.get('vibrant_conda_activate', '')
    vibrant_path = config['software']['vibrant']
    db_root = context['db']
    # 优先用config.ini里的vibrant_database和vibrant_files，否则用--db拼接默认子路径
    if config.has_section('database') and config['database'].get('vibrant_database'):
        vibrant_database = config['database']['vibrant_database']
    else:
        vibrant_database = os.path.join(db_root, "vibrant/databases")
    if config.has_section('database') and config['database'].get('vibrant_files'):
        vibrant_files = config['database']['vibrant_files']
    else:
        vibrant_files = os.path.join(db_root, "vibrant/files")
    sample = context['sample']
    threads = context['threads']
    paths = context['paths']
    
    # 设置输入输出路径
    input_fasta = os.path.join(paths["checkv_prefilter"], sample, "filtered_contigs.fa")
    vibrant_dir = os.path.join(paths["vibrant"], sample)
    
    # 清理并创建目录
    if os.path.exists(vibrant_dir):
        try:
            shutil.rmtree(vibrant_dir)
        except Exception as e:
            print(f"[vibrant] Warning: Failed to remove {vibrant_dir}: {e}")
    os.makedirs(vibrant_dir, exist_ok=True)
    
    # 运行 VIBRANT
    cmd = f"""
    {vibrant_module_unload} &&
    {vibrant_conda_activate} &&
    {vibrant_path} -i {input_fasta} -folder {vibrant_dir} -t {threads} \
    -d {vibrant_database} -m {vibrant_files}
    """
    print(f"[vibrant] Running: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit(f"ERROR: VIBRANT failed: {ret}")
    
    print(f"[vibrant] VIBRANT analysis completed. Results saved to: {vibrant_dir}") 