import csv
import subprocess
import sys
import os
import shutil
import configparser


def get_software_paths(config_file="config.ini"):
    """读取配置文件中的软件路径"""
    config = configparser.ConfigParser()
    config.read(config_file)
    return {
        'fastp': config.get('software', 'fastp', fallback='fastp'),
        'bowtie2': config.get('software', 'bowtie2', fallback='bowtie2'),
        'megahit': config.get('software', 'megahit', fallback='megahit')
    }


def run_fastp(**context):
    """质控与修剪原始数据"""
    fastp_path = get_software_paths()['fastp']
    trim_dir = context['paths']["trimmed"]
    os.makedirs(trim_dir, exist_ok=True)
    params = "-l 90 -q 20 -u 30 -y --trim_poly_g"
    cmd = (
        f"{fastp_path} --in1 {context['input1']} --in2 {context['input2']} "
        f"--out1 {trim_dir}/{context['sample1']}.fq.gz "
        f"--out2 {trim_dir}/{context['sample2']}.fq.gz "
        f"{params} --thread {context['threads']} "
        f"--html {trim_dir}/{context['sample']}report.html "
        f"--json {trim_dir}/report.json"
    )
    print(f"[fastp] Running: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("ERROR: fastp failed!")


def run_host_removal(**context):
    """宿主去除"""
    output = context['output']
    threads = context['threads']
    sample1 = context['sample1']
    sample2 = context['sample2']
    host_list = context['host_list']
    db = context['db']
    sample = context['sample']
    paths = context['paths']
    if not host_list:
        print("[host_removal] Skipping: No host index provided.")
        return
    bowtie2_path = get_software_paths()['bowtie2']
    index_paths = [os.path.join(db, "bowtie2_index", na, na) for na in host_list]
    bowtie2_dir = paths["host_removed"]
    sample_dir = os.path.join(bowtie2_dir, sample)
    trim_dir = paths["trimmed"]
    if os.path.exists(sample_dir):
        try:
            shutil.rmtree(sample_dir)
        except Exception as e:
            print(f"[host_removal] Warning: Failed to remove {sample_dir}: {e}")
    os.makedirs(sample_dir, exist_ok=True)
    for fq in [sample1, sample2]:
        shutil.copy(os.path.join(trim_dir, f"{fq}.fq.gz"), os.path.join(sample_dir, f"{fq}.fq.gz"))
    for index in index_paths:
        input1 = os.path.join(sample_dir, f"{sample1}.fq.gz")
        input2 = os.path.join(sample_dir, f"{sample2}.fq.gz")
        tmp_prefix = os.path.join(sample_dir, "tmp")
        sam_output = os.path.join(sample_dir, "tmp.sam")
        cmd = [
            bowtie2_path, "-p", str(threads),
            "-x", index,
            "-1", input1, "-2", input2,
            "--un-conc", tmp_prefix,
            "-S", sam_output
        ]
        print(f"[host_removal] Running: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
            shutil.move(f"{tmp_prefix}.1", os.path.join(sample_dir, f"{sample1}.fastq"))
            shutil.move(f"{tmp_prefix}.2", os.path.join(sample_dir, f"{sample2}.fastq"))
        except Exception as e:
            sys.exit(f"ERROR: bowtie2 failed: {e}")
    # 清理临时文件，使用 paths 里的绝对路径
    for path in [
        os.path.join(paths["trimmed"], f"{sample}*"),
        os.path.join(paths["host_removed"], sample, "tmp.sam")
    ]:
        try:
            subprocess.run(["rm", "-rf", path], check=False)
        except Exception as e:
            print(f"[host_removal] Warning: Failed to remove {path}: {e}")


def run_assembly(**context):
    """组装"""
    megahit_path = get_software_paths()['megahit']
    assembly_dir_tmp = os.path.join(context['paths']["assembly"])
    assembly_dir = os.path.join(context['paths']["assembly"], context['sample'])
    if os.path.exists(assembly_dir):
        try:
            shutil.rmtree(assembly_dir)
        except Exception as e:
            print(f"[assembly] Warning: Failed to remove {assembly_dir}: {e}")
    os.makedirs(assembly_dir_tmp, exist_ok=True)
    k_list = "21,29,39,59,79,99,119"
    cmd = (
        f"{megahit_path} -1 {context['paths']['host_removed']}/{context['sample']}/{context['sample1']}.fastq "
        f"-2 {context['paths']['host_removed']}/{context['sample']}/{context['sample2']}.fastq "
        f"-o {assembly_dir} --k-list {k_list} "
        f"--num-cpu-threads {context['threads']} --min-contig-len 1000 --memory 0.5"
    )
    print(f"[assembly] Running: {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: MEGAHIT failed: {e}")


def run_busco_filter(**context):
    """BUSCO 过滤细菌污染"""
    print("[busco_filter] Running BUSCO filter...")
    output = context['output']
    sample = context['sample']
    db = context['db']
    threads = context['threads']
    paths = context['paths']
    
    abs_busco_dir = os.path.join(paths["busco_filter"], sample)  # 绝对路径
    busco_dir = os.path.relpath(abs_busco_dir, start=os.getcwd())  # 相对路径用于 BUSCO
    input_fasta = os.path.join(paths["high_quality"], sample, "contigs.fa")
    
    # 清理并创建目录（用绝对路径）
    if os.path.exists(abs_busco_dir):
        try:
            shutil.rmtree(abs_busco_dir)
        except Exception as e:
            print(f"[busco_filter] Warning: Failed to remove {abs_busco_dir}: {e}")
    os.makedirs(abs_busco_dir, exist_ok=True)

    # Step 1: 使用BUSCO（用相对路径）
    cmd = f"""
    source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/busco &&
    busco -f -i {input_fasta} -c {threads} -o {busco_dir} -m geno -l {db}/bacteria_odb12 --offline
     """
    print(f"[busco_filter] Running: {cmd}")
    s1 = subprocess.call(cmd, shell=True)
    if s1 != 0:
        sys.exit(f"ERROR: busco filter failed: {s1}")
    
    # Step 2: 解析基因预测结果统计总基因数（用绝对路径）
    predicted_file = os.path.join(abs_busco_dir, r"prodigal_output/predicted_genes/predicted.fna")
    # Count genes per contig
    predicted_counts = {}
    with open(predicted_file, 'r') as pf:
        for line in pf:
            if line.startswith('>'):
                header = line[1:].split()[0]
                contig = '_'.join(header.split('_')[:-1])  # contig = part before first underscore
                predicted_counts[contig] = predicted_counts.get(contig, 0) + 1
    if not predicted_counts:
        sys.exit("ERROR: No predicted genes found in predicted.fna.")
    print(f"Total contigs with predicted genes: {len(predicted_counts)}")
    total_genes = sum(predicted_counts.values())
    print(f"Total predicted genes: {total_genes}")
    
    full_table = os.path.join(abs_busco_dir, r"run_bacteria_odb12/full_table.tsv")
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
    
    input_fasta = os.path.join(paths["high_quality"], sample, "contigs.fa")
    output_fasta = os.path.join(abs_busco_dir, "filtered_contigs.fa")
    
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
    