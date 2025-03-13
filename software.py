import subprocess
import os
import sys
import pandas as pd
from tools import *


def run_fastqc(output, input1, input2, threads):
    print("Run fastqc")
    if os.path.exists(f"{output}/1.fastqc") is True:
        subprocess.call([f"rm -rf {output}/1.fastqc"], shell=True)
    subprocess.call([f"mkdir {output}/1.fastqc"], shell=True)
    print(f"fastqc {input1} {input2} -t {threads} -o {output}/1.fastqc")
    ret = subprocess.call([f"fastqc {input1} {input2} -t {threads} -o {output}/1.fastqc"], shell=True)
    if ret != 0:
        print("Warning: fastqc error")


# You should adjust trimmomatic settings here
def run_trim(output, threads, input1, input2, sample1, sample2, adapter):
    print("Run trim")
    if os.path.exists(f"{output}/2.trim") is True:
        subprocess.call([f"rm -rf {output}/2.trim"], shell=True)
    subprocess.call([f"mkdir {output}/2.trim"], shell=True)
    print(
        f"trimmomatic PE -threads {threads} -phred33 {input1} {input2} {output}/2.trim/{sample1}.fastq {output}/2.trim/{sample1}_single.fastq {output}/2.trim/{sample2}.fastq {output}/2.trim/{sample2}_single.fastq ILLUMINACLIP:{adapter}:2:30:10 SLIDINGWINDOW:4:20 MINLEN:50")
    ret = subprocess.call([
        f"trimmomatic PE -threads {threads} -phred33 {input1} {input2} {output}/2.trim/{sample1}.fastq {output}/2.trim/{sample1}_single.fastq {output}/2.trim/{sample2}.fastq {output}/2.trim/{sample2}_single.fastq ILLUMINACLIP:{adapter}:2:30:10 SLIDINGWINDOW:4:20 MINLEN:50"],
        shell=True)
    if ret != 0:
        sys.exit("Error: trimmomatic error")


def run_bowtie2(output, threads, sample1, sample2, index_path):
    if len(index_path) == 0:
        print("No need for running bowtie2")
    else:
        print("Run bowtie2")
    if os.path.exists(f"{output}/3.bowtie2") is True:
        subprocess.call([f"rm -rf {output}/3.bowtie2"], shell=True)
    subprocess.call([f"mkdir {output}/3.bowtie2"], shell=True)
    subprocess.call([f"cp {output}/2.trim/{sample1}.fastq {output}/3.bowtie2/{sample1}.fastq"], shell=True)
    subprocess.call([f"cp {output}/2.trim/{sample2}.fastq {output}/3.bowtie2/{sample2}.fastq"], shell=True)
    for na in index_path:
        print(
            f"bowtie2 -p {threads} -x {na} -1 {output}/3.bowtie2/{sample1}.fastq -2 {output}/3.bowtie2/{sample2}.fastq --un-conc {output}/3.bowtie2/tmp > {output}/3.bowtie2/tmp.sam")
        ret = subprocess.call([
            f"bowtie2 -p {threads} -x {na} -1 {output}/3.bowtie2/{sample1}.fastq -2 {output}/3.bowtie2/{sample2}.fastq --un-conc {output}/3.bowtie2/tmp > {output}/3.bowtie2/tmp.sam"],
            shell=True)
        if ret != 0:
            sys.exit("Error: bowtie2 error")
        subprocess.call([f"mv {output}/3.bowtie2/tmp.1 {output}/3.bowtie2/{sample1}.fastq"], shell=True)
        subprocess.call([f"mv {output}/3.bowtie2/tmp.2 {output}/3.bowtie2/{sample2}.fastq"], shell=True)
    if len(index_path) != 0:
        subprocess.call([f"rm {output}/3.bowtie2/tmp.sam"], shell=True)
    subprocess.call([f"rm -rf {output}/2.trim"], shell=True)


def run_viromeQC(output, sample1, sample2):
    print("Run viromeQC")
    if os.path.exists(f"{output}/4.viromeQC") is True:
        subprocess.call([f"rm -rf {output}/4.viromeQC"], shell=True)
    subprocess.call([f"mkdir {output}/4.viromeQC"], shell=True)
    print(
        f"python {sys.path[0]}/viromeqc/viromeQC.py -i {output}/3.bowtie2/{sample1}.fastq {output}/3.bowtie2/{sample2}.fastq -o {output}/4.viromeQC/report.txt")
    # ret = subprocess.call([
    #     f"python {sys.path[0]}/viromeqc/viromeQC.py -i {output}/3.bowtie2/{sample1}.fastq {output}/3.bowtie2/{sample2}.fastq -o {output}/4.viromeQC/report.txt"],
    #     shell=True)
    ret = 0
    if ret != 0:
        print("Warning: viromeQC error")


def run_spades(output, threads, sample1, sample2):
    print("Run spades")
    if os.path.exists(f"{output}/5.spades") is True:
        subprocess.call([f"rm -rf {output}/5.spades"], shell=True)
    subprocess.call([f"mkdir {output}/5.spades"], shell=True)
    print(
        f"spades.py –meta -1 {output}/3.bowtie2/{sample1}.fastq -2 {output}/3.bowtie2/{sample2}.fastq -t {threads} -o {output}/5.spades")
    ret = subprocess.call([
        f"spades.py –meta -1 {output}/3.bowtie2/{sample1}.fastq -2 {output}/3.bowtie2/{sample2}.fastq -t {threads} -o {output}/5.spades"],
        shell=True)
    if ret != 0:
        sys.exit("Error: spades error")


def run_vsearch_1(output, sample):
    print("Run vsearch (trim short contigs)")
    if os.path.exists(f"{output}/6.filter") is True:
        subprocess.call([f"rm -rf {output}/6.filter"], shell=True)
    subprocess.call([f"mkdir {output}/6.filter"], shell=True)
    print(
        f"vsearch --sortbylength {output}/5.spades/scaffolds.fasta --minseqlength 1000 --maxseqlength -1 --relabel s{sample}.contig --output {output}/6.filter/contig_1k.fasta")
    ret = subprocess.call([
        f"vsearch --sortbylength {output}/5.spades/scaffolds.fasta --minseqlength 1000 --maxseqlength -1 --relabel s{sample}.contig --output {output}/6.filter/contig_1k.fasta"],
        shell=True)
    if ret != 0:
        sys.exit("Error: vsearch error")


def run_virsorter(output, threads):
    print("Run virsorter")
    sofware = "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/viroprofiler-virsorter2/virsorter/bin/"
    db = "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db"  # db
    if os.path.exists(f"{output}/7.vircontigs") is True:
        subprocess.call([f"rm -rf {output}/7.vircontigs"], shell=True)
    subprocess.call([f"mkdir {output}/7.vircontigs"], shell=True)
    print(f"virsorter run -w {output}/7.vircontigs -i {output}/6.filter/contig_1k.fasta -j {threads} all")
    ret = subprocess.call(
        [
            f"{sofware}virsorter run --keep-original-seq -w {output}/7.vircontigs/vs2-pass1 -include-groups dsDNAphage,ssDNA --min-length 5000 --min-score 0.5 -i {output}/6.filter/contig_1k.fasta -j {threads}  -d {db}/virsorter2 all"],
        shell=True)
    print(f"VIR-SOP1")
    ret = subprocess.call(
        [
            f"{sofware}checkv end_to_end {output}/7.vircontigs/vs2-pass1/final-viral-combined.fa checkv -t {threads}  -d {db}/checkvdb/checkv-db-v1.0 "],
        shell=True)
    ret = subprocess.call(
        [
            f"cat {output}/7.vircontigs/checkv/proviruses.fna {output}/7.vircontigs/checkv/viruses.fna > {output}/7.vircontigs/checkv/combined.fna "],
        shell=True)
    print(f"VIR-SOP2")
    ret = subprocess.call(
        [
            f"{sofware}virsorter run --seqname-suffix-off --viral-gene-enrich-off --prep-for-dramv -i {output}/7.vircontigs/checkv/combined.fna -w {output}/7.vircontigs --include-groups dsDNAphage,ssDNA --min-length 5000 --min-score 0.5 -d {db}/virsorter2 all"],
        shell=True)

    if ret != 0:
        sys.exit("Error: virsorter error")


def run_blastn(output, threads):
    print("Run blastn Sorry")
    db = "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db"
    if os.path.exists(f"{output}/8.blastncontigs") is True:
        subprocess.call([f"rm -rf {output}/8.blastncontigs"], shell=True)
    subprocess.call([f"mkdir {output}/8.blastncontigs"], shell=True)
    print(
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/crass -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/crass.out')
    ret = subprocess.call([
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/crass -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/crass.out'],
        shell=True)
    if ret != 0:
        sys.exit("blastn error")
    print(
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/gpd -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/gpd.out')
    ret = subprocess.call([
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/gpd -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/gpd.out'],
        shell=True)
    if ret != 0:
        sys.exit("blastn error")
    print(
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/gvd -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/gvd.out')
    ret = subprocess.call([
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/gvd -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/gvd.out'],
        shell=True)
    if ret != 0:
        sys.exit("blastn error")
    print(
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/mgv -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/mgv.out')
    ret = subprocess.call([
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/mgv -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/mgv.out'],
        shell=True)
    if ret != 0:
        sys.exit("blastn error")
    print(
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/ncbi -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/ncbi.out')
    ret = subprocess.call([
        f'blastn -query {output}/6.filter/contig_1k.fasta -db {db}/blastn_database/ncbi -num_threads {threads} -max_target_seqs 1 -outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " -out {output}/8.blastncontigs/ncbi.out'],
        shell=True)
    if ret != 0:
        sys.exit("Error: blastn error")


def run_combination(output):
    print("Combine virsorter and blastn results")
    if os.path.exists(f"{output}/9.final-contigs") is True:
        subprocess.call([f"rm -rf {output}/9.final-contigs"], shell=True)
    subprocess.call([f"mkdir {output}/9.final-contigs"], shell=True)
    ret = filter_vircontig(output)
    if ret != 0:
        sys.exit("Error: combine error")

def run_checkv(output, threads):
    sofware = "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/viroprofiler-virsorter2/virsorter/bin/"
    db = "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db"  # db
    print("Run checkv")
    if os.path.exists(f"{output}/10.checkv") is True:
        subprocess.call([f"rm -rf {output}/10.checkv"], shell=True)
    subprocess.call([f"mkdir {output}/10.checkv"], shell=True)
    print(
        f"checkv end_to_end {output}/9.final-contigs/contigs.fa {output}/10.checkv -d {sys.path[0]}/checkv_database -t {threads}")
    ret = subprocess.call([
        f"{sofware}checkv end_to_end {output}/9.final-contigs/contigs.fa {output}/10.checkv -d {db}/checkvdb/checkv-db-v1.0 -t {threads}"],
        shell=True)
    if ret != 0:
        sys.exit("Error: checkv error")

def high_quality_output(output):
    print("Get final output")
    if os.path.exists(f"{output}/11.high_quality") is True:
        subprocess.call([f"rm -rf {output}/11.high_quality"], shell=True)
    subprocess.call([f"mkdir {output}/11.high_quality"], shell=True)
    filter_checkv(output)

def run_vsearch_2(output, threads):
    print("Run vsearch (cluster)")
    if os.path.exists(f"{output}/12.final_non_dup") is True:
        subprocess.call([f"rm -rf {output}/12.final_non_dup"], shell=True)
    subprocess.call([f"mkdir {output}/12.final_non_dup"], shell=True)
    print(
        f"vsearch --cluster_fast {output}/11.high_quality/contigs.fa --id 0.995 --centroids {output}/12.final_non_dup/final.fasta --uc {output}/11.high_quality/clusters.uc --maxseqlength -1 --threads {threads}")
    ret = subprocess.call([
        f"vsearch --cluster_fast {output}/11.high_quality/contigs.fa --id 0.995 --centroids {output}/12.final_non_dup/final.fasta --uc {output}/11.high_quality/clusters.uc --maxseqlength -1 --threads {threads}"],
        shell=True)
    if ret != 0:
        sys.exit("Error: vsearch error")
    final_info(output)