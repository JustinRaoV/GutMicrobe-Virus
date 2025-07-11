"""
丰度分析模块

本模块包含使用coverm进行contig和基因丰度分析的功能。
"""

import subprocess
import sys
import os
from core.config_manager import get_config


def run_coverm_contig(**context):
    """使用coverm进行contig丰度分析
    
    对host_removed后的fastq文件进行contig丰度分析，使用vclust_dedup生成的viruslib_nr.fa作为参考。
    """
    print("[coverm_contig] Running coverm contig abundance analysis...")
    
    config = get_config()
    r1 = context['input1']
    r2 = context['input2']
    viruslib_contig_path = context['viruslib_contig_path']
    output_dir = context['output']
    sample = context['sample']
    threads = context['threads']
    
    # 创建输出目录
    coverm_dir = os.path.join(output_dir, "coverm_contig")
    if os.path.exists(coverm_dir):
        try:
            subprocess.call([f"rm -rf {coverm_dir}"], shell=True)
        except Exception as e:
            print(f"[coverm_contig] Warning: Failed to remove {coverm_dir}: {e}")
    subprocess.call([f"mkdir -p {coverm_dir}"], shell=True)
    
    # 构建coverm命令
    output_file = os.path.join(coverm_dir, f"{sample}_coverm.tsv")
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"coverm contig "
        f"-1 {r1} -2 {r2} "
        f"--reference {viruslib_contig_path} "
        f"--min-read-percent-identity 95 "
        f"--min-read-aligned-percent 75 "
        f"-m count "
        f"--output-format dense "
        f"-t {threads} "
        f"-o {output_file}"
    )
    
    print(f"[coverm_contig] Running: {cmd}")
    ret = subprocess.call([cmd], shell=True)
    if ret != 0:
        sys.exit("ERROR: coverm contig error")
    
    print(f"[coverm_contig] Contig abundance analysis completed: {output_file}")


def run_coverm_gene(**context):
    """使用coverm进行基因丰度分析
    
    对host_removed后的fastq文件进行基因丰度分析，使用cdhit_dedup生成的gene_cdhit.fq作为参考。
    """
    print("[coverm_gene] Running coverm gene abundance analysis...")
    
    config = get_config()
    r1 = context['input1']
    r2 = context['input2']
    viruslib_gene_path = context['viruslib_gene_path']
    output_dir = context['output']
    sample = context['sample']
    threads = context['threads']
    
    # 创建输出目录
    coverm_dir = os.path.join(output_dir, "coverm_gene")
    if os.path.exists(coverm_dir):
        try:
            subprocess.call([f"rm -rf {coverm_dir}"], shell=True)
        except Exception as e:
            print(f"[coverm_gene] Warning: Failed to remove {coverm_dir}: {e}")
    subprocess.call([f"mkdir -p {coverm_dir}"], shell=True)
    
    # 构建coverm命令
    output_file = os.path.join(coverm_dir, f"{sample}_gene_coverm.tsv")
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"coverm contig "
        f"-1 {r1} -2 {r2} "
        f"--reference {viruslib_gene_path} "
        f"--min-read-percent-identity 95 "
        f"--min-read-aligned-percent 75 "
        f"-m count "
        f"--output-format dense "
        f"-t {threads} "
        f"-o {output_file}"
    )
    
    print(f"[coverm_gene] Running: {cmd}")
    ret = subprocess.call([cmd], shell=True)
    if ret != 0:
        sys.exit("ERROR: coverm gene error")
    
    print(f"[coverm_gene] Gene abundance analysis completed: {output_file}")


def run_abundance_analysis(**context):
    """运行完整的丰度分析
    
    包括contig和基因丰度分析。
    """
    print("[abundance_analysis] Running complete abundance analysis...")
    
    # 运行contig丰度分析
    run_coverm_contig(**context)
    
    # 运行基因丰度分析
    run_coverm_gene(**context)
    
    print("[abundance_analysis] Complete abundance analysis finished") 