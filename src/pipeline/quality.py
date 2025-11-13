"""质量评估和结果整合"""
import os
import subprocess
import shutil
import pandas as pd
from src.config import get_software, get_database
from src.utils import ensure_dir, get_path


def run_combination(ctx):
    """整合病毒检测结果"""
    out_dir = ensure_dir(get_path(ctx, "combination"))
    
    def read_contigs_from_file(file_path, parser=None):
        """读取单个文件的contig列表"""
        contigs = set()
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path) as f:
                for line in f:
                    contig = parser(line) if parser else line.strip()
                    if contig:
                        contigs.add(contig)
        return contigs
    
    # 收集各工具结果
    tools = {
        "virsorter": read_contigs_from_file(
            get_path(ctx, "virsorter", "vs2-pass2/final-viral-combined.fa"),
            lambda x: x[1:].split("|")[0].split("||")[0].strip() if x.startswith(">") else None
        ),
        "dvf": read_contigs_from_file(get_path(ctx, "dvf", "virus_dvf.list")),
        "checkv_viral": read_contigs_from_file(get_path(ctx, "checkv_prefilter", "viral_contigs.list"))
    }
    
    # VIBRANT: 读取 phages_combined.txt 文件
    vibrant_dir = get_path(ctx, "vibrant")
    vibrant_file = os.path.join(vibrant_dir, "VIBRANT_contigs/VIBRANT_phages_contigs/contigs.phages_combined.txt")
    vibrant_contigs = set()
    if os.path.exists(vibrant_file):
        with open(vibrant_file) as f:
            for line in f:
                contig = line.strip().split()[0]
                if contig:
                    vibrant_contigs.add(contig)
    tools["vibrant"] = vibrant_contigs
    
    # BLASTN: 读取过滤后的结果列表
    tools["blastn"] = read_contigs_from_file(get_path(ctx, "blastn", "blastn_virus.list"))
    
    # 统计
    all_contigs = set().union(*tools.values())
    ctx["logger"].info(f"各工具检出: " + ", ".join([f"{k}={len(v)}" for k, v in tools.items()]) + f", 总计={len(all_contigs)}")
    
    # 计算命中数并筛选
    min_hit = int(ctx["config"].get("virus_detection", {}).get("min_tools_required", 1))
    final_contigs = {c for c in all_contigs if sum(c in tool_set for tool_set in tools.values()) >= min_hit}
    ctx["logger"].info(f"最小命中数={min_hit}, 通过筛选={len(final_contigs)}")
    
    # 提取序列
    with open(get_path(ctx, "vsearch", "contigs.fa")) as fin, open(os.path.join(out_dir, "contigs.fa"), "w") as fout:
        write = False
        for line in fin:
            if line.startswith(">"):
                write = line[1:].strip() in final_contigs
            if write:
                fout.write(line)
    
    # 保存统计
    with open(os.path.join(out_dir, "info.txt"), "w") as f:
        f.write("contig\tblastn\tvirsorter\tdvf\tvibrant\tcheckv_viral\n")
        for c in sorted(final_contigs):
            f.write(f"{c}\t" + "\t".join([str(int(c in tools[k])) for k in ["blastn", "virsorter", "dvf", "vibrant", "checkv_viral"]]) + "\n")
    
    ctx["logger"].info(f"结果保存至: {out_dir}")


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
    """筛选高质量病毒"""
    checkv_file = get_path(ctx, "checkv", "quality_summary.tsv")
    dat = pd.read_table(checkv_file)
    high_quality = dat[dat["checkv_quality"].isin(["Complete", "High-quality", "Medium-quality"])]
    
    # 提取高质量序列ID
    hq_ids = set(high_quality["contig_id"])
    
    # 提取序列
    in_file = get_path(ctx, "combination", "contigs.fa")
    out_file = os.path.join(ensure_dir(get_path(ctx, "high_quality")), "contigs.fa")
    
    with open(in_file) as fin, open(out_file, "w") as fout:
        write = False
        for line in fin:
            if line.startswith(">"):
                write = line[1:].strip() in hq_ids
            if write:
                fout.write(line)
    
    ctx["logger"].info(f"筛选出{len(hq_ids)}个高质量病毒")


def run_busco(ctx):
    """BUSCO过滤 - 去除细菌污染"""
    in_file = get_path(ctx, "high_quality", "contigs.fa")
    out_dir = ensure_dir(get_path(ctx, "busco_filter"))
    busco_db = get_database(ctx["config"], "busco")
    
    # 运行BUSCO
    cmd = f"{get_software(ctx['config'], 'busco')} -f -i {in_file} -c {ctx['threads']} -o {out_dir} -m geno -l {busco_db} --offline"
    subprocess.run(cmd, shell=True, check=True)
    
    # 统计预测基因数
    predicted_file = os.path.join(out_dir, "prodigal_output/predicted_genes/predicted.fna")
    gene_counts = {}
    with open(predicted_file) as f:
        for line in f:
            if line.startswith(">"):
                contig = "_".join(line[1:].split()[0].split("_")[:-1])
                gene_counts[contig] = gene_counts.get(contig, 0) + 1
    
    # 统计BUSCO命中数
    busco_file = os.path.join(out_dir, "run_bacteria_odb12/full_table.tsv")
    busco_counts = {}
    with open(busco_file) as f:
        next(f)  # 跳过表头
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 3 and parts[1] in ("Complete", "Fragmented"):
                contig = parts[2].split(":")[-2] if ":" in parts[2] else parts[2].split()[0]
                busco_counts[contig] = busco_counts.get(contig, 0) + 1
    
    # 筛选：移除BUSCO比例过高的contig（细菌污染）
    threshold = float(ctx["config"].get("parameters", {}).get("busco_ratio_threshold", 0.2))
    to_remove = {c for c, total in gene_counts.items() 
                 if total > 0 and busco_counts.get(c, 0) / total > threshold}
    
    ctx["logger"].info(f"BUSCO阈值={threshold}, 移除{len(to_remove)}个污染contig")
    
    # 输出过滤后序列
    out_file = os.path.join(out_dir, "contigs.fa")
    with open(in_file) as fin, open(out_file, "w") as fout:
        write = True
        for line in fin:
            if line.startswith(">"):
                contig = line[1:].strip().split()[0]
                write = contig not in to_remove
            if write:
                fout.write(line)
    
    ctx["logger"].info(f"BUSCO过滤完成")
