import subprocess
import os
import shutil
from core.config_manager import get_config
from utils.tools import make_clean_dir
from utils.common import create_simple_logger


def run_fastp(**context):
    """质控与修剪原始数据"""
    logger = create_simple_logger("fastp")
    logger.info("Running fastp...")

    config = get_config()
    fastp_path = config["software"]["fastp"]
    fastp_params = config["parameters"]["fastp_params"]
    trim_dir = os.path.join(context["paths"]["trimmed"], context["sample"])

    # 直接用 os.makedirs 创建目录
    make_clean_dir(trim_dir)

    # 使用主环境运行fastp
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{fastp_path} --in1 {context['input1']} --in2 {context['input2']} "
        f"--out1 {trim_dir}/{context['sample1']}.fq.gz "
        f"--out2 {trim_dir}/{context['sample2']}.fq.gz "
        f"{fastp_params} --thread {context['threads']} "
        f"--html {trim_dir}/{context['sample']}report.html "
        f"--json {trim_dir}/report.json"
    )

    logger.info(f"执行fastp命令: {cmd}")

    # 直接用 subprocess 运行命令
    subprocess.run(cmd, shell=True, check=True)


def run_host_removal(**context):
    """去宿主"""
    config = get_config()
    logger = create_simple_logger("host_removal")
    logger.info("Running host removal...")
    bowtie2_path = config["software"]["bowtie2"]
    sample = context["sample"]
    sample1 = context["sample1"]
    sample2 = context["sample2"]
    threads = context["threads"]
    host_list = context["host_list"]
    paths = context["paths"]
    if config.has_section("database") and config["database"].get("bowtie2_db"):
        bowtie2_db = config["database"]["bowtie2_db"]
    else:
        bowtie2_db = context["db"] + "/bowtie2_index/"

    sample_dir = os.path.join(paths["host_removed"], sample)
    make_clean_dir(sample_dir)

    # 构建索引路径列表
    index_paths = []
    if host_list:
        for host in host_list:
            index_path = os.path.join(bowtie2_db, f"{host}/{host}")
            if os.path.exists(f"{index_path}.1.bt2"):
                index_paths.append(index_path)
            else:
                logger.warning(
                    f"[host_removal] Warning: Bowtie2 index not found for {host}"
                )
    for fq in [sample1, sample2]:
        trim_dir = os.path.join(
            context["paths"]["trimmed"], context["sample"], f"{fq}.fq.gz"
        )
        dst = os.path.join(sample_dir, f"{fq}.fq.gz")
        if os.path.exists(trim_dir):
            shutil.copy2(trim_dir, dst)

    if not index_paths and logger:
        logger.warning("[host_removal] No host genome specified, skipping host removal")
        return

    for index in index_paths:
        input1 = os.path.join(sample_dir, f"{sample1}.fq.gz")
        input2 = os.path.join(sample_dir, f"{sample2}.fq.gz")
        tmp_prefix = os.path.join(sample_dir, "tmp")
        sam_output = os.path.join(sample_dir, "tmp.sam")

        # 使用主环境运行bowtie2
        cmd = (
            f"{config['environment']['main_conda_activate']} && "
            f"{bowtie2_path} -p {threads} -x {index} "
            f"-1 {input1} -2 {input2} --un-conc {tmp_prefix} -S {sam_output}"
        )
        logger.info(f"[host_removal] Running: {cmd}")

        subprocess.run(cmd, shell=True, check=True)
        # 使用 pigz 压缩为 .fq.gz 格式
        for i, fq in enumerate([sample1, sample2], 1):
            uncompressed_file = f"{tmp_prefix}.{i}"
            compressed_file = os.path.join(sample_dir, f"{fq}.fq.gz")
            pigz_cmd = f"{config['environment']['main_conda_activate']} && pigz -p {threads} -c {uncompressed_file}"
            with open(compressed_file, "wb") as outfile:
                subprocess.run(pigz_cmd, shell=True, stdout=outfile, check=True)
            # 删除未压缩的临时文件
            os.remove(uncompressed_file)
    # 清理临时文件，使用 paths 里的绝对路径
    for path in [
        os.path.join(paths["trimmed"], f"{sample}*"),
        os.path.join(paths["host_removed"], sample, "tmp.sam"),
    ]:
        subprocess.run(["rm", "-rf", path], check=True)


def run_assembly(**context):
    """组装"""
    config = get_config()
    megahit_path = config["software"]["megahit"]
    logger = create_simple_logger("assembly")
    logger.info("Running assembly...")
    megahit_params = config["parameters"]["megahit_params"]
    assembly_dir_tmp = os.path.join(context["paths"]["assembly"])
    assembly_dir = os.path.join(context["paths"]["assembly"], context["sample"])
    if os.path.exists(assembly_dir):
        shutil.rmtree(assembly_dir)
    os.makedirs(assembly_dir_tmp, exist_ok=True)

    # 使用主环境运行megahit
    cmd = (
        f"{config['environment']['main_conda_activate']} && "
        f"{megahit_path} -1 {context['paths']['host_removed']}/{context['sample']}/{context['sample1']}.fq.gz "
        f"-2 {context['paths']['host_removed']}/{context['sample']}/{context['sample2']}.fq.gz "
        f"-o {assembly_dir} {megahit_params} "
        f"--num-cpu-threads {context['threads']}"
    )
    logger.info(f"[assembly] Running: {cmd}")

    subprocess.run(cmd, shell=True, check=True)
