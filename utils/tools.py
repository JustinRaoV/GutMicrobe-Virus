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
    print(f"Removing intermediate results from {output}...")


def make_clean_dir(path):
    """
    创建一个干净的目录。如果目录已存在则先删除再新建。
    """
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
