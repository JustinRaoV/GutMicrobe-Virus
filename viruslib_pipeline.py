#!/usr/bin/env python3
"""病毒库构建流程"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import load_config, get_software, get_params, get_database
from src.logger import setup_logger
from src.utils import run_cmd, ensure_dir


def parse_args():
    p = argparse.ArgumentParser(description="病毒库构建")
    p.add_argument("-i", "--input", help="输入目录(包含各样本的contigs.fa文件)")
    p.add_argument("-t", "--threads", type=int, default=1, help="线程数")
    p.add_argument("-o", "--output", default="viruslib_result", help="输出目录 (默认: viruslib_result)")
    p.add_argument("--upstream-result", help="上游分析结果目录 (默认从此目录读取所有样本的13.busco_filter/*/contigs.fa)")
    p.add_argument("--db", default="~/db", help="数据库目录")
    p.add_argument("--config", default="config/config.yaml", help="配置文件")
    
    args = p.parse_args()
    
    # 如果没有指定输入，使用默认的上游结果目录
    if not args.input and not args.upstream_result:
        args.upstream_result = "result"
    
    return args


def collect_input_files(args, logger):
    """收集输入的contigs文件"""
    input_files = []
    
    if args.input:
        # 从指定目录读取contigs文件
        logger.info(f"从输入目录收集文件: {args.input}")
        for f in os.listdir(args.input):
            if f.endswith((".fa", ".fasta", ".fna")):
                input_files.append(os.path.join(args.input, f))
    elif args.upstream_result:
        # 从上游分析结果读取
        logger.info(f"从上游结果收集文件: {args.upstream_result}")
        busco_dir = os.path.join(args.upstream_result, "*/13.busco_filter/*/contigs.fa")
        import glob
        input_files = glob.glob(busco_dir)
        
        # 如果没找到，尝试不带样本名的路径
        if not input_files:
            busco_dir = os.path.join(args.upstream_result, "13.busco_filter/*/contigs.fa")
            input_files = glob.glob(busco_dir)
    
    if not input_files:
        raise RuntimeError("未找到输入文件！请检查输入目录或上游结果目录")
    
    logger.info(f"找到 {len(input_files)} 个contigs文件")
    return input_files


def merge_and_rename_contigs(input_files, output_file, logger):
    """合并contigs文件并重命名为vOTU1-vOTUn"""
    logger.info("合并并重命名contigs")
    
    votu_counter = 1
    with open(output_file, 'w') as fout:
        for input_file in input_files:
            with open(input_file) as fin:
                for line in fin:
                    if line.startswith(">"):
                        # 重命名为vOTU编号
                        fout.write(f">vOTU{votu_counter}\n")
                        votu_counter += 1
                    else:
                        fout.write(line)
    
    logger.info(f"合并完成: {votu_counter - 1} 个序列")
    return votu_counter - 1


def run_vclust(config, input_file, output_dir, threads, logger):
    """运行vclust去冗余（三步走）"""
    vclust = get_software(config, 'vclust')
    
    # Step 1: prefilter
    logger.info("Step 1: vclust prefilter")
    fltr_file = os.path.join(output_dir, "fltr.txt")
    cmd = f"{vclust} prefilter -i {input_file} -o {fltr_file} --min-ident 0.95"
    run_cmd(cmd, logger)
    
    # Step 2: align
    logger.info("Step 2: vclust align")
    ani_file = os.path.join(output_dir, "ani.tsv")
    cmd = f"{vclust} align -i {input_file} -o {ani_file} --filter {fltr_file}"
    run_cmd(cmd, logger)
    
    # Step 3: cluster
    logger.info("Step 3: vclust cluster")
    clusters_file = os.path.join(output_dir, "clusters.tsv")
    ids_file = os.path.join(output_dir, "ani.ids.tsv")
    cmd = (
        f"{vclust} cluster -i {ani_file} -o {clusters_file} --ids {ids_file} "
        f"--algorithm leiden --metric ani --ani 0.95 --qcov 0.85"
    )
    run_cmd(cmd, logger)
    
    return clusters_file


def extract_representative_sequences(clusters_file, input_fasta, output_fasta, config, logger):
    """从clusters提取代表序列并重命名"""
    logger.info("提取代表序列")
    
    # 提取代表序列ID（每个cluster的第一个序列）
    repr_list = os.path.join(os.path.dirname(clusters_file), "representatives.list")
    cmd = f"awk 'NR==1{{next}} !seen[$2]++{{print $1}}' {clusters_file} > {repr_list}"
    run_cmd(cmd, logger)
    
    # 使用seqkit提取序列
    temp_fasta = output_fasta + ".tmp"
    seqkit = get_software(config, 'seqkit')
    cmd = f"{seqkit} grep -f {repr_list} {input_fasta} -o {temp_fasta}"
    run_cmd(cmd, logger)
    
    # 重命名为vOTU1-vOTUn
    logger.info("重命名为vOTU编号")
    votu_counter = 1
    with open(temp_fasta) as fin, open(output_fasta, 'w') as fout:
        for line in fin:
            if line.startswith(">"):
                fout.write(f">vOTU{votu_counter}\n")
                votu_counter += 1
            else:
                fout.write(line)
    
    os.remove(temp_fasta)
    logger.info(f"提取并重命名完成: {votu_counter - 1} 个代表性vOTU")
    return votu_counter - 1


def run_pipeline(args):
    """运行病毒库构建流程"""
    config = load_config(args.config)
    logger = setup_logger("viruslib", args.output)
    
    logger.info("=== 病毒库构建流程 ===")
    
    # 1. 收集并合并contigs
    logger.info("[1/4] 收集并合并contigs")
    merge_dir = ensure_dir(os.path.join(args.output, "1.merge_contigs"))
    input_files = collect_input_files(args, logger)
    merged_file = os.path.join(merge_dir, "all_contigs.fa")
    total_seqs = merge_and_rename_contigs(input_files, merged_file, logger)
    
    # 2. vclust去冗余（三步走）
    logger.info("[2/4] vclust去冗余")
    vclust_dir = ensure_dir(os.path.join(args.output, "2.vclust_dedup"))
    clusters_file = run_vclust(config, merged_file, vclust_dir, args.threads, logger)
    
    # 3. 提取代表序列并重命名
    logger.info("[3/4] 提取代表序列")
    nr_fasta = os.path.join(vclust_dir, "viruslib_nr.fa")
    nr_count = extract_representative_sequences(clusters_file, merged_file, nr_fasta, config, logger)
    
    logger.info(f"去冗余统计: {total_seqs} -> {nr_count} (去除 {total_seqs - nr_count} 个冗余序列)")
    
    # 4. PhaBox2预测
    logger.info("[4/4] PhaBox2预测")
    phabox_dir = ensure_dir(os.path.join(args.output, "3.phabox2"))
    phabox_db = get_database(config, 'phabox2')
    cmd = (
        f"{get_software(config, 'phabox2')} --contigs {nr_fasta} "
        f"--threads {args.threads} --out {phabox_dir} --database {phabox_db}"
    )
    run_cmd(cmd, logger)
    
    logger.info("=== 流程完成 ===")
    logger.info(f"最终病毒库: {nr_fasta}")
    logger.info(f"PhaBox2结果: {phabox_dir}")


def main():
    try:
        run_pipeline(parse_args())
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
