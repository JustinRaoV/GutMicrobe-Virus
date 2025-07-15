#!/usr/bin/env python3
"""
下游分析模块

使用coverm进行contig和基因丰度分析。
"""

import argparse
import os
import sys
from utils.tools import *
from modules.abundance_analysis import run_abundance_analysis
from core.config_manager import get_config
from utils.common import create_simple_logger


def parameter_input():
    parser = argparse.ArgumentParser(
        description="GutMicrobe Virus Downstream Analysis Pipeline"
    )
    parser.add_argument(
        "input1",
        help="Path to the fastq(.gz) file of read1 (for sample name extraction)",
    )
    parser.add_argument(
        "input2",
        help="Path to the fastq(.gz) file of read2 (for sample name extraction)",
    )
    parser.add_argument(
        "--upstream-result",
        help="Path to upstream analysis result directory",
        required=True,
    )
    parser.add_argument(
        "--viruslib-result",
        help="Path to viruslib pipeline result directory",
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory",
        default=os.path.join(os.getcwd(), "abundance_result"),
    )
    parser.add_argument(
        "-t", "--threads", type=int, help="Number of threads", default=1
    )
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


def build_context(args):
    """构建上下文信息"""
    # 从输入文件名获取样本名称
    sample1 = get_sample_name(args.input1.split("/")[-1])
    sample2 = get_sample_name(args.input2.split("/")[-1])
    if not sample1 or not sample2:
        raise ValueError("输入文件名解析失败")
    sample = sample1[0:-2]

    # 自动找到host_removed下的fastq文件
    host_removed_dir = os.path.join(args.upstream_result, "2.host_removed", sample)
    if not os.path.exists(host_removed_dir):
        raise ValueError(f"Host removed directory not found: {host_removed_dir}")

    # 查找host_removed后的fastq文件
    fastq_files = [f for f in os.listdir(host_removed_dir) if f.endswith(".fq.gz")]
    if len(fastq_files) != 2:
        raise ValueError(
            f"Expected 2 fastq files in {host_removed_dir}, found {len(fastq_files)}"
        )

    # 按文件名排序，确保R1在前，R2在后
    fastq_files.sort()
    input1 = os.path.join(host_removed_dir, fastq_files[0])
    input2 = os.path.join(host_removed_dir, fastq_files[1])

    # 自动找到viruslib的contig文件（vclust_dedup生成的viruslib_nr.fa）
    viruslib_contig_path = os.path.join(
        args.viruslib_result, "2.vclust_dedup", "viruslib_nr.fa"
    )
    if not os.path.exists(viruslib_contig_path):
        raise ValueError(f"Virus library contig file not found: {viruslib_contig_path}")

    # 自动找到viruslib的gene文件（cdhit_dedup生成的gene_cdhit.fq）
    viruslib_gene_path = os.path.join(
        args.viruslib_result, "5.cdhit_dedup", "gene_cdhit.fq"
    )
    if not os.path.exists(viruslib_gene_path):
        raise ValueError(f"Virus library gene file not found: {viruslib_gene_path}")

    return {
        "output": args.output,
        "threads": args.threads,
        "input1": input1,
        "input2": input2,
        "sample": sample,
        "viruslib_contig_path": viruslib_contig_path,
        "viruslib_gene_path": viruslib_gene_path,
        "upstream_result": args.upstream_result,
        "viruslib_result": args.viruslib_result,
    }


def main():
    args = parameter_input()
    config = get_config(args.config)

    # 配置验证
    if args.validate_config:
        try:
            # 检查coverm配置
            if "coverm" not in config["software"]:
                raise ValueError("配置文件中缺少coverm软件路径")
            if "coverm_params" not in config["parameters"]:
                raise ValueError("配置文件中缺少coverm参数配置")

            # 检查输入文件是否存在
            if not os.path.exists(args.input1):
                raise ValueError(f"输入文件1不存在: {args.input1}")
            if not os.path.exists(args.input2):
                raise ValueError(f"输入文件2不存在: {args.input2}")

            # 检查上游分析结果目录是否存在
            if not os.path.exists(args.upstream_result):
                raise ValueError(f"上游分析结果目录不存在: {args.upstream_result}")

            # 检查病毒库结果目录是否存在
            if not os.path.exists(args.viruslib_result):
                raise ValueError(f"病毒库分析结果目录不存在: {args.viruslib_result}")

            print("配置验证通过!")
            sys.exit(0)
        except Exception as e:
            print(f"配置验证失败: {e}")
            sys.exit(1)

    context = build_context(args)
    logger = create_simple_logger("downstream", args.log_level)

    # 记录启动信息
    logger.info("GutMicrobe Virus Downstream Analysis Pipeline 启动")
    logger.info(f"样本名称: {context['sample']}")
    logger.info(f"原始输入文件1: {args.input1}")
    logger.info(f"原始输入文件2: {args.input2}")
    logger.info(f"上游分析结果目录: {args.upstream_result}")
    logger.info(f"病毒库分析结果目录: {args.viruslib_result}")
    logger.info(f"自动找到的host_removed文件1: {context['input1']}")
    logger.info(f"自动找到的host_removed文件2: {context['input2']}")
    logger.info(f"自动找到的contig文件: {context['viruslib_contig_path']}")
    logger.info(f"自动找到的gene文件: {context['viruslib_gene_path']}")
    logger.info(f"输出目录: {args.output}")
    logger.info(f"线程数: {args.threads}")

    try:
        logger.info("开始丰度分析")

        # 将执行器添加到context中
        step_context = context.copy()

        # 执行丰度分析
        run_abundance_analysis(**step_context)

        logger.info("丰度分析完成")

    except Exception as e:
        logger.error(f"丰度分析失败: {e}")
        raise

    logger.info("下游分析完成")


if __name__ == "__main__":
    main()
