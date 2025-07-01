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
    index_paths = [os.path.join(db, "bowtie2db", na, na) for na in host_list]
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
    assembly_dir = os.path.join(context['paths']["assembly"], context['sample'])
    if os.path.exists(assembly_dir):
        try:
            shutil.rmtree(assembly_dir)
        except Exception as e:
            print(f"[assembly] Warning: Failed to remove {assembly_dir}: {e}")
    k_list = "21,29,39,59,79,99,119"
    cmd = (
        f"{megahit_path} -1 {context['output']}/2.bowtie2/{context['sample']}/{context['sample1']}.fastq "
        f"-2 {context['output']}/2.bowtie2/{context['sample']}/{context['sample2']}.fastq "
        f"-o {assembly_dir} --k-list {k_list} "
        f"--num-cpu-threads {context['threads']} --min-contig-len 1000"
    )
    print(f"[assembly] Running: {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: MEGAHIT failed: {e}")
