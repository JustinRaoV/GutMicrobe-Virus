import subprocess
import os
import shutil
from core.config import get_config_manager
from utils.tools import make_clean_dir
from utils.logging import setup_module_logger
from utils.environment import EnvironmentManager


def run_fastp(**context):
    """质控与修剪原始数据"""
    logger = setup_module_logger("preprocessing.fastp")
    logger.info("开始执行fastp质控")

    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    
    fastp_path = config.get("software", "fastp")
    fastp_params = config.get("parameters", "fastp_params")
    trim_dir = os.path.join(context["paths"]["trimmed"], context["sample"])

    # 创建目录
    make_clean_dir(trim_dir)

    # 构建基础命令
    base_cmd = (
        f"{fastp_path} --in1 {context['input1']} --in2 {context['input2']} "
        f"--out1 {trim_dir}/{context['sample1']}.fq.gz "
        f"--out2 {trim_dir}/{context['sample2']}.fq.gz "
        f"{fastp_params} --thread {context['threads']} "
        f"--html {trim_dir}/{context['sample']}report.html "
        f"--json {trim_dir}/report.json"
    )
    
    # 使用统一的环境管理器执行命令
    try:
        env_manager.run_command(base_cmd, tool_name="main")
        logger.info("fastp质控完成")
    except Exception as e:
        logger.error(f"fastp执行失败: {str(e)}")
        raise


def run_host_removal(**context):
    """去宿主"""
    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    logger = setup_module_logger("preprocessing.host_removal")
    logger.info("开始执行宿主基因组去除")
    
    bowtie2_path = config.get("software", "bowtie2")
    sample = context["sample"]
    sample1 = context["sample1"]
    sample2 = context["sample2"]
    threads = context["threads"]
    host_list = context["host_list"]
    paths = context["paths"]
    
    # 获取数据库路径
    try:
        bowtie2_db = config.get_database_path("bowtie2_db", context["db"])
    except KeyError:
        bowtie2_db = os.path.join(context["db"], "bowtie2_index")

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
                logger.warning(f"Bowtie2索引未找到: {host}")
                
    # 复制质控后的文件
    for fq in [sample1, sample2]:
        trim_dir = os.path.join(context["paths"]["trimmed"], context["sample"], f"{fq}.fq.gz")
        dst = os.path.join(sample_dir, f"{fq}.fq.gz")
        if os.path.exists(trim_dir):
            shutil.copy2(trim_dir, dst)

    if not index_paths:
        logger.warning("未指定宿主基因组，跳过宿主去除步骤")
        return

    try:
        for index in index_paths:
            input1 = os.path.join(sample_dir, f"{sample1}.fq.gz")
            input2 = os.path.join(sample_dir, f"{sample2}.fq.gz")
            tmp_prefix = os.path.join(sample_dir, "tmp")
            sam_output = os.path.join(sample_dir, "tmp.sam")

            # 构建bowtie2命令
            bowtie2_cmd = (
                f"{bowtie2_path} -p {threads} -x {index} "
                f"-1 {input1} -2 {input2} --un-conc {tmp_prefix} -S {sam_output}"
            )
            
            env_manager.run_command(bowtie2_cmd, tool_name="main")
            
            # 使用 pigz 压缩为 .fq.gz 格式
            pigz_path = config.get("software", "pigz", "pigz")
            for i, fq in enumerate([sample1, sample2], 1):
                uncompressed_file = f"{tmp_prefix}.{i}"
                compressed_file = os.path.join(sample_dir, f"{fq}.fq.gz")
                
                pigz_cmd = f"{pigz_path} -p {threads} -c {uncompressed_file}"
                with open(compressed_file, "wb") as outfile:
                    env_manager.run_command(pigz_cmd, tool_name="main", logger=logger, stdout=outfile)
                # 删除未压缩的临时文件
                os.remove(uncompressed_file)
        
        logger.info("宿主基因组去除完成")
    except Exception as e:
        logger.error(f"宿主去除执行失败: {str(e)}")
        raise
    finally:
        # 清理临时文件
        for path in [
            os.path.join(paths["trimmed"], f"{sample}*"),
            os.path.join(paths["host_removed"], sample, "tmp.sam"),
        ]:
            subprocess.run(["rm", "-rf", path], check=False)


def run_assembly(**context):
    """组装"""
    config = get_config_manager()
    env_manager = EnvironmentManager(config)
    logger = setup_module_logger("preprocessing.assembly")
    logger.info("开始执行基因组组装")
    
    megahit_path = config.get("software", "megahit")
    megahit_params = config.get("parameters", "megahit_params")
    assembly_dir_tmp = os.path.join(context["paths"]["assembly"])
    assembly_dir = os.path.join(context["paths"]["assembly"], context["sample"])
    
    if os.path.exists(assembly_dir):
        shutil.rmtree(assembly_dir)
    os.makedirs(assembly_dir_tmp, exist_ok=True)

    # 构建megahit命令
    megahit_cmd = (
        f"{megahit_path} -1 {context['paths']['host_removed']}/{context['sample']}/{context['sample1']}.fq.gz "
        f"-2 {context['paths']['host_removed']}/{context['sample']}/{context['sample2']}.fq.gz "
        f"-o {assembly_dir} {megahit_params} "
        f"--num-cpu-threads {context['threads']}"
    )
    
    try:
        env_manager.run_command(megahit_cmd, tool_name="main")
        logger.info("基因组组装完成")
    except Exception as e:
        logger.error(f"组装执行失败: {str(e)}")
        raise
