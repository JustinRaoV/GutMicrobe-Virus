"""
病毒分析模块

本模块包含序列比对和结果整合功能。
"""

import subprocess
import sys
import os
from core.config_manager import get_config


def run_blastn(**context):
    """BLASTN 比对
    
    对过滤后的 contigs 进行 BLASTN 比对，搜索病毒数据库。
    """
    print("[blastn] Running blastn...")
    
    config = get_config()
    db_root = context['db']
    # 优先用config.ini里的blastn_database，否则用--db拼接默认子路径
    if config.has_section('database') and config['database'].get('blastn_database'):
        blastn_db_root = config['database']['blastn_database']
    else:
        blastn_db_root = os.path.join(db_root, "blastn_database")
    blastn_dir = os.path.join(context['paths']["blastn"], context['sample'])
    
    # 清理并创建目录
    if os.path.exists(blastn_dir):
        try:
            subprocess.call([f"rm -rf {blastn_dir}"], shell=True)
        except Exception as e:
            print(f"[blastn] Warning: Failed to remove {blastn_dir}: {e}")
    subprocess.call([f"mkdir -p {blastn_dir}"], shell=True)
    
    # 对多个数据库进行比对，使用主环境
    for dbname in ["crass", "gpd", "gvd", "mgv", "ncbi"]:
        out_path = f"{blastn_dir}/{dbname}.out"
        cmd = (
            f"{config['environment']['main_conda_activate']} && "
            f'blastn -query {context["paths"]["vsearch"]}/{context["sample"]}/contig_1k.fasta '
            f'-db {blastn_db_root}/{dbname} -num_threads {context["threads"]} -max_target_seqs 1 '
            f'-outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " '
            f'-out {out_path}'
        )
        print(f"[blastn] Running: {cmd}")
        ret = subprocess.call([cmd], shell=True)
        if ret != 0:
            sys.exit("ERROR: blastn error")


def run_combination(**context):
    """合并病毒识别和比对结果
    
    整合所有病毒识别工具的结果，生成候选病毒序列。
    支持的工具：VirSorter、DeepVirFinder、VIBRANT、BLASTN、CheckV预过滤
    用户可以通过配置选择使用哪些工具的结果。
    """
    print("[combination] Combining all virus detection results")
    
    final_dir = os.path.join(context['paths']["combination"], context['sample'])
    
    # 清理并创建目录
    if os.path.exists(final_dir):
        try:
            subprocess.call([f"rm -rf {final_dir}"], shell=True)
        except Exception as e:
            print(f"[combination] Warning: Failed to remove {final_dir}: {e}")
    subprocess.call([f"mkdir -p {final_dir}"], shell=True)
    
    # 合并结果
    from utils.tools import filter_vircontig_enhanced
    ret = filter_vircontig_enhanced(context['output'], context['sample'], context['paths'])
    if ret != 0:
        sys.exit("ERROR: combine error") 