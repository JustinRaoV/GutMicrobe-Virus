"""
病毒序列过滤和预处理模块

本模块包含病毒发现流程中的序列过滤和预处理步骤。
"""

import subprocess
import sys
import os
import shutil
import pandas as pd
from core.config_manager import get_config


def run_vsearch(**context):
    """VSEARCH 过滤和排序
    
    对组装的 contigs 进行长度过滤和排序，移除过短的序列。
    """
    config = get_config()
    vsearch_path = config['software']['vsearch']
    vsearch_params = config['parameters']['vsearch_params']
    
    filter_dir = os.path.join(context['paths']["vsearch"], context['sample'])
    assembly_dir = os.path.join(context['paths']["assembly"], context['sample'])
    
    # 清理并创建目录
    if os.path.exists(filter_dir):
        try:
            shutil.rmtree(filter_dir)
        except Exception as e:
            print(f"[vsearch] Warning: Failed to remove {filter_dir}: {e}")
    os.makedirs(filter_dir, exist_ok=True)
    
    try:
        # 使用主环境运行vsearch
        cmd = (
            f"{config['environment']['main_conda_activate']} && "
            f"{vsearch_path} --sortbylength "
            f"{os.path.join(assembly_dir, 'final.contigs.fa')} "
            f"{vsearch_params} --relabel s{context['sample']}.contig "
            f"--output {os.path.join(filter_dir, 'contig_1k.fasta')}"
        )
        print(f"[vsearch] Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
        
        # 清理组装目录
        try:
            shutil.rmtree(assembly_dir)
        except Exception as e:
            print(f"[vsearch] Warning: Failed to remove {assembly_dir}: {e}")
            
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: VSearch failed: {e}")


def run_checkv_prefilter(**context):
    """CheckV 预过滤：过滤包含过多宿主基因的 contigs，保存病毒基因计数更高的 contigs
    
    使用 CheckV 评估 contigs 的病毒性：
    1. 移除包含过多宿主基因的序列（宿主基因 > 10 且宿主基因 > 病毒基因 * 5）
    2. 剩下的全部 contig 保存供下一步使用
    3. 在剩下的 contig 里，病毒基因 > 宿主基因 的 contig 单独保存供后续合并
    """
    print("[checkv_prefilter] Running CheckV pre-filter...")
    
    config = get_config()
    checkv_path = config['software']['checkv']
    db_root = context['db']
    # 优先用config.ini里的checkv_database，否则用--db拼接默认子路径
    checkv_db = None
    if config.has_section('database') and config['database'].get('checkv_database'):
        checkv_db = config['database']['checkv_database']
    else:
        checkv_db = os.path.join(db_root, "checkvdb/checkv-db-v1.4")
    sample = context['sample']
    threads = context['threads']
    paths = context['paths']
    
    # 设置输入输出路径
    input_fasta = os.path.join(paths["vsearch"], sample, "contig_1k.fasta")
    checkv_dir = os.path.join(paths["checkv_prefilter"], sample)
    
    # 清理并创建目录
    if os.path.exists(checkv_dir):
        try:
            shutil.rmtree(checkv_dir)
        except Exception as e:
            print(f"[checkv_prefilter] Warning: Failed to remove {checkv_dir}: {e}")
    os.makedirs(checkv_dir, exist_ok=True)
    
    # 使用主环境运行CheckV
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{checkv_path} end_to_end {input_fasta} {checkv_dir} "
        f"-d {checkv_db} -t {threads}"
    )
    print(f"[checkv_prefilter] Running: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
       sys.exit("ERROR: CheckV pre-filter failed")
    
    # 解析结果并过滤
    quality_file = os.path.join(checkv_dir, "quality_summary.tsv")
    if not os.path.exists(quality_file):
        sys.exit("ERROR: CheckV quality summary file not found")
    
    # 读取 CheckV 结果
    df = pd.read_table(quality_file, header=0)
    
    # 定义过滤和保存的 contigs
    contigs_to_remove = []
    viral_contigs = []
    
    for index, row in df.iterrows():
        contig = row.get('contig_id', 0)
        viral_genes = row.get('viral_genes', 0) or 0
        host_genes = row.get('host_genes', 0) or 0
        
        # 过滤条件：宿主基因 > 10 且宿主基因 > 病毒基因 * 5
        if host_genes > 10 and host_genes > viral_genes * 5:
            contigs_to_remove.append(contig)
        # 保存条件：病毒基因 > 宿主基因
        elif viral_genes > host_genes:
            viral_contigs.append(contig)
    
    print(f"[checkv_prefilter] Contigs to remove (host genes > viral genes * 5): {len(contigs_to_remove)}")
    print(f"[checkv_prefilter] Viral contigs to keep (viral genes > host genes): {len(viral_contigs)}")
    
    # 合并所有要保留的 contigs（剩下的全部保存）
    all_keep_contigs = [row['contig_id'] for _, row in df.iterrows() if row['contig_id'] not in contigs_to_remove]
    print(f"[checkv_prefilter] Total contigs to keep: {len(all_keep_contigs)}")
    
    # 保存 all_keep_contigs.list
    all_keep_list = os.path.join(checkv_dir, "all_keep_contigs.list")
    with open(all_keep_list, "w") as f:
        for contig in all_keep_contigs:
            f.write(f"{contig}\n")
    
    # 提取 all_keep_contigs 的序列
    all_keep_fasta = os.path.join(checkv_dir, "filtered_contigs.fa")
    seqkit_path = config['software']['seqkit']
    cmd = (
        f"{seqkit_path} grep -f {all_keep_list} "
        f"{input_fasta} -o {all_keep_fasta}"
    )
    print(f"[checkv_prefilter] Extracting all_keep_contigs with seqkit: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("ERROR: Failed to extract all_keep_contigs with seqkit")
    
    # 保存病毒 contigs 列表（单独保存供后续合并）
    viral_list = os.path.join(checkv_dir, "viral_contigs.list")
    with open(viral_list, "w") as f:
        for contig in viral_contigs:
            f.write(f"{contig}\n")
    
    # 提取病毒 contigs 的序列
    viral_fasta = os.path.join(checkv_dir, "viral_contigs.fa")
    cmd = (
        f"{seqkit_path} grep -f {viral_list} "
        f"{input_fasta} -o {viral_fasta}"
    )
    print(f"[checkv_prefilter] Extracting viral_contigs with seqkit: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("ERROR: Failed to extract viral_contigs with seqkit")
    
    print(f"[checkv_prefilter] All keep contigs saved to: {all_keep_fasta}")
    print(f"[checkv_prefilter] Viral contigs saved to: {viral_fasta}")
    print(f"[checkv_prefilter] CheckV pre-filter completed successfully")