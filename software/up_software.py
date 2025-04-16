import shutil
import subprocess
import os
import sys
import pandas as pd
from tools import *


def run_fastqc(output, input1, input2, threads):
    fastqc_dir = os.path.join(output, "1.fastqc")
    os.makedirs(fastqc_dir, exist_ok=True)
    cmd = [
        "fastqc", input1, input2,
        "-t", str(threads),
        "-o", fastqc_dir
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"FastQC failed: {e}")


def run_trim(output, threads, input1, input2, sample1, sample2, adapter):
    trim_dir = os.path.join(output, "2.trim")
    os.makedirs(trim_dir, exist_ok=True)
    cmd = [
        "trimmomatic", "PE",
        "-threads", str(threads),
        "-phred33",
        input1, input2,
        f"{trim_dir}/{sample1}.fastq",
        f"{trim_dir}/{sample1}_single.fastq",
        f"{trim_dir}/{sample2}.fastq",
        f"{trim_dir}/{sample2}_single.fastq",
        f"ILLUMINACLIP:{adapter}:2:30:10",
        "SLIDINGWINDOW:4:20",
        "MINLEN:50"
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"Trimmomatic error: {e}")


def run_bowtie2(output, threads, sample1, sample2, index_path, sample):
    bowtie2_dir = os.path.join(output, "3.bowtie2")
    sample_dir = os.path.join(bowtie2_dir, sample)
    trim_dir = os.path.join(output, "2.trim")

    if os.path.exists(sample_dir):
        shutil.rmtree(sample_dir)  # 修复：使用shutil.rmtree删除非空目录
    os.makedirs(sample_dir, exist_ok=True)

    try:
        shutil.copy(os.path.join(trim_dir, f"{sample1}.fastq"),
                    os.path.join(sample_dir, f"{sample1}.fastq"))
        shutil.copy(os.path.join(trim_dir, f"{sample2}.fastq"),
                    os.path.join(sample_dir, f"{sample2}.fastq"))
    except Exception as e:
        sys.exit(f"File copy failed: {e}")

    for index in index_path:
        input1 = os.path.join(sample_dir, f"{sample1}.fastq")
        input2 = os.path.join(sample_dir, f"{sample2}.fastq")
        tmp_prefix = os.path.join(sample_dir, "tmp")
        sam_output = os.path.join(sample_dir, "tmp.sam")
        cmd = [
            "bowtie2", "-p", str(threads),
            "-x", index,
            "-1", input1, "-2", input2,
            "--un-conc", tmp_prefix,
            "-S", sam_output
        ]
        try:
            subprocess.run(cmd, check=True)
            shutil.move(f"{tmp_prefix}.1", input1)
            shutil.move(f"{tmp_prefix}.2", input2)
        except Exception as e:
            sys.exit(f"bowtie2 failed: {e}")

    # 使用安全路径处理
    subprocess.run(["rm", "-rf", f"{output}/2.trim/{sample}*"], check=False)
    subprocess.run(["rm", "-rf", f"{output}/3.bowtie2/{sample}/tmp.sam"], check=False)


def run_spades(output, threads, sample1, sample2, sample):
    spades_dir = os.path.join(output, "4.spades", sample)
    if os.path.exists(spades_dir):
        shutil.rmtree(spades_dir)
    os.makedirs(spades_dir, exist_ok=True)

    cmd = [
        "spades.py", "--meta",
        "-1", os.path.join(output, "3.bowtie2", sample, f"{sample1}.fastq"),
        "-2", os.path.join(output, "3.bowtie2", sample, f"{sample2}.fastq"),
        "-t", str(threads), "-o", spades_dir
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"SPAdes failed: {e}")


def run_vsearch_1(output, sample, threads):
    filter_dir = os.path.join(output, "5.filter", sample)
    os.makedirs(filter_dir, exist_ok=True)

    try:
        subprocess.run(["pigz", "-p", str(threads), "-f",
                        os.path.join(output, "3.bowtie2", sample, "*.fastq")],
                       check=True)

        cmd = [
            "vsearch", "--sortbylength",
            os.path.join(output, "4.spades", sample, "scaffolds.fasta"),
            "--minseqlength", "1000", "--maxseqlength", "-1",
            "--relabel", f"s{sample}.contig",
            "--output", os.path.join(filter_dir, "contig_1k.fasta")
        ]
        subprocess.run(cmd, check=True)
        shutil.rmtree(os.path.join(output, "4.spades", sample))
    except subprocess.CalledProcessError as e:
        sys.exit(f"VSearch error: {e}")


def run_virsorter(output, threads, sample, db):
    print("Running VirSorter")
    os.path.join(db, "virsorter2")
    input_fasta = os.path.join(output, "5.filter", sample, "contig_1k.fasta")
    virsorter_dir = os.path.join(output, "6.vircontigs", sample)

    try:
        # First pass
        cmd = (
            f"module unload anaconda && "
            f"source activate virsorter2 && "
            f"virsorter run -w {virsorter_dir}/vs2-pass1 "
            f"-i {input_fasta} -j {threads} --min-length 3000 "
            f"--min-score 0.5 --keep-original-seq all"
        )
        subprocess.run(cmd, shell=True, check=True)

        # CheckV
        checkv_dir = os.path.join(virsorter_dir, "checkv")
        cmd = [
            "checkv", "end_to_end",
            os.path.join(virsorter_dir, "vs2-pass1/final-viral-combined.fa"),
            checkv_dir, "-t", str(threads), "-d", f"{db}/checkvdb/checkv-db-v1.0 "
        ]
        subprocess.run(cmd, check=True)

        # Combine outputs
        with open(os.path.join(checkv_dir, "combined.fna"), "w") as out:
            for f in ["proviruses.fna", "viruses.fna"]:
                with open(os.path.join(checkv_dir, f)) as infile:
                    out.write(infile.read())

        # Second pass
        cmd = (
            f"source activate virsorter-env && "
            f"virsorter run -w {virsorter_dir} "
            f"-i {checkv_dir}/combined.fna --prep-for-dramv "
            f"--min-length 5000 --min-score 0.5 all"
        )
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"VirSorter error: {e}")


def run_blastn(output, threads, sample, db):  # 添加db参数
    db_path = os.path.join(db, "blastn_database")  # 使用参数传递的db路径
    input_fasta = os.path.join(output, "5.filter", sample, "contig_1k.fasta")
    blast_dir = os.path.join(output, "7.blastncontigs", sample)
    os.makedirs(blast_dir, exist_ok=True)

    databases = [
        ("crass", "crass.out"),
        ("gpd", "gpd.out"),
        ("gvd", "gvd.out"),
        ("mgv", "mgv.out"),
        ("ncbi", "ncbi.out")
    ]

    for db_name, out_file in databases:
        db_file = os.path.join(db_path, db_name)
        if not os.path.exists(db_file + ".nhr"):  # 检查数据库是否存在
            sys.exit(f"BLAST database {db_file} not found")

        cmd = [
            "blastn", "-query", input_fasta,
            "-db", db_file,
            "-num_threads", str(threads), "-max_target_seqs", "1",
            "-outfmt", "6", "-out", os.path.join(blast_dir, out_file)
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(f"BLASTn failed for {db_name}: {e}")


def run_combination(output, sample):
    print("Combine virsorter and blastn results")
    final_dir = os.path.join(output, "8.final-contigs", sample)
    if os.path.exists(final_dir):
        shutil.rmtree(final_dir)
    os.makedirs(final_dir, exist_ok=True)
    ret = filter_vircontig(output, sample)
    if ret != 0:
        sys.exit("Error: combine error")


def run_checkv(output, threads, sample, db):
    checkv_dir = os.path.join(output, "9.checkv", sample)
    input_fasta = os.path.join(output, "8.final-contigs", sample, "contigs.fa")

    if os.path.exists(checkv_dir):
        shutil.rmtree(checkv_dir)
    os.makedirs(checkv_dir, exist_ok=True)

    cmd = [
        "checkv", "end_to_end",
        input_fasta,
        checkv_dir,
        "-t", str(threads),
        "-d", os.path.join(db, "checkvdb/checkv-db-v1.0")
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        sys.exit(f"CheckV error: {e}")


def high_quality_output(output, sample):
    """生成高质量输出"""
    print("Generating high-quality output")
    hq_dir = os.path.join(output, "11.high_quality", sample)
    try:
        # 清理并创建目录
        if os.path.exists(hq_dir):
            shutil.rmtree(hq_dir)
        os.makedirs(hq_dir, exist_ok=True)

        # 调用过滤函数（假设已实现）
        ret = filter_checkv(output, sample)
        if ret != 0:
            raise RuntimeError("filter_checkv returned non-zero status")
    except Exception as e:
        sys.exit(f"High-quality output error: {e}")


def run_vsearch_2(output, threads, sample):
    print("Run vsearch (cluster)")
    # if os.path.exists(f"{output}/12.final_non_dup/{sample}") is True:
    #     subprocess.call([f"rm -rf {output}/12.final_non_dup/{sample}"], shell=True)
    # subprocess.call([f"mkdir -p {output}/12.final_non_dup/{sample}"], shell=True)
    # print(
    #     f"vsearch --cluster_fast {output}/11.high_quality/{sample}/contigs.fa --id 0.995 --centroids {output}/12.final_non_dup/{sample}/final.fasta --uc {output}/11.high_quality/{sample}/clusters.uc --maxseqlength -1 --threads {threads}")
    # ret = subprocess.call([
    #     f"vsearch --cluster_fast {output}/11.high_quality/{sample}/contigs.fa --id 0.995 --centroids {output}/12.final_non_dup/{sample}/final.fasta --uc {output}/11.high_quality/{sample}/clusters.uc --maxseqlength -1 --threads {threads}"],
    #     shell=True)
    # if ret != 0:
    #     sys.exit("Error: vsearch error")
    # final_info(output, sample)
