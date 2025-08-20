import subprocess
import os
import pandas as pd
import shutil


def get_sample_name(file):
    if file.endswith(".fq.gz") or file.endswith(".fastq"):
        return file[:-6]
    elif file.endswith(".fq"):
        return file[:-3]
    elif file.endswith(".fastq.gz"):
        return file[:-9]


def filter_checkv(output, sample, paths):
    checkv_dir = os.path.join(paths["checkv"], sample)
    dat = pd.read_table(f"{checkv_dir}/quality_summary.tsv", header=0)
    checkv = dat[
        dat["checkv_quality"].isin(["Complete", "High-quality", "Medium-quality"])
    ]["contig_id"].tolist()
    final_dir = os.path.join(paths["combination"], sample)
    highq_dir = os.path.join(paths["high_quality"], sample)
    with open(f"{final_dir}/contigs.fa") as f, open(
        f"{highq_dir}/contigs.fa", "w"
    ) as f1:
        while True:
            line = f.readline()
            if not line:
                break
            contig = line[1:-1]
            seq = f.readline()[:-1]
            if contig in checkv:
                f1.write(f">{contig}\n{seq}\n")


def final_info(output, sample, paths):
    checkv_dir = os.path.join(paths["checkv"], sample)
    final_dir = os.path.join(paths["combination"], sample)
    highq_dir = os.path.join(paths["high_quality"], sample)
    nondup_dir = os.path.join(paths["final_non_dup"], sample)
    checkv = pd.read_table(f"{checkv_dir}/quality_summary.tsv", header=0, index_col=0)
    blastn = pd.read_table(f"{final_dir}/blastn_info.txt", header=0, index_col=0)
    info = pd.read_table(f"{final_dir}/info.txt", header=0, index_col=0)
    subprocess.call(
        [f"cat {nondup_dir}/final.fasta | grep '>' > {nondup_dir}/temp.txt"], shell=True
    )
    contig = []
    contig_blastn = []
    with open(f"{nondup_dir}/temp.txt", "r") as fi:
        for line in fi:
            contig.append(line[1:-1])
    for ct in contig:
        if info.loc[ct, "blastn"] == 1:
            contig_blastn.append(ct)
    checkv.loc[contig, "checkv_quality"].to_csv(
        f"{nondup_dir}/completeness.txt", header=True, index=True, sep="\t"
    )
    info.loc[contig].to_csv(f"{nondup_dir}/info.txt", header=True, index=True, sep="\t")
    blastn.loc[contig_blastn].to_csv(
        f"{nondup_dir}/blastn_info.txt", header=True, index=True, sep="\t"
    )
    subprocess.call([f"rm {nondup_dir}/temp.txt"], shell=True)


def remove_inter_result(output):
    """
    清理中间结果文件
    
    Args:
        output: 输出目录路径
    """
    import glob
    from utils.common import safe_remove_directory, get_logger
    
    logger = get_logger("remove_inter_result")
    logger.info(f"开始清理中间结果文件: {output}")
    
    # 定义需要清理的中间结果目录
    intermediate_dirs = [
        "1.trimmed",
        "2.host_removed",
        "3.assembly",
        "4.blastn",
        "5.virsorter",
        "6.dvf",
        "7.vibrant",
        "8.checkv_prefilter",
        "9.combination",
        "10.checkv",
        "11.high_quality",
        "12.final_non_dup"
    ]
    
    cleaned_count = 0
    for dir_name in intermediate_dirs:
        dir_path = os.path.join(output, dir_name)
        if os.path.exists(dir_path):
            if safe_remove_directory(dir_path, logger):
                cleaned_count += 1
    
    # 清理临时文件
    temp_patterns = [
        os.path.join(output, "*.tmp"),
        os.path.join(output, "temp_*"),
        os.path.join(output, "**/temp.txt"),
    ]
    
    for pattern in temp_patterns:
        for temp_file in glob.glob(pattern, recursive=True):
            try:
                os.remove(temp_file)
                logger.info(f"删除临时文件: {temp_file}")
                cleaned_count += 1
            except Exception as e:
                logger.warning(f"删除临时文件失败 {temp_file}: {e}")
    
    logger.info(f"清理完成，共清理 {cleaned_count} 个项目")


def make_clean_dir(path):
    """
    创建一个干净的目录。如果目录已存在则先删除再新建。
    
    Args:
        path: 目录路径
    """
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
