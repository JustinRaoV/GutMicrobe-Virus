import argparse
import os
import sys
from utils.tools import *
from modules import *
from utils.paths import get_paths
from core.logger import create_logger
from core.config_manager import get_config
from core.executor import get_executor


def parameter_input():
    parser = argparse.ArgumentParser(description='GutMicrobe Virus Pipeline')
    parser.add_argument('input1', help='Path to the fastq(.gz) file of read1')
    parser.add_argument('input2', help='Path to the fastq(.gz) file of read2')
    parser.add_argument('--host', help='Bowtie2 index name(s), comma separated', default=None)
    parser.add_argument('-o', '--output', help='Output directory', default=os.path.join(os.getcwd(), 'result'))
    parser.add_argument('-t', '--threads', type=int, help='Number of threads', default=1)
    parser.add_argument('-r', '--remove_inter_result', action='store_true', help='Remove intermediate results', default=False)
    parser.add_argument('-k', '--keep_log', action='store_true', help='Resume interrupted run', default=True)
    parser.add_argument('--db', help='Path to database directory', default="/public/home/TonyWuLab/raojun/db")
    parser.add_argument('--config', help='Path to config file', default="config.ini")
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Log level')
    parser.add_argument('--validate-config', action='store_true', help='Validate configuration and exit')
    return parser.parse_args()


def setup_logging(output, sample, keep_log, log_level="INFO"):
    """设置日志系统"""
    logger, error_handler = create_logger(output, sample, log_level)
    
    # 兼容旧的进度跟踪系统
    log_path = os.path.join(output, "logs", f"{sample}log.txt")
    
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
    
    return update_log_step, current_step, logger, error_handler


def register_steps():
    """注册所有处理步骤，返回(步骤名, 函数)列表"""
    return [
        ("fastp", run_fastp),
        ("host_removal", run_host_removal),
        ("assembly", run_assembly),
        ("vsearch", run_vsearch),
        ("checkv_prefilter", run_checkv_prefilter),
        ("virsorter", run_virsorter),
        ("dvf", run_dvf),
        ("vibrant", run_vibrant),
        ("blastn", run_blastn),
        ("combination", run_combination),
        ("checkv", run_checkv),
        ("high_quality", high_quality_output),
        ("busco_filter", run_busco_filter),
    ]


def build_context(args):
    sample1 = get_sample_name(args.input1.split('/')[-1])
    sample2 = get_sample_name(args.input2.split('/')[-1])
    if not sample1 or not sample2:
        raise ValueError("输入文件名解析失败")
    sample = sample1[0: -2]
    host_list = args.host.split(',') if args.host else None
    steps_name = [
        "trimmed", "host_removed", "assembly", "vsearch", "checkv_prefilter", "virsorter", "dvf", "vibrant", "blastn", "combination", "checkv", "high_quality", "busco_filter"
    ]
    paths = get_paths(args.output, steps_name)
    return {
        'output': args.output,
        'threads': args.threads,
        'input1': args.input1,
        'input2': args.input2,
        'sample1': sample1,
        'sample2': sample2,
        'sample': sample,
        'host_list': host_list,
        'db': args.db,
        'paths': paths
    }


def main():
    args = parameter_input()
    config = get_config(args.config)
    
    # 配置验证
    if args.validate_config:
        try:
            # 检查所有必须的软件路径
            for section in ['software', 'parameters', 'environment', 'database']:
                for key in config[section]:
                    value = config[section][key]
                    if not value:
                        raise ValueError(f"配置项 {section}.{key} 为空")
            print("配置验证通过!")
            sys.exit(0)
        except Exception as e:
            print(f"配置验证失败: {e}")
            sys.exit(1)
    
    context = build_context(args)
    update_log, current_step, logger, error_handler = setup_logging(
        context['output'], context['sample'], args.keep_log, args.log_level
    )
    
    # 初始化执行器
    executor = get_executor(logger, error_handler)
    
    # 记录启动信息
    logger.info("GutMicrobe Virus Pipeline 启动")
    logger.info(f"输入文件1: {args.input1}")
    logger.info(f"输入文件2: {args.input2}")
    logger.info(f"输出目录: {args.output}")
    logger.info(f"线程数: {args.threads}")
    logger.info(f"数据库目录: {args.db}")
    
    steps = register_steps()
    logger.info(f"总步骤数: {len(steps)}")

    # 步骤执行主循环
    for idx, (step_name, func) in enumerate(steps, 1):
        if current_step < idx:
            try:
                logger.step_start(step_name, idx, len(steps))
                
                # 将执行器添加到context中
                step_context = context.copy()
                step_context['executor'] = executor
                step_context['logger'] = logger
                step_context['error_handler'] = error_handler
                
                # 执行步骤
                func(**step_context)
                
                logger.step_complete(step_name, idx)
                current_step = update_log(idx)
                
            except Exception as e:
                logger.step_failed(step_name, idx, str(e))
                raise

    logger.info("所有步骤完成")
    if args.remove_inter_result:
        logger.info("清理中间结果文件")
        remove_inter_result(context['output'])
    logger.info("Pipeline 成功完成")
    print("Pipeline finished successfully.")


if __name__ == '__main__':
    main()
    