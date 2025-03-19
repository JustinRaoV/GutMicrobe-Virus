import subprocess
import os
import sys


def run_phabox2(sample, output, threads, db, sample_name):
    print("Run phabox2")
    if os.path.exists(f"{output}/13.phabox2/{sample_name}") is True:
        subprocess.call([f"rm -rf {output}/13.phabox2/{sample_name}"], shell=True)
    subprocess.call([f"mkdir -p {output}/13.phabox2/sample_name"], shell=True)
    print(f"phabox2 --task end_to_end --dbdir {db}/phabox/phabox_db_v2 --skip Y \
        --outpth  {output}/13.phabox2/{sample_name} \
        --contigs {sample} \
        --threads {threads}")

    ret = subprocess.call([f"phabox2 --task end_to_end --dbdir {db}/phabox/phabox_db_v2 --skip Y \
         --outpth  {output}/13.phabox2/{sample_name} \
         --contigs {sample} \
         --threads {threads}"], shell=True)
    if ret != 0:
        print("Warning: phabox2 error")


def run_prodigal(output):
    print("Run anno")
    if os.path.exists(f"{output}/14.prodigal") is True:
        subprocess.call([f"rm -rf {output}/14.prodigal"], shell=True)

    subprocess.call([f"mkdir {output}/14.prodigal"], shell=True)
    # Step 1: Merge contigs
    ret = subprocess.call([
        f"cat {output}/11.high_quality/*/contigs.fa > {output}/14.prodigal/merged_contigs.fa", ],
        shell=True)
    if ret != 0:
        sys.exit("Error: merge contigs error")

    # Step 2: Gene prediction with MetaProdigal
    cmd = [
        "prodigal",
        "-i", f"{output}/14.prodigal/merged_contigs.fa",
        "-o", f"{output}/14.prodigal/genes.gff",
        "-a", f"{output}/14.prodigal/protein.fa",
        "-f", "gff"
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: prodigal error")


def run_cdhit(output, c, aS, threads):
    print("Run cdhit")
    if os.path.exists(f"{output}/15.cdhit") is True:
        subprocess.call([f"rm -rf {output}/15.cdhit"], shell=True)
    subprocess.call([f"mkdir {output}/15.cdhit"], shell=True)
    # Step 3: CD-HIT clustering
    cmd = [
        "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/software/cd-hit-v4.8.1/cd-hit",
        "-i", "input_fasta",
        "-o", f"{output}/15.cdhit/genes.fa.cdhit",
        "-c", c,
        "-aS", aS,
        "-T", threads,
        "-M", 160000
    ]

    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: CD-HIT error")


def run_eggnog(output, db):
    print("Run eggnog")
    if os.path.exists(f"{output}/16.eggnog") is True:
        subprocess.call([f"rm -rf {output}/16.eggnog"], shell=True)
    subprocess.call([f"mkdir {output}/16.eggnog"], shell=True)
    cmd = [
        "source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/eggnog &&",
        "emapper.py",
        "-i", f"{output}/15.cdhit/genes.fa.cdhit",
        "--output ", f"{output}/16.eggnog/pfam",
        "-d", "pfam",
        "--data_dir", f"{db}/eggnog5"
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: eggnog pfam error")

    cmd = [
        "source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/eggnog &&",
        "emapper.py",
        "-i", f"{output}/15.cdhit/genes.fa.cdhit",
        "--output ", f"{output}/16.eggnog/VOGdb",
        "-d", "VOGdb",
        "--data_dir", f"{db}/eggnog5"
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: eggnog VOGDB error")

# salmon基因定量 Salmon gene quantification
