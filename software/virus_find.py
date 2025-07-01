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
        'vsearch': config.get('software', 'vsearch', fallback='vsearch'),
        'virsorter': config.get('software', 'virsorter', fallback='virsorter'),
        'checkv': config.get('software', 'checkv', fallback='checkv')
    }


def run_vsearch_1(**context):
    """VSEARCH 过滤和排序"""
    vsearch_path = get_software_paths()['vsearch']
    filter_dir = os.path.join(context['paths']["vsearch"], context['sample'])
    assembly_dir = os.path.join(context['paths']["assembly"], context['sample'])
    if os.path.exists(filter_dir):
        try:
            shutil.rmtree(filter_dir)
        except Exception as e:
            print(f"[vsearch] Warning: Failed to remove {filter_dir}: {e}")
    os.makedirs(filter_dir, exist_ok=True)
    try:
        cmd = [
            vsearch_path, "--sortbylength",
            os.path.join(assembly_dir, "final.contigs.fa"),
            "--minseqlength", "500", "--maxseqlength", "-1",
            "--relabel", f"s{context['sample']}.contig",
            "--output", os.path.join(filter_dir, "contig_1k.fasta")
        ]
        print(f"[vsearch] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        try:
            shutil.rmtree(assembly_dir)
        except Exception as e:
            print(f"[vsearch] Warning: Failed to remove {assembly_dir}: {e}")
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: VSearch failed: {e}")


def run_virsorter(**context):
    """VirSorter 病毒识别"""
    print("[virsorter] Running VirSorter...")
    db = context['db']
    input_fasta = os.path.join(context['paths']["vsearch"], context['sample'], "contig_1k.fasta")
    virsorter_dir = os.path.join(context['paths']["virsorter"], context['sample'])
    if os.path.exists(virsorter_dir):
        try:
            shutil.rmtree(virsorter_dir)
        except Exception as e:
            print(f"[virsorter] Warning: Failed to remove {virsorter_dir}: {e}")
    os.makedirs(virsorter_dir, exist_ok=True)
    software = get_software_paths()
    virsorter_path = software['virsorter']
    checkv_path = software['checkv']
    try:
        cmd1 = (
            f"{virsorter_path} run --prep-for-dramv -w {virsorter_dir}/vs2-pass1 "
            f"-i {input_fasta} -j {context['threads']} --min-length 3000 --include-groups dsDNAphage,NCLDV,RNA,ssDNA,lavidaviridae  "
            f"--min-score 0.5 --keep-original-seq all")
        print(f"[virsorter] Running: {cmd1}")
        s1 = subprocess.call(cmd1, shell=True)
        if s1 != 0:
            sys.exit(f"ERROR: VirSorter failed {s1}")
        checkv_dir = os.path.join(virsorter_dir, "checkv")
        if os.path.exists(checkv_dir):
            try:
                shutil.rmtree(checkv_dir)
            except Exception as e:
                print(f"[virsorter] Warning: Failed to remove {checkv_dir}: {e}")
        os.makedirs(checkv_dir, exist_ok=True)
        cmd2 = (
            f"{checkv_path} end_to_end {os.path.join(virsorter_dir, 'vs2-pass1/final-viral-combined.fa')} {checkv_dir} "
            f"-d {os.path.join(db, 'checkv-db-v1.5')} -t {context['threads']}"
        )
        print(f"[virsorter] Running: {cmd2}")
        s2 = subprocess.call(cmd2, shell=True)
        if s2 != 0:
            sys.exit("ERROR: checkv failed")
        with open(os.path.join(checkv_dir, "combined.fna"), "w") as out:
            for f in ["proviruses.fna", "viruses.fna"]:
                with open(os.path.join(checkv_dir, f)) as infile:
                    out.write(infile.read())
        cmd3 = (
            f"{virsorter_path}  run -w {virsorter_dir} "
            f"-i {checkv_dir}/combined.fna --prep-for-dramv "
            f"--min-length 3000 --min-score 0.5 all"
        )
        print(f"[virsorter] Running: {cmd3}")
        s3 = subprocess.call(cmd3, shell=True)
        if s3 != 0:
            sys.exit("ERROR: virsorter2 error")
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: VirSorter error: {e}")


def run_blastn(**context):
    """BLASTN 比对"""
    print("[blastn] Running blastn...")
    db = "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db"
    blastn_dir = os.path.join(context['paths']["blastn"], context['sample'])
    if os.path.exists(blastn_dir):
        try:
            subprocess.call([f"rm -rf {blastn_dir}"], shell=True)
        except Exception as e:
            print(f"[blastn] Warning: Failed to remove {blastn_dir}: {e}")
    subprocess.call([f"mkdir -p {blastn_dir}"], shell=True)
    for dbname in ["crass", "gpd", "gvd", "mgv", "ncbi"]:
        out_path = f"{blastn_dir}/{dbname}.out"
        cmd = (
            f'blastn -query {context["paths"]["vsearch"]}/{context["sample"]}/contig_1k.fasta '
            f'-db {db}/blastn_database/{dbname} -num_threads {context["threads"]} -max_target_seqs 1 '
            f'-outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " '
            f'-out {out_path}'
        )
        print(f"[blastn] Running: {cmd}")
        ret = subprocess.call([cmd], shell=True)
        if ret != 0:
            sys.exit("ERROR: blastn error")


def run_combination(**context):
    """合并病毒识别和比对结果"""
    print("[combination] Combine virsorter and blastn results")
    final_dir = os.path.join(context['paths']["combination"], context['sample'])
    if os.path.exists(final_dir):
        try:
            subprocess.call([f"rm -rf {final_dir}"], shell=True)
        except Exception as e:
            print(f"[combination] Warning: Failed to remove {final_dir}: {e}")
    subprocess.call([f"mkdir -p {final_dir}"], shell=True)
    # 这里建议后续将 filter_vircontig 也改为 **context
    ret = filter_vircontig(context['output'], context['sample'], context['paths'])
    if ret != 0:
        sys.exit("ERROR: combine error")


def run_checkv(**context):
    """CheckV 质量评估"""
    print("[checkv] Running checkv...")
    checkv_dir = os.path.join(context['paths']["checkv"], context['sample'])
    db = context['db']
    if os.path.exists(checkv_dir):
        try:
            subprocess.call([f"rm -rf {checkv_dir}"], shell=True)
        except Exception as e:
            print(f"[checkv] Warning: Failed to remove {checkv_dir}: {e}")
    subprocess.call([f"mkdir -p {checkv_dir}"], shell=True)
    cmd = (
        f"checkv end_to_end {context['paths']['combination']}/{context['sample']}/contigs.fa {checkv_dir} "
        f"-d {db}/checkvdb/checkv-db-v1.0 -t {context['threads']}"
    )
    print(f"[checkv] Running: {cmd}")
    ret = subprocess.call([cmd], shell=True)
    if ret != 0:
        sys.exit("ERROR: checkv error")


def high_quality_output(**context):
    """提取高质量病毒结果"""
    print("[high_quality] Get final output")
    highq_dir = os.path.join(context['paths']["high_quality"], context['sample'])
    if os.path.exists(highq_dir):
        try:
            subprocess.call([f"rm -rf {highq_dir}"], shell=True)
        except Exception as e:
            print(f"[high_quality] Warning: Failed to remove {highq_dir}: {e}")
    subprocess.call([f"mkdir -p {highq_dir}"], shell=True)
    filter_checkv(context['output'], context['sample'], context['paths'])


def run_vsearch_2(output, threads, sample):
    print("Run vsearch (cluster)")
    if os.path.exists(f"{output}/12.final_non_dup/{sample}") is True:
        subprocess.call([f"rm -rf {output}/12.final_non_dup/{sample}"], shell=True)
    subprocess.call([f"mkdir -p {output}/12.final_non_dup/{sample}"], shell=True)
    print(
        f"vsearch --cluster_fast {output}/11.high_quality/{sample}/contigs.fa --id 0.995 --centroids {output}/12.final_non_dup/{sample}/final.fasta --uc {output}/11.high_quality/{sample}/clusters.uc --maxseqlength -1 --threads {threads}")
    ret = subprocess.call([
        f"vsearch --cluster_fast {output}/11.high_quality/{sample}/contigs.fa --id 0.995 --centroids {output}/12.final_non_dup/{sample}/final.fasta --uc {output}/11.high_quality/{sample}/clusters.uc --maxseqlength -1 --threads {threads}"],
        shell=True)
    if ret != 0:
        sys.exit("Error: vsearch error")
    final_info(output, sample)