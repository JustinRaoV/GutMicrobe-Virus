import os
import subprocess
import sys


def run_cdhit(output, threads, c=0.95, aS=0.9):
    print("Run cd-hit")
    if os.path.exists(f"{output}/13.cd-hit") is True:
        subprocess.call([f"rm -rf {output}/13.cd-hit"], shell=True)
    subprocess.call([f"mkdir -p {output}/13.cd-hit"], shell=True)
    print(f"cat {output}/12.final_non_dup/*.fasta > {output}/13.cd-hit/all.fasta")
    ret = subprocess.call([f"cat {output}/12.final_non_dup/*.fasta > {output}/13.cd-hit/all.fasta"], shell=True)
    if ret != 0:
        print("Warning: cat error")

    cmd = [
        f"/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/software/cd-hit-v4.8.1/cd-hit-est \
        -i {output}/13.cd-hit/all.fasta -o {output}/13.cd-hit/cdhit.fasta -c {c} -aS {aS} -T {threads} -M 160000"
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: CD-HIT error")


def run_phabox2(output, threads, db):
    print("Run phabox2")
    if os.path.exists(f"{output}/14.phabox2") is True:
        subprocess.call([f"rm -rf {output}/14.phabox2"], shell=True)
    subprocess.call([f"mkdir -p {output}/14.phabox2/"], shell=True)
    print(f"phabox2 --task end_to_end --dbdir {db}/phabox/phabox_db_v2 --skip Y \
            --outpth  {output}/14.phabox2/ \
            --contigs {output}/13.cd-hit/cdhit.fasta \
            --threads {threads}")

    ret = subprocess.call([f"phabox2 --task end_to_end --dbdir {db}/phabox/phabox_db_v2 --skip Y \
            --outpth  {output}/14.phabox2/ \
            --contigs {output}/13.cd-hit/cdhit.fasta \
            --threads {threads}"], shell=True)
    if ret != 0:
        print("Warning: phabox2 error")


def run_prodigal(output, threads):
    print("Run anno")
    if os.path.exists(f"{output}/15.prodigal") is True:
        subprocess.call([f"rm -rf {output}/15.prodigal"], shell=True)

    subprocess.call([f"mkdir {output}/15.prodigal"], shell=True)
    cmd = [
        f"prodigal -i {output}/13.cd-hit/all.fasta -o {output}/15.prodigal/genes.gff -a {output}/15.prodigal/protein.fa -f gff"
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: prodigal error")
    cmd = [
        f"/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/software/cd-hit-v4.8.1/cd-hit -i {output}/15.prodigal/protein.fa \
        -o {output}/15.prodigal/nucleotide.fa -c 0.95 -aS 0.9 -T {threads} -M 160000"
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: cd-hit-est error")


def run_eggnog(output, db):
    print("Run eggnog")
    if os.path.exists(f"{output}/16.eggnog") is True:
        subprocess.call([f"rm -rf {output}/16.eggnog"], shell=True)
    subprocess.call([f"mkdir {output}/16.eggnog"], shell=True)
    cmd = [
        "source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/eggnog &&",
        f"emapper.py -i {output}/15.prodigal/nucleotide.fa --output {output}/16.eggnog/pfam -d pfam --data_dir {db}/eggnog5"
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: eggnog pfam error")

    cmd = [
        "source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/eggnog &&",
        f"emapper.py -i {output}/15.prodigal/nucleotide.fa --output {output}/16.eggnog/VOGdb -d VOGdb --data_dir {db}/eggnog5"
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: eggnog VOGDB error")


