"""
病毒检测模块

本模块包含各种病毒识别工具，包括 VirSorter、DeepVirFinder 和 VIBRANT。
"""

import subprocess
import os
from core.config_manager import get_config
from utils.common import create_simple_logger
from utils.tools import make_clean_dir


def run_virsorter(**context):
    """VirSorter 病毒识别

    使用 VirSorter2 进行病毒识别，包括两轮识别和中间的质量评估。
    """
    logger = create_simple_logger("virsorter")
    logger.info("[virsorter] Running VirSorter...")

    # 设置路径和参数
    input_fasta = os.path.join(
        context["paths"]["checkv_prefilter"], context["sample"], "filtered_contigs.fa"
    )
    virsorter_dir = os.path.join(context["paths"]["virsorter"], context["sample"])
    config = get_config()
    env_config = config["environment"]

    make_clean_dir(virsorter_dir)

    # 执行三个步骤
    logger.info("[virsorter] Running pass1...")
    _run_virsorter_pass1(
        config["software"]["virsorter"],
        input_fasta,
        virsorter_dir,
        context["threads"],
        config["parameters"]["virsorter_params"],
        env_config,
    )
    logger.info("[virsorter] Running checkv...")
    _run_checkv_in_virsorter(
        config["software"]["checkv"],
        virsorter_dir,
        context["db"],
        context["threads"],
    )

    logger.info("[virsorter] Running pass2...")
    _run_virsorter_pass2(
        config["software"]["virsorter"],
        virsorter_dir,
        config["parameters"]["virsorter_params"],
        env_config,
    )


def _run_virsorter_pass1(
    virsorter_path, input_fasta, virsorter_dir, threads, virsorter_params, env_config
):
    """运行 VirSorter 第一轮"""
    if env_config.get("virsorter_module_unload"):
        unload_cmd = f"{env_config['virsorter_module_unload']} && "
    else:
        unload_cmd = ""
    if env_config.get("virsorter_conda_activate"):
        activate_cmd = f"{env_config['virsorter_conda_activate']} && "
    else:
        activate_cmd = ""
    cmd = (
        f"{unload_cmd} {activate_cmd} "
        f"{virsorter_path} run --prep-for-dramv -w {virsorter_dir}/vs2-pass1 "
        f"-i {input_fasta} -j {threads} {virsorter_params} "
        f"--keep-original-seq all"
    )
    subprocess.run(cmd, shell=True, check=True)


def _run_checkv_in_virsorter(checkv_path, virsorter_dir, db, threads):
    """在 VirSorter 中运行 CheckV"""
    checkv_dir = os.path.join(virsorter_dir, "checkv")

    # 清理并创建目录
    make_clean_dir(checkv_dir)

    # 运行 CheckV
    cmd = (
        f"{checkv_path} end_to_end {os.path.join(virsorter_dir, 'vs2-pass1/final-viral-combined.fa')} {checkv_dir} "
        f"-d {os.path.join(db, 'checkvdb/checkv-db-v1.4')} -t {threads}"
    )
    subprocess.run(cmd, shell=True, check=True)

    # 合并 proviruses.fna 和 viruses.fna
    with open(os.path.join(checkv_dir, "combined.fna"), "w") as out:
        for f in ["proviruses.fna", "viruses.fna"]:
            with open(os.path.join(checkv_dir, f)) as infile:
                out.write(infile.read())


def _run_virsorter_pass2(virsorter_path, virsorter_dir, virsorter_params, env_config):
    """运行 VirSorter 第二轮"""
    if env_config.get("virsorter_module_unload"):
        unload_cmd = f"{env_config['virsorter_module_unload']} && "
    else:
        unload_cmd = ""
    if env_config.get("virsorter_conda_activate"):
        activate_cmd = f"{env_config['virsorter_conda_activate']} && "
    else:
        activate_cmd = ""
    cmd = (
        f"{unload_cmd} {activate_cmd} "
        f"{virsorter_path} run -w {virsorter_dir} "
        f"-i {virsorter_dir}/checkv/combined.fna --prep-for-dramv "
        f"{virsorter_params} all"
    )
    subprocess.run(cmd, shell=True, check=True)


def run_dvf(**context):
    """DeepVirFinder 病毒识别

    使用 DeepVirFinder 进行病毒序列预测，基于深度学习模型。
    """
    logger = create_simple_logger("dvf")
    logger.info("[dvf] Running DeepVirFinder...")

    config = get_config()
    env = config["environment"]
    if env.get("dvf_module_unload"):
        unload_cmd = f"{env['dvf_module_unload']} && "
    else:
        unload_cmd = ""
    if env.get("dvf_conda_activate"):
        activate_cmd = f"{env['dvf_conda_activate']} && "
    else:
        activate_cmd = ""
    dvf_path = config["software"]["dvf"]
    sample = context["sample"]
    threads = context["threads"]
    paths = context["paths"]
    db_root = context["db"]
    # 优先用config.ini里的dvf_models，否则用--db拼接默认子路径
    if config.has_section("database") and config["database"].get("dvf_models"):
        dvf_models = config["database"]["dvf_models"]
    else:
        dvf_models = os.path.join(db_root, "dvf/models")

    # 设置输入输出路径
    input_fasta = os.path.join(paths["checkv_prefilter"], sample, "filtered_contigs.fa")
    dvf_dir = os.path.join(paths["dvf"], sample)

    # 清理并创建目录
    make_clean_dir(dvf_dir)

    # 运行 DeepVirFinder
    cmd = f"""
    {unload_cmd} {activate_cmd}
    {dvf_path} -i {input_fasta} -o {dvf_dir} -c {threads} \
    -m {dvf_models}
    """
    subprocess.run(cmd, shell=True, check=True)

    # 过滤结果：使用配置文件中的阈值
    config = get_config()
    dvf_score_threshold = config["parameters"]["dvf_score_threshold"]
    dvf_pvalue_threshold = config["parameters"]["dvf_pvalue_threshold"]
    cmd = f"awk 'NR>1 && $3 > {dvf_score_threshold} && $4 < {dvf_pvalue_threshold} {{print $1}}' {dvf_dir}/*_dvfpred.txt > {dvf_dir}/virus_dvf.list"
    subprocess.run(cmd, shell=True, check=True)

    # 提取病毒序列
    cmd = f"seqkit grep -f {dvf_dir}/virus_dvf.list {input_fasta} > {dvf_dir}/dvf.fasta"
    subprocess.run(cmd, shell=True, check=True)

    logger.info(f"[dvf] DeepVirFinder analysis completed. Results saved to: {dvf_dir}")


def run_vibrant(**context):
    """VIBRANT 病毒识别

    使用 VIBRANT 进行病毒序列预测和注释。
    """
    logger = create_simple_logger("vibrant")
    logger.info("[vibrant] Running VIBRANT...")

    config = get_config()
    env = config["environment"]
    if env.get("vibrant_module_unload"):
        unload_cmd = f"{env['vibrant_module_unload']} && "
    else:
        unload_cmd = ""
    if env.get("vibrant_conda_activate"):
        activate_cmd = f"{env['vibrant_conda_activate']} && "
    else:
        activate_cmd = ""
    vibrant_path = config["software"]["vibrant"]
    db_root = context["db"]
    # 优先用config.ini里的vibrant_database和vibrant_files，否则用--db拼接默认子路径
    if config.has_section("database") and config["database"].get("vibrant_database"):
        vibrant_database = config["database"]["vibrant_database"]
    else:
        vibrant_database = os.path.join(db_root, "vibrant/databases")
    if config.has_section("database") and config["database"].get("vibrant_files"):
        vibrant_files = config["database"]["vibrant_files"]
    else:
        vibrant_files = os.path.join(db_root, "vibrant/files")
    sample = context["sample"]
    threads = context["threads"]
    paths = context["paths"]

    # 设置输入输出路径
    input_fasta = os.path.join(paths["checkv_prefilter"], sample, "filtered_contigs.fa")
    vibrant_dir = os.path.join(paths["vibrant"], sample)

    # 清理并创建目录
    make_clean_dir(vibrant_dir)

    # 运行 VIBRANT
    cmd = f"""
    {unload_cmd} {activate_cmd}
    {vibrant_path} -i {input_fasta} -folder {vibrant_dir} -t {threads} \
    -d {vibrant_database} -m {vibrant_files}
    """
    subprocess.run(cmd, shell=True, check=True)

    logger.info(
        f"[vibrant] VIBRANT analysis completed. Results saved to: {vibrant_dir}"
    )


def run_blastn(**context):
    """BLASTN 比对
    对过滤后的 contigs 进行 BLASTN 比对，搜索病毒数据库。
    """
    logger = create_simple_logger("blastn")
    logger.info("[blastn] Running blastn...")

    config = get_config()
    db_root = context["db"]
    # 优先用config.ini里的blastn_database，否则用--db拼接默认子路径
    if config.has_section("database") and config["database"].get("blastn_database"):
        blastn_db_root = config["database"]["blastn_database"]
    else:
        blastn_db_root = os.path.join(db_root, "blastn_database")
    blastn_dir = os.path.join(context["paths"]["blastn"], context["sample"])

    # 清理并创建目录
    make_clean_dir(blastn_dir)

    # 对多个数据库进行比对，使用主环境
    for dbname in ["crass", "gpd", "gvd", "mgv", "ncbi"]:
        out_path = f"{blastn_dir}/{dbname}.out"
        cmd = (
            f"{config['environment']['main_conda_activate']} && "
            f'blastn -query {context["paths"]["vsearch"]}/{context["sample"]}/contig.fasta '
            f'-db {blastn_db_root}/{dbname} -num_threads {context["threads"]} -max_target_seqs 1 '
            f'-outfmt "6 qseqid sseqid pident evalue qcovs nident qlen slen length mismatch positive ppos gapopen gaps qstart qend sstart send bitscore qcovhsp qcovus qseq sstrand frames " '
            f"-out {out_path}"
        )

        subprocess.run(cmd, shell=True, check=True)

    logger.info("[blastn] blastn analysis completed successfully")
