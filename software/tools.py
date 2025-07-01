import subprocess
import os
import sys
import pandas as pd


def get_sample_name(file):
    if file.endswith('.fq.gz') or file.endswith('.fastq'):
        return file[:-6]
    elif file.endswith('.fq'):
        return file[:-3]
    elif file.endswith('.fastq.gz'):
        return file[:-9]



def _filter_blastn_file(filepath, dbname, blastn):
    df = pd.read_table(filepath, header=None)
    df.columns = [
        'qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'nident', 'qlen', 'slen', 'length',
        'mismatch', 'positive', 'ppos', 'gapopen', 'gaps', 'qstart', 'qend', 'sstart', 'send',
        'bitscore', 'qcovhsp', 'qcovus', 'qseq', 'sstrand', 'frames'
    ]
    df = df[(df['pident'] >= 50) & (df['evalue'] <= 1e-10) & (df['qcovs'] >= 80)]
    for qseqid in df['qseqid']:
        if qseqid not in blastn:
            blastn.append(qseqid)
    df = df.iloc[:, :5]
    df['database'] = dbname
    return df


def filter_vircontig(output, sample, paths):
    filtered = pd.DataFrame(columns=pd.Index(['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'database']))
    blastn = []
    virso = []
    blastn_dir = os.path.join(paths["blastn"], sample)
    blastn_files = [
        ("crass.out", "crass"),
        ("gpd.out", "gpd"),
        ("gvd.out", "gvd"),
        ("mgv.out", "mgv"),
        ("ncbi.out", "ncbi")
    ]
    for fname, dbname in blastn_files:
        fpath = os.path.join(blastn_dir, fname)
        if os.path.getsize(fpath) != 0:
            filtered = pd.concat([filtered, _filter_blastn_file(fpath, dbname, blastn)], axis=0)
    vircontigs_dir = os.path.join(paths["virsorter"], sample)
    virsorter_file = os.path.join(vircontigs_dir, "final-viral-score.tsv")
    if os.path.getsize(virsorter_file) != 0:
        dat = pd.read_table(virsorter_file, header=0)
        for contig in dat.iloc[:, 0]:
            key = contig.split('|')[0]
            if key not in virso:
                virso.append(key)
    info = []
    vsearch_dir = os.path.join(paths["vsearch"], sample)
    final_dir = os.path.join(paths["combination"], sample)
    with open(f"{vsearch_dir}/contig_1k.fasta") as f:
        line = f.readline()
        if line == '':
            return 1
        f1 = open(f"{final_dir}/contigs.fa", 'w')
        while line:
            contig = line[1:-1]
            out = [contig, 0, 0]
            line = f.readline()
            seq = ''
            while line and line[0] != '>':
                seq += line[:-1]
                line = f.readline()
            if contig in blastn or contig in virso:
                f1.write(f">{contig}\n{seq}\n")
                if contig in blastn:
                    out[1] = 1
                if contig in virso:
                    out[2] = 1
                info.append(out)
            if not line:
                break
        f1.close()
    info_df = pd.DataFrame(info, columns=pd.Index(['contig', 'blastn', 'virsorter']))
    info_df.to_csv(f"{final_dir}/info.txt", header=True, index=False, sep='\t')
    filtered = filtered.sort_values(by=['qcovs', 'pident', 'evalue'], ascending=[False, False, True])
    filtered = filtered.drop_duplicates(subset=['qseqid'])
    filtered.to_csv(f"{final_dir}/blastn_info.txt", header=True, index=False, sep='\t')
    return 0


def filter_checkv(output, sample, paths):
    checkv_dir = os.path.join(paths["checkv"], sample)
    dat = pd.read_table(f"{checkv_dir}/quality_summary.tsv", header=0)
    checkv = dat[dat["checkv_quality"].isin(['Complete', 'High-quality', 'Medium-quality'])]['contig_id'].tolist()
    final_dir = os.path.join(paths["combination"], sample)
    highq_dir = os.path.join(paths["high_quality"], sample)
    with open(f"{final_dir}/contigs.fa") as f, open(f"{highq_dir}/contigs.fa", 'w') as f1:
        while True:
            line = f.readline()
            if not line:
                break
            contig = line[1:-1]
            seq = f.readline()[:-1]
            if contig in checkv:
                f1.write(f">{contig}\n{seq}\n")


def final_info(output, sample, paths):
    checkv_dir = os.path.join(paths["checkv"], sample)
    final_dir = os.path.join(paths["combination"], sample)
    highq_dir = os.path.join(paths["high_quality"], sample)
    nondup_dir = os.path.join(paths["final_non_dup"], sample)
    checkv = pd.read_table(f"{checkv_dir}/quality_summary.tsv", header=0, index_col=0)
    blastn = pd.read_table(f"{final_dir}/blastn_info.txt", header=0, index_col=0)
    info = pd.read_table(f"{final_dir}/info.txt", header=0, index_col=0)
    subprocess.call(
        [f"cat {nondup_dir}/final.fasta | grep '>' > {nondup_dir}/temp.txt"],
        shell=True)
    contig = []
    contig_blastn = []
    with open(f"{nondup_dir}/temp.txt", "r") as fi:
        for line in fi:
            contig.append(line[1:-1])
    for ct in contig:
        if info.loc[ct, 'blastn'] == 1:
            contig_blastn.append(ct)
    checkv.loc[contig, "checkv_quality"].to_csv(f"{nondup_dir}/completeness.txt", header=True, index=True, sep='\t')
    info.loc[contig].to_csv(f"{nondup_dir}/info.txt", header=True, index=True, sep='\t')
    blastn.loc[contig_blastn].to_csv(f"{nondup_dir}/blastn_info.txt", header=True, index=True, sep='\t')
    subprocess.call([f"rm {nondup_dir}/temp.txt"], shell=True)


def remove_inter_result(output):
    subprocess.call(
        [f"rm -rf {output}/3* {output}/5* {output}/6* {output}/7* {output}/8* {output}/9* {output}/10* {output}/11*"],
        shell=True)