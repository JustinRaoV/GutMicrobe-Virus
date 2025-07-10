import csv
import subprocess
import sys
import os
import shutil
from core.config_manager import get_config


def run_fastp(**context):
    """质控与修剪原始数据"""
    logger = context.get('logger')
    executor = context.get('executor')
    
    config = get_config()
    fastp_path = config['software']['fastp']
    fastp_params = config['parameters']['fastp_params']
    trim_dir = context['paths']["trimmed"]
    
    # 使用文件管理器创建目录
    if executor:
        executor.file_manager.ensure_dir(trim_dir)
    else:
        os.makedirs(trim_dir, exist_ok=True)
    
    # 使用主环境运行fastp
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{fastp_path} --in1 {context['input1']} --in2 {context['input2']} "
        f"--out1 {trim_dir}/{context['sample1']}.fq.gz "
        f"--out2 {trim_dir}/{context['sample2']}.fq.gz "
        f"{fastp_params} --thread {context['threads']} "
        f"--html {trim_dir}/{context['sample']}report.html "
        f"--json {trim_dir}/report.json"
    )
    
    if logger:
        logger.info(f"执行fastp命令: {cmd}")
    
    # 使用执行器运行命令
    if executor:
        executor.command_executor.run_shell_command(cmd)
    else:
        ret = subprocess.call(cmd, shell=True)
        if ret != 0:
            sys.exit("ERROR: fastp failed!")


def run_host_removal(**context):
    """去宿主"""
    config = get_config()
    bowtie2_path = config['software']['bowtie2']
    sample = context['sample']
    sample1 = context['sample1']
    sample2 = context['sample2']
    threads = context['threads']
    host_list = context['host_list']
    paths = context['paths']
    
    if not host_list:
        print("[host_removal] No host genome specified, skipping host removal")
        # 直接复制文件
        sample_dir = os.path.join(paths["host_removed"], sample)
        os.makedirs(sample_dir, exist_ok=True)
        for fq in [sample1, sample2]:
            src = os.path.join(paths["trimmed"], f"{fq}.fq.gz")
            dst = os.path.join(sample_dir, f"{fq}.fq.gz")
            if os.path.exists(src):
                shutil.copy2(src, dst)
        return
    
    sample_dir = os.path.join(paths["host_removed"], sample)
    os.makedirs(sample_dir, exist_ok=True)
    
    # 构建索引路径列表
    index_paths = []
    for host in host_list:
        index_path = os.path.join(context['db'], f"bowtie2_index/{host}")
        if os.path.exists(f"{index_path}.1.bt2"):
            index_paths.append(index_path)
        else:
            print(f"[host_removal] Warning: Bowtie2 index not found for {host}")
    
    if not index_paths:
        print("[host_removal] No valid host indices found, skipping host removal")
        # 直接复制文件
        for fq in [sample1, sample2]:
            src = os.path.join(paths["trimmed"], f"{fq}.fq.gz")
            dst = os.path.join(sample_dir, f"{fq}.fq.gz")
            if os.path.exists(src):
                shutil.copy2(src, dst)
        return

    for index in index_paths:
        input1 = os.path.join(sample_dir, f"{sample1}.fq.gz")
        input2 = os.path.join(sample_dir, f"{sample2}.fq.gz")
        tmp_prefix = os.path.join(sample_dir, "tmp")
        sam_output = os.path.join(sample_dir, "tmp.sam")
        
        # 使用主环境运行bowtie2
        cmd = (
            f"{config['environment']['main_conda_activate']} && "
            f"{bowtie2_path} -p {threads} -x {index} "
            f"-1 {input1} -2 {input2} --un-conc {tmp_prefix} -S {sam_output}"
        )
        print(f"[host_removal] Running: {cmd}")
        try:
            subprocess.run(cmd, shell=True, check=True)
            # 使用 pigz 压缩为 .fq.gz 格式
            for i, fq in enumerate([sample1, sample2], 1):
                uncompressed_file = f"{tmp_prefix}.{i}"
                compressed_file = os.path.join(sample_dir, f"{fq}.fq.gz")
                pigz_cmd = f"{config['environment']['main_conda_activate']} && pigz -p {threads} -c {uncompressed_file}"
                print(f"[host_removal] Compressing {fq} with pigz...")
                with open(compressed_file, 'wb') as outfile:
                    subprocess.run(pigz_cmd, shell=True, stdout=outfile, check=True)
                # 删除未压缩的临时文件
                os.remove(uncompressed_file)
        except Exception as e:
            sys.exit(f"ERROR: bowtie2 or pigz failed: {e}")
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
    config = get_config()
    megahit_path = config['software']['megahit']
    megahit_params = config['parameters']['megahit_params']
    assembly_dir_tmp = os.path.join(context['paths']["assembly"])
    assembly_dir = os.path.join(context['paths']["assembly"], context['sample'])
    if os.path.exists(assembly_dir):
        try:
            shutil.rmtree(assembly_dir)
        except Exception as e:
            print(f"[assembly] Warning: Failed to remove {assembly_dir}: {e}")
    os.makedirs(assembly_dir_tmp, exist_ok=True)
    
    # 使用主环境运行megahit
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{megahit_path} -1 {context['paths']['host_removed']}/{context['sample']}/{context['sample1']}.fq.gz "
        f"-2 {context['paths']['host_removed']}/{context['sample']}/{context['sample2']}.fq.gz "
        f"-o {assembly_dir} {megahit_params} "
        f"--num-cpu-threads {context['threads']}"
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
    db_root = context['db']
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
    config = get_config()
    env = config['environment']
    busco_module_unload = env.get('busco_module_unload', '')
    busco_conda_activate = env.get('busco_conda_activate', '')
    # 优先用config.ini里的busco_database，否则用--db拼接默认子路径
    if config.has_section('database') and config['database'].get('busco_database'):
        busco_db = config['database']['busco_database']
    else:
        busco_db = os.path.join(db_root, "bacteria_odb12")
    cmd = f"""
    {busco_module_unload} &&
    {busco_conda_activate} &&
    busco -f -i {input_fasta} -c {threads} -o {busco_dir} -m geno -l {busco_db} --offline
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
    