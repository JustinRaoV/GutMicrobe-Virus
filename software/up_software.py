import csv
import shutil
import subprocess
import os
import sys
import pandas as pd
from software.tools import *


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
    if os.path.exists(filter_dir):
        shutil.rmtree(filter_dir)  # 修复：使用shutil.rmtree删除非空目录
    os.makedirs(filter_dir, exist_ok=True)

    try:
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
    if os.path.exists(virsorter_dir):
        shutil.rmtree(virsorter_dir)  # 修复：使用shutil.rmtree删除非空目录
    os.makedirs(virsorter_dir, exist_ok=True)
    try:
        # First pass
        cmd = (
            f"module unload CentOS/7.9/Anaconda3/24.5.0 && "
            f"source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/viroprofiler-virsorter2 && "
            f"virsorter run -w {virsorter_dir}/vs2-pass1 "
            f"-i {input_fasta} -j {threads} --min-length 3000 --include-groups dsDNAphage,NCLDV,RNA,ssDNA,lavidaviridae  "
            f"--min-score 0.5 --keep-original-seq all"
        )
        s1 = subprocess.call(cmd, shell=True)
        if s1 != 0:
            sys.exit("VirSorter failed")
        # CheckV
        checkv_dir = os.path.join(virsorter_dir, "checkv")
        if os.path.exists(checkv_dir):
            shutil.rmtree(checkv_dir)  # 修复：使用shutil.rmtree删除非空目录
        os.makedirs(checkv_dir, exist_ok=True)
        cmd = f"""
        checkv end_to_end {os.path.join(virsorter_dir, "vs2-pass1/final-viral-combined.fa")} {checkv_dir} \
            -d {os.path.join(db, 'checkvdb/checkv-db-v1.0')} \
            -t {threads}
        """

        s2 = subprocess.call(cmd, shell=True)
        if s2 != 0:
            sys.exit("checkv failed")

        # Combine outputs
        with open(os.path.join(checkv_dir, "combined.fna"), "w") as out:
            for f in ["proviruses.fna", "viruses.fna"]:
                with open(os.path.join(checkv_dir, f)) as infile:
                    out.write(infile.read())

        # Second pass
        cmd = (
            f"module unload CentOS/7.9/Anaconda3/24.5.0 && source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/viroprofiler-virsorter2 && "
            f"virsorter run -w {virsorter_dir} "
            f"-i {checkv_dir}/combined.fna --prep-for-dramv "
            f"--min-length 3000 --min-score 0.5 all"
        )
        s3 = subprocess.call(cmd, shell=True)
        if s3 != 0:
            sys.exit("Error: virsorter2 error")
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
            "-outfmt",
            "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames ",
            "-out", os.path.join(blast_dir, out_file)
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
    hq_dir = os.path.join(output, "10.high_quality", sample)
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


def run_busco_filter(output, sample, db, threads):
    busco_dir = os.path.join(output, "11.busco_filter", sample, "contigs.fa")
    input_fasta = os.path.join(output, "10.high_quality", sample, "contigs.fa")
    # 清理并创建目录
    if os.path.exists(busco_dir):
        shutil.rmtree(busco_dir)
    os.makedirs(busco_dir, exist_ok=True)

    # Step 1: 使用BUSCO
    cmd = f"""
    source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/busco &&
     busco -f -i {input_fasta} -c {threads} -o {busco_dir} -m geno -l {db}/bacteria_odb12 --offline
     """
    s1 = subprocess.call(cmd, shell=True)
    if s1 != 0:
        sys.exit(f"busco filter failed: {s1}")
    # Step 2: 解析基因预测结果统计总基因数
    predicted_file = os.path.join(busco_dir, r"prodigal_output/predicted_genes/predicted.fna")
    # Count genes per contig
    predicted_counts = {}
    with open(predicted_file, 'r') as pf:
        for line in pf:
            if line.startswith('>'):
                header = line[1:].split()[0]
                contig = '_'.join(header.split('_')[:-1])  # contig = part before first underscore
                predicted_counts[contig] = predicted_counts.get(contig, 0) + 1
    if not predicted_counts:
        sys.exit("Error: No predicted genes found in predicted.fna.")
    print(f"Total contigs with predicted genes: {len(predicted_counts)}")
    total_genes = sum(predicted_counts.values())
    print(f"Total predicted genes: {total_genes}")
    full_table = os.path.join(busco_dir, r"run_bacteria_odb12/full_table.tsv")
    busco_counts = {}
    with open(full_table, 'r') as ft:
        reader = csv.reader(ft, delimiter='\t')
        headers = next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            status = row[1].strip()
            if status in ("Complete", "Fragmented"):
                seq_field = row[2]
                # If sequence field includes "file:contig:start-end", extract contig
                if ':' in seq_field:
                    parts = seq_field.split(':')
                    contig_name = parts[-2] if len(parts) >= 2 else parts[0]
                else:
                    contig_name = seq_field
                contig_name = contig_name.split()[0]
                busco_counts[contig_name] = busco_counts.get(contig_name, 0) + 1

    total_busco_hits = sum(busco_counts.values()) if busco_counts else 0
    print(f"Total BUSCO genes (Complete/Frag): {total_busco_hits}")
    print(f"Contigs with BUSCO hits: {len(busco_counts)}")
    contigs_to_remove = []
    for contig, gene_count in predicted_counts.items():
        if gene_count == 0:
            continue
        busco_genes = busco_counts.get(contig, 0)
        ratio = busco_genes / gene_count
        print(f"Contig {contig}: {busco_genes}/{gene_count} BUSCO genes (ratio {ratio:.2%})")
        if ratio > 0.05:
            contigs_to_remove.append(contig)
    if contigs_to_remove:
        print(f"Removing {len(contigs_to_remove)} contigs with BUSCO ratio > 5%: {contigs_to_remove}")
    else:
        print("No contigs exceed BUSCO ratio threshold (5%).")
    input_fasta = os.path.join(output, "8.filter", sample, "filtered_contigs.fa")
    output_fasta = os.path.join(busco_dir, "filtered_contigs.fa")
    # Read input FASTA sequences
    contig_seqs = {}
    with open(input_fasta, 'r') as f:
        header = None
        seq_lines = []
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if header:
                    contig_seqs[header] = ''.join(seq_lines)
                header = line[1:].split()[0]
                seq_lines = []
            else:
                seq_lines.append(line)
        if header:
            contig_seqs[header] = ''.join(seq_lines)

    # Write filtered sequences
    with open(output_fasta, 'w') as out:
        for hdr, seq in contig_seqs.items():
            if hdr not in contigs_to_remove:
                out.write(f">{hdr}\n{seq}\n")

    print(f"Filtered contigs saved to: {output_fasta}")
