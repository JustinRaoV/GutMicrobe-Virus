"""质量评估和结果整合"""
import os
import re
import subprocess
import shutil
import pandas as pd
from src.config import get_software, get_database
from src.utils import ensure_dir, get_path


# CheckV质量等级排序 (数值越大质量越高)
QUALITY_RANK = {
    "Complete": 5,
    "High-quality": 4,
    "Medium-quality": 3,
    "Low-quality": 2,
    "Not-determined": 1
}


def get_dedup_key(contig_id):
    """
    生成用于去重的key
    
    去重逻辑 - 跨工具去重：
    1. VirSorter2 的 ||full 表示整条contig都是病毒
       - 如果geNomad也识别了同一条contig（无provirus后缀），则是同一病毒
    2. VirSorter2 的 ||N_partial 表示contig的第N个病毒片段
    3. geNomad 的 |provirus_START_END 表示特定区域的病毒
    
    去重规则：
    - k141_8||full 和 k141_8 → 同一病毒（都是整条contig）
    - k141_8||full 和 k141_8|provirus_100_3000 → 不同（一个是全长，一个是片段）
    - k141_8||0_partial 和 k141_8||1_partial → 不同（不同片段）
    - k141_8|provirus_100_3000 和 k141_8|provirus_5000_8000 → 不同（不同区域）
    
    返回: (原始contig_id, 区域标识)
    """
    original_id = contig_id
    region_type = "full"  # 默认是全长
    
    # VirSorter2 后缀处理
    if "||" in contig_id:
        parts = contig_id.split("||")
        original_id = parts[0]
        suffix = parts[1] if len(parts) > 1 else ""
        
        if suffix == "full" or suffix == "lt2gene":
            region_type = "full"
        elif "_partial" in suffix:
            # ||0_partial, ||1_partial 等是不同区域
            region_type = suffix  # 保留原后缀作为区域标识
    
    # geNomad provirus 后缀处理
    elif "|provirus_" in contig_id:
        # 提取 provirus_START_END 作为区域标识
        match = re.search(r'\|provirus_(\d+_\d+)$', contig_id)
        if match:
            original_id = contig_id[:match.start()]
            region_type = f"provirus_{match.group(1)}"
    
    return (original_id, region_type)


def run_combination(ctx):
    """整合病毒检测结果 - 直接合并文件"""
    out_dir = ensure_dir(get_path(ctx, "combination"))
    out_file = os.path.join(out_dir, "contigs.fa")
    
    # 待合并的文件路径
    vs2_file = get_path(ctx, "virsorter", "vs2-pass2/final-viral-combined.fa")
    
    input_basename = os.path.splitext(os.path.basename(get_path(ctx, "vsearch", "contigs.fa")))[0]
    genomad_file = get_path(ctx, "genomad", f"{input_basename}_summary/{input_basename}_virus.fna")
    
    ctx["logger"].info("开始合并病毒检测结果...")
    
    merged_count = 0
    with open(out_file, "w") as fout:
        # 1. 合并 VirSorter2 结果
        if os.path.exists(vs2_file):
            ctx["logger"].info(f"正在合并 VirSorter2 结果: {vs2_file}")
            with open(vs2_file) as fin:
                for line in fin:
                    fout.write(line)
                    if line.startswith(">"):
                        merged_count += 1
        else:
             ctx["logger"].warning(f"未找到 VirSorter2 结果文件: {vs2_file}")

        # 2. 合并 geNomad 结果
        if os.path.exists(genomad_file):
            ctx["logger"].info(f"正在合并 geNomad 结果: {genomad_file}")
            with open(genomad_file) as fin:
                for line in fin:
                    fout.write(line)
                    if line.startswith(">"):
                        merged_count += 1
        else:
             ctx["logger"].warning(f"未找到 geNomad 结果文件: {genomad_file}")

    ctx["logger"].info(f"合并完成，共写入 {merged_count} 条序列到: {out_file}")


def run_checkv(ctx):
    """CheckV质量评估"""
    in_file = get_path(ctx, "combination", "contigs.fa")
    out_dir = get_path(ctx, "checkv")
    
    cmd = (
        f"{get_software(ctx['config'], 'checkv')} end_to_end {in_file} {out_dir} "
        f"-d {get_database(ctx['config'], 'checkv')} -t {ctx['threads']}"
    )
    subprocess.run(cmd, shell=True, check=True)
    ctx["logger"].info("CheckV质量评估完成")


def run_high_quality(ctx):
    """筛选高质量病毒 - 跨工具去重并保留最高质量版本"""
    checkv_file = get_path(ctx, "checkv", "quality_summary.tsv")
    dat = pd.read_table(checkv_file)
    
    # 只保留高质量序列 (Complete, High-quality, Medium-quality)
    quality_filter = ["Complete", "High-quality", "Medium-quality"]
    high_quality = dat[dat["checkv_quality"].isin(quality_filter)].copy()
    
    # 提取去重key: (原始contig_id, 区域标识)
    high_quality["dedup_key"] = high_quality["contig_id"].apply(get_dedup_key)
    # 提取原始ID和区域类型
    high_quality["original_id"] = high_quality["dedup_key"].apply(lambda x: x[0])
    high_quality["region_type"] = high_quality["dedup_key"].apply(lambda x: x[1])
    
    # 添加质量排序分数
    high_quality["quality_rank"] = high_quality["checkv_quality"].map(QUALITY_RANK)
    
    # 跨工具去重逻辑：
    # - 同一original_id + 都是"full"类型 → 需要去重（如 k141_8||full 和 k141_8）
    # - 同一original_id + 不同区域类型 → 保留（不同病毒片段）
    high_quality["completeness_num"] = pd.to_numeric(high_quality["completeness"], errors="coerce").fillna(0)
    
    # 创建实际去重key：对于full类型只用original_id，其他类型保留完整key
    def get_final_dedup_key(row):
        if row["region_type"] == "full":
            return row["original_id"]
        else:
            return f"{row['original_id']}|{row['region_type']}"
    
    high_quality["final_dedup_key"] = high_quality.apply(get_final_dedup_key, axis=1)
    
    # 按去重key分组，选择最佳记录
    high_quality_sorted = high_quality.sort_values(
        by=["quality_rank", "completeness_num", "contig_length"],
        ascending=[False, False, False]
    )
    best_records = high_quality_sorted.drop_duplicates(subset=["final_dedup_key"], keep="first")
    
    # 提取最终保留的序列ID
    hq_ids = set(best_records["contig_id"])
    
    ctx["logger"].info(f"原始高质量序列: {len(high_quality)}条, 去重后: {len(hq_ids)}条")
    
    # 提取序列
    in_file = get_path(ctx, "combination", "contigs.fa")
    out_file = os.path.join(ensure_dir(get_path(ctx, "high_quality")), "contigs.fa")
    
    with open(in_file) as fin, open(out_file, "w") as fout:
        write = False
        for line in fin:
            if line.startswith(">"):
                contig_id = line[1:].strip().split()[0]
                write = contig_id in hq_ids
            if write:
                fout.write(line)
    
    ctx["logger"].info(f"筛选出{len(hq_ids)}个高质量病毒")


def run_busco(ctx):
    """BUSCO过滤 - 去除细菌污染，并重命名序列"""
    in_file = get_path(ctx, "high_quality", "contigs.fa")
    out_dir = ensure_dir(get_path(ctx, "busco_filter"))
    busco_db = get_database(ctx["config"], "busco")
    sample_name = ctx["sample"]
    
    # 运行BUSCO
    cmd = f"{get_software(ctx['config'], 'busco')} -f -i {in_file} -c {ctx['threads']} -o {out_dir} -m geno -l {busco_db} --offline"
    subprocess.run(cmd, shell=True, check=True)
    
    # 统计预测基因数
    predicted_file = os.path.join(out_dir, "prodigal_output/predicted_genes/predicted.fna")
    gene_counts = {}
    if os.path.exists(predicted_file):
        with open(predicted_file) as f:
            for line in f:
                if line.startswith(">"):
                    contig = "_".join(line[1:].split()[0].split("_")[:-1])
                    gene_counts[contig] = gene_counts.get(contig, 0) + 1
    
    # 统计BUSCO命中数
    busco_file = os.path.join(out_dir, "run_bacteria_odb12/full_table.tsv")
    busco_counts = {}
    if os.path.exists(busco_file):
        with open(busco_file) as f:
            # 跳过注释行
            for line in f:
                if not line.startswith("#"):
                    parts = line.strip().split("\t")
                    if len(parts) >= 3 and parts[1] in ("Complete", "Fragmented"):
                        contig = parts[2].split(":")[-2] if ":" in parts[2] else parts[2].split()[0]
                        busco_counts[contig] = busco_counts.get(contig, 0) + 1
    
    # 筛选：移除BUSCO比例过高的contig（细菌污染）
    threshold = float(ctx["config"].get("parameters", {}).get("busco_ratio_threshold", 0.05))
    to_remove = {c for c, total in gene_counts.items() 
                 if total > 0 and busco_counts.get(c, 0) / total > threshold}
    
    ctx["logger"].info(f"BUSCO阈值={threshold}, 移除{len(to_remove)}个污染contig")
    
    # 输出过滤后序列并重命名为"样本名_序号"
    out_file = os.path.join(out_dir, "contigs.fa")
    seq_index = 1
    with open(in_file) as fin, open(out_file, "w") as fout:
        write = True
        for line in fin:
            if line.startswith(">"):
                contig = line[1:].strip().split()[0]
                write = contig not in to_remove
                if write:
                    # 重命名为"样本名_序号"
                    fout.write(f">{sample_name}_{seq_index}\n")
                    seq_index += 1
            elif write:
                fout.write(line)
    
    ctx["logger"].info(f"BUSCO过滤完成，输出{seq_index - 1}条序列")
