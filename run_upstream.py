import argparse
import os
from software.tools import *
from software.filter import *
from software.virus_find import *
from software.paths import get_paths


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
    return parser.parse_args()


def setup_logging(output, sample, keep_log):
    os.makedirs(os.path.join(output, "logs"), exist_ok=True)
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
    return update_log_step, current_step


def register_steps():
    """注册所有处理步骤，返回(步骤名, 函数)列表"""
    return [
        ("fastp", run_fastp),
        ("host_removal", run_host_removal),
        ("assembly", run_assembly),
        ("vsearch", run_vsearch_1),
        ("virsorter", run_virsorter),
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
        "trimmed", "host_removed", "assembly", "vsearch", "virsorter", "blastn", "combination", "checkv", "high_quality", "busco_filter"
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
    context = build_context(args)
    update_log, current_step = setup_logging(context['output'], context['sample'], args.keep_log)
    steps = register_steps()

    # 步骤执行主循环
    for idx, (step_name, func) in enumerate(steps, 1):
        if current_step < idx:
            # 只传递 context 字典，所有函数都需支持 **context
            func(**context)
            current_step = update_log(idx)

    print("all steps finished")
    if args.remove_inter_result:
        remove_inter_result(context['output'])
    print("Pipeline finished successfully.")


if __name__ == '__main__':
    main()
    