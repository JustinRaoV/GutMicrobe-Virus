import subprocess
import os
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


def filter_vircontig_enhanced(output, sample, paths):
    """增强版病毒contig过滤，支持所有工具的结果合并
    
    支持的工具：
    - BLASTN: 病毒数据库比对
    - VirSorter: 病毒序列预测
    - DeepVirFinder: 深度学习病毒预测
    - VIBRANT: 病毒识别和注释
    - CheckV预过滤: 病毒基因计数更高的contigs
    """
    print("[filter_vircontig_enhanced] Processing virus detection results...")
    
    # 读取配置
    import configparser
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # 获取工具选择配置
    use_blastn = config.getboolean('combination', 'use_blastn', fallback=True)
    use_virsorter = config.getboolean('combination', 'use_virsorter', fallback=True)
    use_dvf = config.getboolean('combination', 'use_dvf', fallback=True)
    use_vibrant = config.getboolean('combination', 'use_vibrant', fallback=True)
    use_checkv_prefilter = config.getboolean('combination', 'use_checkv_prefilter', fallback=True)
    
    print(f"[filter_vircontig_enhanced] Tool selection:")
    print(f"  - BLASTN: {'✓' if use_blastn else '✗'}")
    print(f"  - VirSorter: {'✓' if use_virsorter else '✗'}")
    print(f"  - DeepVirFinder: {'✓' if use_dvf else '✗'}")
    print(f"  - VIBRANT: {'✓' if use_vibrant else '✗'}")
    print(f"  - CheckV预过滤: {'✓' if use_checkv_prefilter else '✗'}")
    
    # 初始化结果容器
    filtered = pd.DataFrame(columns=pd.Index(['qseqid', 'sseqid', 'pident', 'evalue', 'qcovs', 'database']))
    blastn_contigs = []
    virsorter_contigs = []
    dvf_contigs = []
    vibrant_contigs = []
    checkv_viral_contigs = []
    
    # 1. 处理 BLASTN 结果
    if use_blastn:
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
            if os.path.exists(fpath) and os.path.getsize(fpath) != 0:
                filtered = pd.concat([filtered, _filter_blastn_file(fpath, dbname, blastn_contigs)], axis=0)
    
    # 2. 处理 VirSorter 结果
    if use_virsorter:
        virsorter_dir = os.path.join(paths["virsorter"], sample)
        virsorter_file = os.path.join(virsorter_dir, "final-viral-score.tsv")
        if os.path.exists(virsorter_file) and os.path.getsize(virsorter_file) != 0:
            dat = pd.read_table(virsorter_file, header=0)
            for contig in dat.iloc[:, 0]:
                key = contig.split('|')[0]
                if key not in virsorter_contigs:
                    virsorter_contigs.append(key)
    
    # 3. 处理 DeepVirFinder 结果
    if use_dvf:
        dvf_dir = os.path.join(paths["dvf"], sample)
        dvf_list_file = os.path.join(dvf_dir, "virus_dvf.list")
        if os.path.exists(dvf_list_file):
            with open(dvf_list_file, 'r') as f:
                for line in f:
                    contig = line.strip()
                    if contig and contig not in dvf_contigs:
                        dvf_contigs.append(contig)
    
    # 4. 处理 VIBRANT 结果
    if use_vibrant:
        vibrant_dir = os.path.join(paths["vibrant"], sample)
        vibrant_file = os.path.join(vibrant_dir, "VIBRANT_filtered_contigs", "VIBRANT_phages_filtered_contigs", "filtered_contigs.phages_combined.txt")
        if os.path.exists(vibrant_file):
            with open(vibrant_file, 'r') as f:
                for line in f:
                    if line.startswith('>'):
                        contig = line[1:].strip().split()[0]  # 提取contig名称
                        if contig and contig not in vibrant_contigs:
                            vibrant_contigs.append(contig)
    
    # 5. 处理 CheckV 预过滤结果
    if use_checkv_prefilter:
        checkv_prefilter_dir = os.path.join(paths["checkv_prefilter"], sample)
        checkv_viral_file = os.path.join(checkv_prefilter_dir, "viral_contigs.list")
        if os.path.exists(checkv_viral_file):
            with open(checkv_viral_file, 'r') as f:
                for line in f:
                    contig = line.strip()
                    if contig and contig not in checkv_viral_contigs:
                        checkv_viral_contigs.append(contig)
    
    # 合并所有病毒contigs
    all_viral_contigs = set()
    all_viral_contigs.update(blastn_contigs)
    all_viral_contigs.update(virsorter_contigs)
    all_viral_contigs.update(dvf_contigs)
    all_viral_contigs.update(vibrant_contigs)
    all_viral_contigs.update(checkv_viral_contigs)
    
    print(f"[filter_vircontig_enhanced] Found viral contigs:")
    print(f"  - BLASTN: {len(blastn_contigs)}")
    print(f"  - VirSorter: {len(virsorter_contigs)}")
    print(f"  - DeepVirFinder: {len(dvf_contigs)}")
    print(f"  - VIBRANT: {len(vibrant_contigs)}")
    print(f"  - CheckV预过滤: {len(checkv_viral_contigs)}")
    print(f"  - 总计: {len(all_viral_contigs)}")
    
    # 生成最终结果
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
            out = [contig, 0, 0, 0, 0, 0]  # [contig, blastn, virsorter, dvf, vibrant, checkv_viral]
            line = f.readline()
            seq = ''
            while line and line[0] != '>':
                seq += line[:-1]
                line = f.readline()
            
            if contig in all_viral_contigs:
                f1.write(f">{contig}\n{seq}\n")
                if contig in blastn_contigs:
                    out[1] = 1
                if contig in virsorter_contigs:
                    out[2] = 1
                if contig in dvf_contigs:
                    out[3] = 1
                if contig in vibrant_contigs:
                    out[4] = 1
                if contig in checkv_viral_contigs:
                    out[5] = 1
                info.append(out)
            
            if not line:
                break
        f1.close()
    
    # 保存详细信息
    info_df = pd.DataFrame(info, columns=pd.Index(['contig', 'blastn', 'virsorter', 'dvf', 'vibrant', 'checkv_viral']))
    info_df.to_csv(f"{final_dir}/info.txt", header=True, index=False, sep='\t')
    
    # 保存 BLASTN 详细信息
    if not filtered.empty:
        filtered = filtered.sort_values(by=['qcovs', 'pident', 'evalue'], ascending=[False, False, True])
        filtered = filtered.drop_duplicates(subset=['qseqid'])
        filtered.to_csv(f"{final_dir}/blastn_info.txt", header=True, index=False, sep='\t')
    
    # 保存各工具的contig列表
    tool_lists = {
        'blastn_contigs.list': blastn_contigs,
        'virsorter_contigs.list': virsorter_contigs,
        'dvf_contigs.list': dvf_contigs,
        'vibrant_contigs.list': vibrant_contigs,
        'checkv_viral_contigs.list': checkv_viral_contigs
    }
    
    for filename, contig_list in tool_lists.items():
        with open(os.path.join(final_dir, filename), 'w') as f:
            for contig in contig_list:
                f.write(f"{contig}\n")
    
    print(f"[filter_vircontig_enhanced] Results saved to: {final_dir}")
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
    print(f"Removing intermediate results from {output}...")