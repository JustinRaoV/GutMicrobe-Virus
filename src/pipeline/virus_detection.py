"""病毒检测模块 - 可配置的多工具检测"""
import os
import subprocess
import shutil
from src.config import get_software, get_params, is_tool_enabled, get_database
from src.utils import ensure_dir, get_path


def _skip_if_disabled(ctx, tool_name):
    """检查工具是否被禁用"""
    if not is_tool_enabled(ctx["config"], tool_name):
        ctx["logger"].info(f"跳过{tool_name}")
        return True
    return False


def _get_input_file(ctx):
    """获取病毒检测输入文件: 优先使用checkv预过滤结果"""
    filtered = get_path(ctx, "checkv_prefilter", "filtered_contigs.fa")
    return filtered if os.path.exists(filtered) else get_path(ctx, "vsearch", "contigs.fa")


def run_checkv_prefilter(ctx):
    """CheckV预过滤 - 过滤宿主污染严重的序列
    
    逻辑:
    1. 移除: 宿主基因>10 且 宿主基因>病毒基因*5 的序列 (宿主污染严重)
    2. 保留: 剩下的所有序列 -> filtered_contigs.fa (供后续病毒检测)
    3. 额外: 病毒基因>宿主基因 的序列 -> viral_contigs.fa (高置信度病毒,供结果合并)
    """
    if _skip_if_disabled(ctx, "checkv_prefilter"):
        return
    
    cfg = ctx["config"]
    in_file = get_path(ctx, "vsearch", "contigs.fa")
    out_dir = ensure_dir(get_path(ctx, "checkv_prefilter"))
    checkv_dir = os.path.join(out_dir, "checkv_result")
    
    # 1. 运行CheckV
    cmd = (
        f"{get_software(cfg, 'checkv')} end_to_end {in_file} {checkv_dir} -d {get_database(cfg, 'checkv')} -t {ctx['threads']}"
    )
    subprocess.run(cmd, shell=True, check=True)
    
    # 2. 解析结果并分类
    import pandas as pd
    quality_file = os.path.join(checkv_dir, "quality_summary.tsv")
    df = pd.read_table(quality_file)
    
    host_threshold = cfg.get('parameters', {}).get('checkv_prefilter_host_genes', 10)
    ratio_threshold = cfg.get('parameters', {}).get('checkv_prefilter_ratio', 5)
    
    df['host_genes'] = df['host_genes'].fillna(0)
    df['viral_genes'] = df['viral_genes'].fillna(0)
    
    # 要移除的序列: 宿主基因>10 且 宿主基因>病毒基因*5
    to_remove = df[(df['host_genes'] > host_threshold) & 
                   (df['host_genes'] > df['viral_genes'] * ratio_threshold)]['contig_id'].tolist()
    
    # 保留的所有序列 (剩下的全部)
    all_keep = df[~df['contig_id'].isin(to_remove)]['contig_id'].tolist()
    
    # 高置信度病毒序列: 病毒基因>宿主基因
    viral_contigs = df[(~df['contig_id'].isin(to_remove)) & 
                       (df['viral_genes'] > df['host_genes'])]['contig_id'].tolist()
    
    ctx["logger"].info(f"CheckV预过滤: 移除{len(to_remove)}, 保留{len(all_keep)}, 其中高置信度病毒{len(viral_contigs)}")
    
    # 3. 保存序列列表
    all_keep_list = os.path.join(out_dir, "all_keep_contigs.list")
    with open(all_keep_list, 'w') as f:
        f.write('\n'.join(all_keep) + '\n')
    
    viral_list = os.path.join(out_dir, "viral_contigs.list")
    with open(viral_list, 'w') as f:
        f.write('\n'.join(viral_contigs) + '\n')
    
    # 4. 使用seqkit提取序列
    seqkit = get_software(cfg, 'seqkit')
    
    # 提取所有保留序列 (供后续病毒检测)
    filtered_fa = os.path.join(out_dir, "filtered_contigs.fa")
    cmd = f"{seqkit} grep -f {all_keep_list} {in_file} -o {filtered_fa}"
    subprocess.run(cmd, shell=True, check=True)
    
    # 提取高置信度病毒序列 (供结果合并)
    viral_fa = os.path.join(out_dir, "viral_contigs.fa")
    cmd = f"{seqkit} grep -f {viral_list} {in_file} -o {viral_fa}"
    subprocess.run(cmd, shell=True, check=True)
    
    ctx["logger"].info("CheckV预过滤完成")


def run_virsorter(ctx):
    """VirSorter2 三步走检测"""
    if _skip_if_disabled(ctx, "virsorter"):
        return
    
    cfg = ctx["config"]
    base_dir = get_path(ctx, "virsorter")
    ensure_dir(os.path.dirname(base_dir))
    in_file = _get_input_file(ctx)
    
    # Pass 1: 初次检测
    ctx["logger"].info("VirSorter Pass 1")
    pass1_dir = os.path.join(base_dir, "vs2-pass1")
    cmd = (
        f"{get_software(cfg, 'virsorter')} run -i {in_file} -w {pass1_dir} "
        f"-j {ctx['threads']} {get_params(cfg, 'virsorter_pass1')} all"
    )
    subprocess.run(cmd, shell=True, check=True)
    
    # CheckV中间步骤
    ctx["logger"].info("VirSorter CheckV验证")
    checkv_dir = os.path.join(base_dir, "checkv")
    pass1_result = os.path.join(pass1_dir, "final-viral-combined.fa")
    cmd = (
        f"{get_software(cfg, 'checkv')} end_to_end {pass1_result} {checkv_dir} "
        f"-t {ctx['threads']} -d {get_database(cfg, 'checkv')}"
    )
    subprocess.run(cmd, shell=True, check=True)
    
    # 合并 proviruses.fna 和 viruses.fna
    combined_file = os.path.join(checkv_dir, "combined.fna")
    cmd = f"cat {checkv_dir}/proviruses.fna {checkv_dir}/viruses.fna > {combined_file}"
    subprocess.run(cmd, shell=True, check=True)
    
    # Pass 2: 精细化检测
    ctx["logger"].info("VirSorter Pass 2")
    pass2_dir = os.path.join(base_dir, "vs2-pass2")
    checkv_combined = os.path.join(checkv_dir, "combined.fna")
    cmd = (
        f"{get_software(cfg, 'virsorter')} run -i {checkv_combined} -w {pass2_dir} "
        f"-j {ctx['threads']} {get_params(cfg, 'virsorter_pass2')} all"
    )
    subprocess.run(cmd, shell=True, check=True)
    
    # 复制最终结果到主目录
    final_result = os.path.join(pass2_dir, "final-viral-score.tsv")
    shutil.copy2(final_result, os.path.join(base_dir, "final-viral-score.tsv"))
    
    ctx["logger"].info("VirSorter完成")


def run_dvf(ctx):
    """DeepVirFinder检测"""
    if _skip_if_disabled(ctx, "dvf"):
        return
    
    cfg = ctx["config"]
    out_dir = ensure_dir(get_path(ctx, "dvf"))
    in_file = _get_input_file(ctx)
    
    # Singularity 模式下直接调用，非 Singularity 需要 python 前缀
    dvf_cmd = get_software(cfg, 'dvf')
    if not cfg.get('singularity', {}).get('enabled', False):
        dvf_cmd = f"python {dvf_cmd}"
    
    cmd = f"{dvf_cmd} -i {in_file} -o {out_dir} -c {ctx['threads']}"
    subprocess.run(cmd, shell=True, check=True)
    
    # 过滤结果
    score_th = cfg.get('parameters', {}).get('dvf_score_threshold', 0.9)
    pval_th = cfg.get('parameters', {}).get('dvf_pvalue_threshold', 0.01)
    
    subprocess.run(
        f"awk 'NR>1 && $3>{score_th} && $4<{pval_th} {{print $1}}' "
        f"{out_dir}/*_dvfpred.txt > {out_dir}/virus_dvf.list",
        shell=True, check=True
    )
    ctx["logger"].info("DeepVirFinder完成")


def run_vibrant(ctx):
    """VIBRANT检测"""
    if _skip_if_disabled(ctx, "vibrant"):
        return
    
    out_dir = ensure_dir(get_path(ctx, "vibrant"))
    in_file = _get_input_file(ctx)
    
    vibrant_db = get_database(ctx['config'], 'vibrant')
    cmd = f"{get_software(ctx['config'], 'vibrant')} -i {in_file} -folder {out_dir} -t {ctx['threads']} -d {vibrant_db}/databases -m {vibrant_db}/files"
    subprocess.run(cmd, shell=True, check=True)
    ctx["logger"].info("VIBRANT完成")


def run_blastn(ctx):
    """BLASTN比对 - 对所有数据库进行比对并过滤"""
    if _skip_if_disabled(ctx, "blastn"):
        return
    
    import pandas as pd
    
    in_file = _get_input_file(ctx)
    out_dir = ensure_dir(get_path(ctx, "blastn"))
    blast_db_dir = os.path.join(get_database(ctx['config'], 'root'), "blast")
    
    # 数据库列表
    databases = ["crass", "gpd", "gvd", "mgv", "ncbi"]
    
    # 获取过滤阈值
    cfg = ctx['config'].get('parameters', {})
    pident_threshold = cfg.get('blastn_pident', 50)
    evalue_threshold = cfg.get('blastn_evalue', 1e-10)
    qcovs_threshold = cfg.get('blastn_qcovs', 80)
    
    # 存储所有过滤后的结果
    filtered_all = pd.DataFrame(columns=['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'database'])
    blastn_contigs = []
    
    # 对每个数据库进行比对
    for db_name in databases:
        ctx["logger"].info(f"BLASTN比对: {db_name}")
        db_path = os.path.join(blast_db_dir, db_name)
        out_file = os.path.join(out_dir, f"blastn_{db_name}.out")
        
        # 完整的输出格式
        outfmt = (
            '"6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch '
            'positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames"'
        )
        
        cmd = (
            f"{get_software(ctx['config'], 'blastn')} -query {in_file} -db {db_path} "
            f"-num_threads {ctx['threads']} -max_target_seqs 5 -outfmt {outfmt} -out {out_file}"
        )
        subprocess.run(cmd, shell=True, check=True)
        
        # 读取并过滤结果
        if os.path.getsize(out_file) > 0:
            try:
                df = pd.read_table(out_file, header=None)
                
                # 检查列数
                if df.shape[1] != 24:
                    ctx["logger"].warning(f"BLASTN输出列数异常: {out_file} 列数={df.shape[1]}, 期望24列")
                    # 尝试继续，但可能失败
                
                df.columns = [
                    'qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'nident', 'qlen', 'slen', 
                    'length', 'mismatch', 'positive', 'ppos', 'gapopen', 'gaps', 'qstart', 'qend', 
                    'sstart', 'send', 'bitscore', 'qcovhsp', 'qcovus', 'qseq', 'sstrand', 'frames'
                ]
                
                # 强制转换数值列为float
                for col in ['pident', 'evalue', 'qcovs', 'nident', 'qlen', 'slen', 'length', 
                           'mismatch', 'positive', 'ppos', 'gapopen', 'gaps', 'bitscore', 'qcovhsp', 'qcovus']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # 确保阈值也是数值类型
                pident_threshold = float(pident_threshold)
                evalue_threshold = float(evalue_threshold)
                qcovs_threshold = float(qcovs_threshold)
                
                # 应用过滤条件（先删除NaN行）
                df_filtered = df.dropna(subset=['pident', 'evalue', 'qcovs'])
                df_filtered = df_filtered[
                    (df_filtered['pident'] >= pident_threshold) &
                    (df_filtered['evalue'] <= evalue_threshold) &
                    (df_filtered['qcovs'] >= qcovs_threshold)
                ]
                
                if len(df_filtered) > 0:
                    # 记录通过过滤的contig ID
                    for contig_id in df_filtered['qseqid'].unique():
                        if contig_id not in blastn_contigs:
                            blastn_contigs.append(contig_id)
                    
                    # 保留关键列并添加数据库标识
                    df_filtered = df_filtered[['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs']].copy()
                    df_filtered['database'] = db_name
                    filtered_all = pd.concat([filtered_all, df_filtered], axis=0, ignore_index=True)
                    
                    ctx["logger"].info(f"  {db_name}: {len(df_filtered)} 条比对通过过滤")
                else:
                    ctx["logger"].info(f"  {db_name}: 无比对结果通过过滤")
                    
            except Exception as e:
                ctx["logger"].error(f"BLASTN结果解析失败: {out_file}, 错误: {e}")
                # 打印前几行用于调试
                try:
                    with open(out_file, 'r') as f:
                        first_lines = [next(f) for _ in range(min(3, sum(1 for _ in open(out_file))))]
                        ctx["logger"].debug(f"文件前3行:\n{''.join(first_lines)}")
                except:
                    pass
        else:
            ctx["logger"].info(f"  {db_name}: 无比对结果")
    
    # 保存过滤后的汇总结果
    if len(filtered_all) > 0:
        filtered_all.to_csv(os.path.join(out_dir, "blastn_filtered.tsv"), sep='\t', index=False)
    
    # 保存通过BLASTN过滤的contig列表
    blastn_list_file = os.path.join(out_dir, "blastn_virus.list")
    with open(blastn_list_file, 'w') as f:
        f.write('\n'.join(blastn_contigs) + '\n' if blastn_contigs else '')
    
    ctx["logger"].info(f"BLASTN完成 - 共 {len(blastn_contigs)} 个contig通过过滤")


def get_enabled_tools(config):
    """获取启用的病毒检测工具列表"""
    return [t for t in ["checkv_prefilter", "virsorter", "dvf", "vibrant", "blastn"] 
            if is_tool_enabled(config, t)]
