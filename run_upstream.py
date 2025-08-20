import argparse
import os
import sys
from utils.tools import get_sample_name, remove_inter_result
from utils.paths import get_paths
from utils.logging import setup_logger, setup_module_logger
from core.config import Config
from modules import (
    run_fastp, run_host_removal, run_assembly, run_vsearch,
    run_checkv_prefilter, run_virsorter, run_dvf, run_vibrant,
    run_blastn, run_combination, run_checkv, high_quality_output,
    run_busco_filter
)


def parameter_input():
    parser = argparse.ArgumentParser(description="GutMicrobe Virus Pipeline")
    parser.add_argument("input1", help="Path to the fastq(.gz) file of read1")
    parser.add_argument("input2", help="Path to the fastq(.gz) file of read2")
    parser.add_argument(
        "--host", help="Bowtie2 index name(s), comma separated", default=None
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory",
        default=os.path.join(os.getcwd(), "result"),
    )
    parser.add_argument(
        "-t", "--threads", type=int, help="Number of threads", default=1
    )
    parser.add_argument(
        "-r",
        "--remove_inter_result",
        action="store_true",
        help="Remove intermediate results",
        default=False,
    )
    parser.add_argument(
        "-k",
        "--keep_log",
        action="store_true",
        help="Resume interrupted run",
        default=True,
    )
    parser.add_argument("--db", help="Path to database directory", default="~/db")
    parser.add_argument("--config", help="Path to config file", default="config.ini")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level",
    )
    parser.add_argument(
        "--validate-config", action="store_true", help="Validate configuration and exit"
    )
    return parser.parse_args()


def setup_logging(output, sample, keep_log, log_level="INFO"):
    """设置日志系统"""
    logger = setup_logger(f"{sample}_pipeline", output, log_level)

    # 兼容旧的进度跟踪系统
    log_path = os.path.join(output, "logs", f"{sample}log.txt")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def update_log_step(step):
        with open(log_path, "w") as f:
            f.write(f"{step}\n")
        return step

    if os.path.exists(log_path) and keep_log:
        try:
            with open(log_path, "r") as f:
                current_step = int(f.readline().strip())
        except Exception:
            current_step = update_log_step(0)
    else:
        current_step = update_log_step(0)

    return update_log_step, current_step, logger


def create_placeholder_step(step_name, paths_key):
    """创建占位符步骤函数，为跳过的步骤创建必要的目录结构"""
    def placeholder_func(**context):
        logger = setup_module_logger(f"placeholder.{step_name}")
        logger.info(f"跳过 {step_name} 步骤 (已禁用)，创建占位符目录")
        
        # 创建基本目录结构
        step_dir = os.path.join(context["paths"][paths_key], context["sample"])
        os.makedirs(step_dir, exist_ok=True)
        
        # 根据不同步骤创建必要的空文件
        if step_name == "virsorter":
            # VirSorter需要final-viral-score.tsv文件
            placeholder_file = os.path.join(step_dir, "final-viral-score.tsv")
            with open(placeholder_file, 'w') as f:
                f.write("# VirSorter disabled - placeholder file\n")
        elif step_name == "dvf":
            # DeepVirFinder需要virus_dvf.list文件
            placeholder_file = os.path.join(step_dir, "virus_dvf.list")
            with open(placeholder_file, 'w') as f:
                f.write("")  # 空文件
        elif step_name == "vibrant":
            # VIBRANT需要特定的目录结构和文件
            vibrant_subdir = os.path.join(step_dir, "VIBRANT_filtered_contigs", "VIBRANT_phages_filtered_contigs")
            os.makedirs(vibrant_subdir, exist_ok=True)
            placeholder_file = os.path.join(vibrant_subdir, "filtered_contigs.phages_combined.txt")
            with open(placeholder_file, 'w') as f:
                f.write("")  # 空文件
        elif step_name == "blastn":
            # BLASTN需要多个输出文件
            blastn_files = ["crass.out", "gpd.out", "gvd.out", "mgv.out", "ncbi.out"]
            for fname in blastn_files:
                placeholder_file = os.path.join(step_dir, fname)
                with open(placeholder_file, 'w') as f:
                    f.write("")  # 空文件
        elif step_name == "checkv_prefilter":
            # CheckV预过滤需要viral_contigs.list文件
            placeholder_file = os.path.join(step_dir, "viral_contigs.list")
            with open(placeholder_file, 'w') as f:
                f.write("")  # 空文件
        
        logger.info(f"{step_name} 占位符创建完成")
    
    return placeholder_func


def register_steps(config):
    """注册所有处理步骤，返回(步骤名, 函数, 是否启用)列表"""
    # 基础步骤（始终执行）
    steps = [
        ("fastp", run_fastp, True),
        ("host_removal", run_host_removal, True),
        ("assembly", run_assembly, True),
        ("vsearch", run_vsearch, True),
    ]
    
    # CheckV预过滤步骤（可选）
    use_checkv_prefilter = config.get_bool("combination", "use_checkv_prefilter", True)
    if use_checkv_prefilter:
        steps.append(("checkv_prefilter", run_checkv_prefilter, True))
    else:
        steps.append(("checkv_prefilter", create_placeholder_step("checkv_prefilter", "checkv_prefilter"), True))
    
    # 可选的病毒检测步骤（根据配置决定是否执行）
    virus_detection_steps = [
        ("virsorter", run_virsorter, "virsorter", config.get_bool("combination", "use_virsorter", True)),
        ("dvf", run_dvf, "dvf", config.get_bool("combination", "use_dvf", True)),
        ("vibrant", run_vibrant, "vibrant", config.get_bool("combination", "use_vibrant", True)),
        ("blastn", run_blastn, "blastn", config.get_bool("combination", "use_blastn", True)),
    ]
    
    for step_name, real_func, paths_key, enabled in virus_detection_steps:
        if enabled:
            steps.append((step_name, real_func, True))
        else:
            # 创建占位符函数以确保目录结构存在
            steps.append((step_name, create_placeholder_step(step_name, paths_key), True))
    
    # 后续处理步骤（始终执行）
    final_steps = [
        ("combination", run_combination, True),
        ("checkv", run_checkv, True),
        ("high_quality", high_quality_output, True),
        ("busco_filter", run_busco_filter, True),
    ]
    
    # 合并所有步骤
    steps.extend(final_steps)
    
    return steps


def build_context(args):
    sample1 = get_sample_name(args.input1.split("/")[-1])
    sample2 = get_sample_name(args.input2.split("/")[-1])
    if not sample1 or not sample2:
        raise ValueError("输入文件名解析失败")
    sample = sample1[0:-2]
    host_list = args.host.split(",") if args.host else None
    steps_name = [
        "trimmed",
        "host_removed",
        "assembly",
        "vsearch",
        "checkv_prefilter",
        "virsorter",
        "dvf",
        "vibrant",
        "blastn",
        "combination",
        "checkv",
        "high_quality",
        "busco_filter",
    ]
    paths = get_paths(args.output, steps_name)
    return {
        "output": args.output,
        "threads": args.threads,
        "input1": args.input1,
        "input2": args.input2,
        "sample1": sample1,
        "sample2": sample2,
        "sample": sample,
        "host_list": host_list,
        "db": args.db,
        "paths": paths,
    }


def main():
    args = parameter_input()
    config = Config(args.config)

    # 配置验证
    if args.validate_config:
        try:
            # 检查所有必须的软件路径
            for section in ["software", "parameters", "environment", "database"]:
                section_config = getattr(config, section, {})
                for key, value in section_config.items():
                    if not value:
                        raise ValueError(f"配置项 {section}.{key} 为空")
            print("配置验证通过!")
            sys.exit(0)
        except Exception as e:
            print(f"配置验证失败: {e}")
            sys.exit(1)

    context = build_context(args)
    context["config"] = config
    update_log, current_step, logger = setup_logging(
        context["output"], context["sample"], args.keep_log, args.log_level
    )

    # 记录启动信息
    logger.info("GutMicrobe Virus Pipeline 启动")
    logger.info(f"输入文件1: {args.input1}")
    logger.info(f"输入文件2: {args.input2}")
    logger.info(f"输出目录: {args.output}")
    logger.info(f"线程数: {args.threads}")
    logger.info(f"数据库目录: {args.db}")

    # 获取步骤列表
    steps = register_steps(config)
    
    # 记录病毒检测工具配置状态
    tool_status = []
    for tool in ['blastn', 'virsorter', 'dvf', 'vibrant', 'checkv_prefilter']:
        enabled = config.get_bool("combination", f"use_{tool}", True)
        status = "启用" if enabled else "禁用(占位符)"
        tool_status.append(f"{tool}({status})")
    logger.info(f"病毒检测工具状态: {', '.join(tool_status)}")
    logger.info(f"总步骤数: {len(steps)}")

    # 步骤执行主循环
    for idx, (step_name, func, enabled) in enumerate(steps, 1):
        if current_step < idx:
            try:
                logger.info(f"开始执行步骤 {idx}/{len(steps)}: {step_name}")
                step_context = context.copy()
                step_context["logger"] = logger

                # 执行步骤
                func(**step_context)

                logger.info(f"步骤 {idx} 完成: {step_name}")
                current_step = update_log(idx)

            except Exception as e:
                logger.error(f"步骤 {idx} 失败: {step_name} - {str(e)}")
                raise

    logger.info("所有步骤完成")
    if args.remove_inter_result:
        logger.info("清理中间结果文件")
        remove_inter_result(context["output"])
    logger.info("Pipeline 成功完成")


if __name__ == "__main__":
    main()
