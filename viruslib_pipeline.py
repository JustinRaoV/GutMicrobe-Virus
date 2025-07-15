import argparse
import os
import sys
from core.logger import create_logger
from core.config_manager import get_config
from utils.paths import get_paths
from modules.viruslib import (
    run_merge_contigs,
    run_vclust_dedup,
    run_phabox2_prediction,
    run_gene_annotation,
    run_cdhit_dedup,
    run_taxonomy_annotation,
    run_eggnog,
)


def parameter_input():
    parser = argparse.ArgumentParser(description="GutMicrobe VirusLib Pipeline")
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
    parser.add_argument(
        "-t", "--threads", type=int, default=1, help="Number of threads"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory (default: config.ini [paths] viruslib_dir)",
    )
    parser.add_argument(
        "--db",
        help="Database directory",
    )
    return parser.parse_args()


def setup_logging(output, sample, log_level="INFO"):
    """设置日志系统"""
    logger, error_handler = create_logger(output, sample, log_level)

    # 兼容旧的进度跟踪系统
    log_path = os.path.join(output, "logs", f"{sample}log.txt")

    def update_log_step(step):
        with open(log_path, "w") as f:
            f.write(f"{step}\n")
        return step

    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                current_step = int(f.readline().strip())
        except Exception:
            current_step = update_log_step(0)
    else:
        current_step = update_log_step(0)

    return update_log_step, current_step, logger, error_handler


def register_steps():
    """注册所有处理步骤，返回(步骤名, 函数)列表"""
    return [
        ("merge_contigs", run_merge_contigs),
        ("vclust_dedup", run_vclust_dedup),
        ("phabox2", run_phabox2_prediction),
        ("gene_annotation", run_gene_annotation),
        ("cdhit_dedup", run_cdhit_dedup),
        ("taxonomy_annotation", run_taxonomy_annotation),
        ("eggnog", run_eggnog),
    ]


def build_context(args, config):
    """构建执行上下文"""
    steps = register_steps()
    steps_name = [name for name, _ in steps]
    paths = get_paths(args.output, steps_name)
    return {
        "paths": paths,
        "config": config,
        "threads": args.threads,
        "busco_dir": os.path.join(config["paths"]["result_dir"], "13.busco_filter"),
        "viruslib_dir": args.output,
        "db": args.db,
    }


def main():
    args = parameter_input()
    config = get_config(args.config)

    # 配置验证
    if args.validate_config:
        try:
            # 检查所有必须的软件路径
            for section in ["software", "parameters"]:
                for key in config[section]:
                    value = config[section][key]
                    if not value:
                        raise ValueError(f"配置项 {section}.{key} 为空")
            print("配置验证通过!")
            sys.exit(0)
        except Exception as e:
            print(f"配置验证失败: {e}")
            sys.exit(1)

    context = build_context(args, config)
    update_log, current_step, logger, error_handler = setup_logging(
        context["viruslib_dir"], "viruslib", args.log_level
    )

    # 记录启动信息
    logger.info("GutMicrobe VirusLib Pipeline 启动")
    logger.info(f"输出目录: {context['viruslib_dir']}")
    logger.info(f"线程数: {context['threads']}")

    steps = register_steps()
    logger.info(f"总步骤数: {len(steps)}")

    # 步骤执行主循环
    for idx, (step_name, func) in enumerate(steps, 1):
        if current_step < idx:
            try:
                logger.step_start(step_name, idx, len(steps))

                # 将执行器添加到context中
                step_context = context.copy()
                step_context["logger"] = logger

                # 执行步骤
                func(**step_context)

                logger.step_complete(step_name, idx)
                current_step = update_log(idx)

            except Exception as e:
                logger.step_failed(step_name, idx, str(e))
                raise

    logger.info("所有步骤完成")
    logger.info("VirusLib Pipeline 成功完成")


if __name__ == "__main__":
    main()
