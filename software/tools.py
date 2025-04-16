import subprocess
import os
import sys
import pandas as pd


def get_sample_name(file):
    if file[-6:] == '.fq.gz' or file[-6:] == '.fastq':
        return file[0: -6]
    elif file[-3:] == '.fq':
        return file[0: -3]
    elif file[-9:] == '.fastq.gz':
        return file[0: -9]


def create_output_file(output):
    os.makedirs(os.path.join(output, "logs"), exist_ok=True)


def filter_vircontig(output, sample):
    filtered = pd.DataFrame(data=None, columns=['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'database'])
    blastn = []
    virso = []
    if os.path.getsize(f"{output}/7.blastncontigs/{sample}/crass.out") != 0:
        crass = pd.read_table(f"{output}/7.blastncontigs/{sample}/crass.out", header=None)
        crass.columns = ['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'nident', 'qlen', 'slen', 'length',
                         'mismatch', 'positive', 'ppos', 'gapopen', 'gaps', 'qstart', 'qend', 'sstart', 'send',
                         'bitscore', 'qcovhsp', 'qcovus', 'qseq', 'sstrand', 'frames']
        crass = crass[crass['pident'] >= 50]
        crass = crass[crass['evalue'] <= 1e-10]
        crass = crass[crass['qcovs'] >= 80]
        for i in range(len(crass)):
            if crass.iloc[i, 0] not in blastn:
                blastn.append(crass.iloc[i, 0])
        crass = crass.iloc[:, :5]
        crass['database'] = ['crass'] * len(crass)
        filtered = pd.concat([filtered, crass], axis=0)
    if os.path.getsize(f"{output}/7.blastncontigs/{sample}/gpd.out") != 0:
        gpd = pd.read_table(f"{output}/7.blastncontigs/{sample}/gpd.out", header=None)
        gpd.columns = ['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'nident', 'qlen', 'slen', 'length', 'mismatch',
                       'positive', 'ppos', 'gapopen', 'gaps', 'qstart', 'qend', 'sstart', 'send', 'bitscore', 'qcovhsp',
                       'qcovus', 'qseq', 'sstrand', 'frames']
        gpd = gpd[gpd['pident'] >= 50]
        gpd = gpd[gpd['evalue'] <= 1e-10]
        gpd = gpd[gpd['qcovs'] >= 80]
        for i in range(len(gpd)):
            if gpd.iloc[i, 0] not in blastn:
                blastn.append(gpd.iloc[i, 0])
        gpd = gpd.iloc[:, :5]
        gpd['database'] = ['gpd'] * len(gpd)
        filtered = pd.concat([filtered, gpd], axis=0)
    if os.path.getsize(f"{output}/7.blastncontigs/{sample}/gvd.out") != 0:
        gvd = pd.read_table(f"{output}/7.blastncontigs/{sample}/gvd.out", header=None)
        gvd.columns = ['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'nident', 'qlen', 'slen', 'length', 'mismatch',
                       'positive', 'ppos', 'gapopen', 'gaps', 'qstart', 'qend', 'sstart', 'send', 'bitscore', 'qcovhsp',
                       'qcovus', 'qseq', 'sstrand', 'frames']
        gvd = gvd[gvd['pident'] >= 50]
        gvd = gvd[gvd['evalue'] <= 1e-10]
        gvd = gvd[gvd['qcovs'] >= 80]
        for i in range(len(gvd)):
            if gvd.iloc[i, 0] not in blastn:
                blastn.append(gvd.iloc[i, 0])
        gvd = gvd.iloc[:, :5]
        gvd['database'] = ['gvd'] * len(gvd)
        filtered = pd.concat([filtered, gvd], axis=0)
    if os.path.getsize(f"{output}/7.blastncontigs/{sample}/mgv.out") != 0:
        mgv = pd.read_table(f"{output}/7.blastncontigs/{sample}/mgv.out", header=None)
        mgv.columns = ['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'nident', 'qlen', 'slen', 'length', 'mismatch',
                       'positive', 'ppos', 'gapopen', 'gaps', 'qstart', 'qend', 'sstart', 'send', 'bitscore', 'qcovhsp',
                       'qcovus', 'qseq', 'sstrand', 'frames']
        mgv = mgv[mgv['pident'] >= 50]
        mgv = mgv[mgv['evalue'] <= 1e-10]
        mgv = mgv[mgv['qcovs'] >= 80]
        for i in range(len(mgv)):
            if mgv.iloc[i, 0] not in blastn:
                blastn.append(mgv.iloc[i, 0])
        mgv = mgv.iloc[:, :5]
        mgv['database'] = ['mgv'] * len(mgv)
        filtered = pd.concat([filtered, mgv], axis=0)
    if os.path.getsize(f"{output}/7.blastncontigs/{sample}/ncbi.out") != 0:
        ncbi = pd.read_table(f"{output}/7.blastncontigs/{sample}/ncbi.out", header=None)
        ncbi.columns = ['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'nident', 'qlen', 'slen', 'length', 'mismatch',
                        'positive', 'ppos', 'gapopen', 'gaps', 'qstart', 'qend', 'sstart', 'send', 'bitscore',
                        'qcovhsp', 'qcovus', 'qseq', 'sstrand', 'frames']
        ncbi = ncbi[ncbi['pident'] >= 50]
        ncbi = ncbi[ncbi['evalue'] <= 1e-10]
        ncbi = ncbi[ncbi['qcovs'] >= 80]
        for i in range(len(ncbi)):
            if ncbi.iloc[i, 0] not in blastn:
                blastn.append(ncbi.iloc[i, 0])
        ncbi = ncbi.iloc[:, :5]
        ncbi['database'] = ['ncbi'] * len(ncbi)
        filtered = pd.concat([filtered, ncbi], axis=0)
    if os.path.getsize(f"{output}/6.vircontigs/{sample}/final-viral-score.tsv") != 0:
        dat = pd.read_table(f"{output}/6.vircontigs/{sample}/final-viral-score.tsv", header=0)
        for i in range(len(dat)):
            if dat.iloc[i, 0] not in virso:
                virso.append(dat.iloc[i, 0].split('|')[0])
    info = pd.DataFrame(data=None, columns=['contig', 'blastn', 'virsorter'])
    num = 0
    with open(f"{output}/5.filter/{sample}/contig_1k.fasta") as f:
        line = f.readline()
        if line == '':
            return 1
        f1 = open(f"{output}/8.final-contigs/{sample}/contigs.fa", 'w')
        while 1:
            contig = line[1: -1]
            out = [contig, 0, 0]
            line = f.readline()
            seq = ''
            while line != '' and line[0] != '>':
                seq = seq + line[0: -1]
                line = f.readline()
            if contig in blastn or contig in virso:
                print(f">{contig}", file=f1)
                print(seq, file=f1)
                if contig in blastn:
                    out[1] = 1
                if contig in virso:
                    out[2] = 1
                info.loc[num] = out
                num += 1
            if line == '':
                break
        f1.close()
    info.to_csv(f"{output}/8.final-contigs/{sample}/info.txt", header=True, index=False, sep='\t')
    filtered = filtered.sort_values(by=['qcovs', 'pident', 'evalue'], ascending=[False, False, True])
    filtered.drop_duplicates(subset=['qseqid'])
    filtered.to_csv(f"{output}/8.final-contigs/{sample}/blastn_info.txt", header=True, index=False, sep='\t')
    return 0


def filter_checkv(output, sample):
    dat = pd.read_table(f"{output}/10.checkv/{sample}/quality_summary.tsv", header=0)
    dat1 = dat[dat["checkv_quality"] == 'Complete']
    dat2 = dat[dat["checkv_quality"] == 'High-quality']
    dat3 = dat[dat["checkv_quality"] == 'Medium-quality']
    checkv = pd.concat([dat1, dat2, dat3])['contig_id'].to_list()
    with open(f"{output}/9.final-contigs/{sample}/contigs.fa") as f:
        f1 = open(f"{output}/11.high_quality/{sample}/contigs.fa", 'w')
        while 1:
            line = f.readline()
            if line == '':
                break
            contig = line[1: -1]
            seq = f.readline()[:-1]
            if contig in checkv:
                print(f">{contig}", file=f1)
                print(seq, file=f1)
        f1.close()


def final_info(output, sample):
    checkv = pd.read_table(f"{output}/10.checkv/{sample}/quality_summary.tsv", header=0, index_col=0)
    blastn = pd.read_table(f"{output}/9.final-contigs/{sample}/blastn_info.txt", header=0, index_col=0)
    info = pd.read_table(f"{output}/9.final-contigs/{sample}/info.txt", header=0, index_col=0)
    subprocess.call(
        [
            f"cat {output}/12.final_non_dup/{sample}/final.fasta | grep '>' > {output}/12.final_non_dup/{sample}/temp.txt"],
        shell=True)
    contig = []
    contig_blastn = []
    with open(f"{output}/12.final_non_dup/{sample}/temp.txt", "r") as fi:
        while 1:
            line = fi.readline()
            if line == '':
                break
            contig.append(line[1: -1])
    for ct in contig:
        if info.loc[ct, 'blastn'] == 1:
            contig_blastn.append(ct)
    checkv.loc[contig, "checkv_quality"].to_csv(f"{output}/12.final_non_dup/{sample}/completeness.txt", header=True,
                                                index=True,
                                                sep='\t')
    info.loc[contig].to_csv(f"{output}/12.final_non_dup/{sample}/info.txt", header=True, index=True, sep='\t')
    blastn.loc[contig_blastn].to_csv(f"{output}/12.final_non_dup/{sample}/blastn_info.txt", header=True, index=True,
                                     sep='\t')
    subprocess.call([f"rm {output}/12.final_non_dup/{sample}/temp.txt"], shell=True)


def remove_inter_result(output):
    subprocess.call(
        [f"rm -rf {output}/3* {output}/5* {output}/6* {output}/7* {output}/8* {output}/9* {output}/10* {output}/11*"],
        shell=True)
