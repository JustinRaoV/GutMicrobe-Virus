import os
import subprocess
import sys

def run_merge_contigs(**context):
    """
    高效合并所有样本的filtered_contigs.fa文件，使用shell cat命令，线程数由context['threads']控制（如用于pigz等多线程工具时）
    """

    busco_dir = context['busco_dir']
    logger = context['logger']
    threads = context.get('threads', 1)
    step_dir = context['paths']['merge_contigs']
    os.makedirs(step_dir, exist_ok=True)
    merged_fa = os.path.join(step_dir, 'viruslib.fa')

    # 查找所有filtered_contigs.fa文件
    contig_files = []
    for root, dirs, files in os.walk(busco_dir):
        for file in files:
            if file == 'filtered_contigs.fa':
                contig_files.append(os.path.join(root, file))

    if not contig_files:
        raise RuntimeError(f"在 {busco_dir} 中未找到任何 filtered_contigs.fa 文件")

    logger.info(f"找到 {len(contig_files)} 个 filtered_contigs.fa 文件")
    logger.info(f"合并线程数: {threads}")

    # 用shell命令合并（如需多线程压缩可用pigz）
    cmd = f"cat {' '.join(contig_files)} > {merged_fa}"
    logger.info(f"使用shell命令合并: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

    logger.info(f"合并完成: {merged_fa}")
    file_size = os.path.getsize(merged_fa)
    logger.info(f"合并文件大小: {file_size / (1024*1024):.2f} MB")


def run_vclust_dedup(**context):
    """使用vclust进行去冗余，包含四个步骤：prefilter、align、cluster、提取代表序列，并对最终contig重命名为vOTU1、vOTU2..."""

    config = context['config']
    logger = context['logger']
    threads = context.get('threads', 1)
    step_dir = context['paths']['vclust_dedup']
    os.makedirs(step_dir, exist_ok=True)
    
    input_fa = os.path.join(context['paths']['merge_contigs'], 'viruslib.fa')
    output_fa = os.path.join(step_dir, 'viruslib_nr.fa')
    
    # 获取vclust和seqkit配置
    vclust_bin = config['software']['vclust']
    seqkit_bin = config['software']['seqkit']
    vclust_params = config['parameters'].get('vclust_params', '')
    
    # 修正参数解析，支持'--min-ident 0.95'格式
    params_dict = {}
    tokens = vclust_params.split()
    i = 0
    while i < len(tokens):
        if tokens[i].startswith('--'):
            key = tokens[i]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith('--'):
                value = tokens[i + 1]
                params_dict[key] = value
                i += 2
            else:
                params_dict[key] = ''
                i += 1
        else:
            i += 1
    
    # 设置默认值
    min_ident = params_dict.get('--min-ident', '0.95')
    out_ani = params_dict.get('--out-ani', '0.95')
    out_qcov = params_dict.get('--out-qcov', '0.85')
    ani = params_dict.get('--ani', '0.95')
    qcov = params_dict.get('--qcov', '0.85')
    
    logger.info(f"vclust去冗余参数: min-ident={min_ident}, out-ani={out_ani}, out-qcov={out_qcov}, ani={ani}, qcov={qcov}")
    logger.info(f"vclust线程数: {threads}")
    
    # 步骤1: vclust prefilter
    fltr_file = os.path.join(step_dir, 'fltr.txt')
    cmd1 = f"{vclust_bin} prefilter -i {input_fa} -o {fltr_file} --min-ident {min_ident} --threads {threads}"
    logger.info(f"步骤1 - vclust prefilter: {cmd1}")
    subprocess.run(cmd1, shell=True, check=True)
    
    # 步骤2: vclust align
    ani_file = os.path.join(step_dir, 'ani.tsv')
    cmd2 = f"{vclust_bin} align -i {input_fa} -o {ani_file} --filter {fltr_file} --outfmt lite --out-ani {out_ani} --out-qcov {out_qcov} --threads {threads}"
    logger.info(f"步骤2 - vclust align: {cmd2}")
    subprocess.run(cmd2, shell=True, check=True)
    
    # 步骤3: vclust cluster（不要加--threads）
    clusters_file = os.path.join(step_dir, 'clusters.tsv')
    ids_file = os.path.join(step_dir, 'ani.ids.tsv')
    cmd3 = f"{vclust_bin} cluster -i {ani_file} -o {clusters_file} --ids {ids_file} --algorithm single --metric ani --ani {ani} --qcov {qcov} --out-repr"
    logger.info(f"步骤3 - vclust cluster: {cmd3}")
    subprocess.run(cmd3, shell=True, check=True)
    
    # 步骤4: 提取代表序列
    representatives_file = os.path.join(step_dir, 'representatives.txt')
    cmd4 = f"cut -f 2 {clusters_file} | sort -u > {representatives_file}"
    logger.info(f"步骤4a - 提取代表序列ID: {cmd4}")
    subprocess.run(cmd4, shell=True, check=True)
    
    cmd5 = f"{seqkit_bin} grep -f {representatives_file} {input_fa} -o {output_fa}"
    logger.info(f"步骤4b - seqkit提取代表序列: {cmd5}")
    subprocess.run(cmd5, shell=True, check=True)
    
    # 检查输出文件
    if not os.path.exists(output_fa):
        raise RuntimeError(f"vclust去冗余输出文件不存在: {output_fa}")
    
    file_size = os.path.getsize(output_fa)
    logger.info(f"vclust去冗余完成: {output_fa} ({file_size / (1024*1024):.2f} MB)")

    # 新增：对viruslib_nr.fa的contig重命名为vOTU1、vOTU2...
    logger.info(f"开始对{output_fa}中的contig进行重命名（vOTU递增）")
    rename_fa = os.path.join(step_dir, 'viruslib_nr.renamed.fa')
    count = 1
    with open(output_fa, 'r') as fin, open(rename_fa, 'w') as fout:
        for line in fin:
            if line.startswith('>'):
                fout.write(f">vOTU{count}\n")
                count += 1
            else:
                fout.write(line)
    # 用重命名后的文件覆盖原文件
    os.replace(rename_fa, output_fa)
    logger.info(f"contig重命名完成，结果文件: {output_fa}")


def run_phabox2_prediction(**context):
    """使用phabox2进行病毒预测，命令格式参考用户指定"""

    config = context['config']
    logger = context['logger']
    threads = context.get('threads', 1)
    step_dir = context['paths']['phabox2']
    os.makedirs(step_dir, exist_ok=True)

    # 获取phabox2路径
    phabox2_bin = config['software']['phabox2']
    # 获取数据库路径
    dbdir = config['database'].get('phabox2_db', '')
    if not dbdir:
        raise RuntimeError('请在config.ini的[database]部分配置phabox2_db = /path/to/phabox_db_v2')
    
    # 输入输出路径
    input_fa = os.path.join(context['paths']['vclust_dedup'], 'viruslib_nr.fa')
    output_dir = step_dir

    # 构建命令
    cmd = (
        f"{phabox2_bin} --task end_to_end "
        f"--dbdir {dbdir} "
        f"--skip Y "
        f"--outpth {output_dir} "
        f"--contigs {input_fa} "
        f"--threads {threads}"
    )
    logger.info(f"执行phabox2预测: {cmd}")
    subprocess.run(cmd, shell=True, check=True)
    logger.info(f"phabox2预测完成: {output_dir}")


def run_gene_annotation(**context):
    """基因功能注释，使用prodigal-gv预测蛋白和基因序列"""

    logger = context['logger']
    step_dir = context['paths']['gene_annotation']
    os.makedirs(step_dir, exist_ok=True)

    input_fa = os.path.join(context['paths']['vclust_dedup'], 'viruslib_nr.fa')
    proteins_faa = os.path.join(step_dir, 'proteins.faa')
    dna_fq = os.path.join(step_dir, 'gene.fq')

    # 获取prodigal-gv路径
    prodigal_bin = 'prodigal-gv'  # 假设已在环境变量中

    cmd = f"{prodigal_bin} -p meta -i {input_fa} -a {proteins_faa} -d {dna_fq}"
    logger.info(f"执行基因预测: {cmd}")
    subprocess.run(cmd, shell=True, check=True)
    logger.info(f"prodigal-gv预测完成: {proteins_faa}, {dna_fq}")


def run_taxonomy_annotation(**context):
    """
    病毒物种注释，使用geNomad进行end-to-end注释
    """


    config = context['config']
    logger = context['logger']
    threads = context.get('threads', 1)
    step_dir = context['paths']['taxonomy_annotation']
    os.makedirs(step_dir, exist_ok=True)

    # 输入、输出、数据库路径
    input_fa = os.path.join(context['paths']['vclust_dedup'], 'viruslib_nr.fa')
    output_dir = os.path.join(step_dir, 'genomad_output')
    db_dir = config['database'].get('genomad_db', '')
    if not db_dir:
        raise RuntimeError('请在config.ini的[database]部分配置genomad_db = /path/to/genomad_db')

    os.makedirs(output_dir, exist_ok=True)

    # 获取 genomad 路径
    genomad_bin = config['software']['genomad']

    cmd = f"{genomad_bin} end-to-end --cleanup --splits {threads} {input_fa} {output_dir} {db_dir}"
    logger.info(f"执行geNomad物种注释: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        raise RuntimeError(f"geNomad注释失败，返回码: {ret}")
    logger.info(f"geNomad注释完成: {output_dir}")


def run_cdhit_dedup(**context):
    """基因序列去冗余，使用cd-hit-est"""

    config = context['config']
    logger = context['logger']
    threads = context.get('threads', 1)
    step_dir = context['paths']['cdhit_dedup']
    os.makedirs(step_dir, exist_ok=True)

    # 获取cd-hit-est路径
    cdhit_bin = config['software'].get('cd-hit-est', 'cd-hit-est')
    input_fa = os.path.join(context['paths']['gene_annotation'], 'gene.fq')
    output_fa = os.path.join(step_dir, 'gene_cdhit.fq')

    cmd = f"{cdhit_bin} -i {input_fa} -o {output_fa} -c 0.95 -n 10 -d 0 -T {threads}"
    logger.info(f"执行cd-hit-est去冗余: {cmd}")
    subprocess.run(cmd, shell=True, check=True)
    logger.info(f"cd-hit-est去冗余完成: {output_fa}")


def run_eggnog(**context):
    
    step_dir = context['paths']['eggnog']
    os.makedirs(step_dir, exist_ok=True)
    config = context['config']
    logger = context['logger']
    db_dir = config['database'].get('eggnog5', '')
    if not db_dir:
        raise RuntimeError('请在config.ini的[database]部分配置eggnog5 = /path/to/eggnog5')
    env_activate = config['environment'].get('eggnog_conda_activate', '')
    if not env_activate:
        raise RuntimeError('请在config.ini的[environment]部分配置eggnog_conda_activate')
    input_fa = os.path.join(context['paths']['gene_annotation'], 'proteins.faa')
    pfam_out = os.path.join(step_dir, 'pfam')
    vogdb_out = os.path.join(step_dir, 'VOGdb')
    # Pfam
    cmd1 = f'{env_activate} && emapper.py -i {input_fa} --output {pfam_out} -d pfam --data_dir {db_dir}'
    logger.info(f"运行eggNOG Pfam注释: {cmd1}")
    ret = subprocess.call(['bash', '-c', cmd1])
    if ret != 0:
        sys.exit("Error: eggnog pfam error")
    # VOGdb
    cmd2 = f'{env_activate} && emapper.py -i {input_fa} --output {vogdb_out} -d VOGdb --data_dir {db_dir}'
    logger.info(f"运行eggNOG VOGdb注释: {cmd2}")
    ret = subprocess.call(['bash', '-c', cmd2])
    if ret != 0:
        sys.exit("Error: eggnog VOGDB error")
    logger.info("eggNOG注释完成")