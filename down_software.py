import subprocess
import os
import sys


def run_phabox2(contigs, output, threads, db, sample):
    print("Run phabox2")
    if os.path.exists(f"{output}/13.phabox2/{sample}") is True:
        subprocess.call([f"rm -rf {output}/13.phabox2/{sample}"], shell=True)
    subprocess.call([f"mkdir -p {output}/13.phabox2/{sample}"], shell=True)
    print(f"phabox2 --task end_to_end --dbdir {db}/phabox/phabox_db_v2 --skip Y \
        --outpth  {output}/13.phabox2/{sample} \
        --contigs {sample} \
        --threads {threads}")

    ret = subprocess.call([f"phabox2 --task end_to_end --dbdir {db}/phabox/phabox_db_v2 --skip Y \
         --outpth  {output}/13.phabox2/{sample} \
         --contigs {contigs} \
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
def run_salmon(output, threads, sample):
    print("Run salmon")
    if os.path.exists(f"{output}/17.salmon/{sample}") is True:
        subprocess.call([f"rm -rf {output}/17.salmon/{sample}"], shell=True)
    subprocess.call([f"mkdir -p {output}/17.salmon/{sample}"], shell=True)
    cmd = [f"salmon quant -i {output}/15.prodigal/index -l A  -1 {output}/3.bowtie2/{sample}/{sample}_1.fastq.gz \
        -2 {output}/3.bowtie2/{sample}/{sample}_2.fastq.gz -o {output}/17.salmon/{sample}/{sample}.quant --meta -p {threads}"
           ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: run_salmon error")


def run_coverm(output, threads, sample):
    print("Run coverm")
    if os.path.exists(f"{output}/18.coverm/{sample}") is True:
        subprocess.call([f"rm -rf {output}/18.coverm/{sample}"], shell=True)
    subprocess.call([f"mkdir -p {output}/18.coverm/{sample}"], shell=True)
    cmd = [
        "coverm contig",
        "---coupled",
        f"{output}/3.bowtie2/{sample}/{sample}_1.fastq.gz {output}/3.bowtie2/{sample}/{sample}_2.fastq.gz",
        "--reference", f"{output}/13.cd-hit/cdhit.fasta",
        "-t", threads,
        "-o", f"{output}/18.coverm/{sample}/{sample}.coverm",
    ]
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        sys.exit("Error: run_salmon error")

# salmon quant -i index -l A -1 ../3.bowtie2/TXAS01/TXAS01_1.fastq.gz \
#         -2 ../3.bowtie2/TXAS01/TXAS01_2.fastq.gz -o ../17.salmon/TXAS01/TXAS01.quant --meta  -p 32"
#
# coverm contig -1 ../3.bowtie2/TXAS01/TXAS01_1.fastq.gz  -2 ../3.bowtie2/TXAS01/TXAS01_2.fastq.gz \
# --reference nucleotide.fa --methods count  --output-file ERR1201173_coverm_tpm.tsv --no-zeros
