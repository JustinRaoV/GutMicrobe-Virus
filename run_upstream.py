#!/usr/bin/env python3
"""上游分析主流程"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import load_config, is_tool_enabled
from src.logger import setup_logger
from src.utils import get_sample_name, mark_step_done, is_step_done, ensure_dir, get_path, get_step_timestamp, invalidate_dependent_steps
from src.pipeline.preprocessing import run_fastp, run_host_removal, run_assembly, run_vsearch
from src.pipeline.virus_detection import (
    run_checkv_prefilter, run_virsorter, run_dvf, run_vibrant, run_blastn, get_enabled_tools
)
from src.pipeline.quality import run_combination, run_checkv, run_high_quality, run_busco


def parse_args():
    p = argparse.ArgumentParser(description="病毒组上游分析流程")
    p.add_argument("input1", nargs="?", help="Read1文件或contigs文件")
    p.add_argument("input2", nargs="?", help="Read2文件(contigs模式下不需要)")
    p.add_argument("--start-from", default="reads", choices=["reads", "contigs"], 
                   help="起始步骤: reads(从测序数据开始) 或 contigs(从组装结果开始)")
    p.add_argument("--host", help="宿主基因组(逗号分隔)", default=None)
    p.add_argument("-o", "--output", default="result", help="输出目录")
    p.add_argument("-t", "--threads", type=int, default=1, help="线程数")
    p.add_argument("--db", default="~/db", help="数据库目录")
    p.add_argument("--config", default="config/config.yaml", help="配置文件")
    p.add_argument("--log-level", default="INFO", help="日志级别")
    p.add_argument("--force", action="store_true", help="强制重跑所有步骤(忽略状态文件)")
    
    args = p.parse_args()
    
    # 验证输入参数
    if args.start_from == "reads" and (not args.input1 or not args.input2):
        p.error("从reads开始需要提供 input1 和 input2")
    if args.start_from == "contigs" and not args.input1:
        p.error("从contigs开始需要提供 contigs 文件路径")
    
    return args


def get_step_dirs(output):
    """生成各步骤目录"""
    steps = ["trimmed", "host_removed", "assembly", "vsearch", "checkv_prefilter", "virsorter", 
             "dvf", "vibrant", "blastn", "combination", "checkv", "high_quality", "busco_filter"]
    return {s: os.path.join(output, f"{i+1}.{s}") for i, s in enumerate(steps)}


def build_context(args, config):
    """构建流程上下文"""
    # 根据起始模式确定样本名
    if args.start_from == "reads":
        sample = get_sample_name(os.path.basename(args.input1))[:-2]
    else:  # contigs模式
        sample = os.path.splitext(os.path.basename(args.input1))[0]
    
    ctx = {
        "sample": sample,
        "threads": args.threads,
        "db": args.db,
        "paths": get_step_dirs(args.output),
        "config": config,
        "logger": setup_logger(sample, args.output, args.log_level),
        "output_dir": args.output,
        "force": args.force,
        "start_from": args.start_from
    }
    
    # reads模式需要的额外信息
    if args.start_from == "reads":
        ctx["sample1"] = get_sample_name(os.path.basename(args.input1))
        ctx["sample2"] = get_sample_name(os.path.basename(args.input2))
        ctx["input1"] = args.input1
        ctx["input2"] = args.input2
        ctx["host_list"] = args.host.split(",") if args.host else []
    else:  # contigs模式
        ctx["contigs_file"] = args.input1
    
    return ctx


def run_pipeline(args):
    """运行完整流程"""
    config = load_config(args.config)
    ctx = build_context(args, config)
    
    ctx["logger"].info(f"样本: {ctx['sample']}")
    ctx["logger"].info(f"起始模式: {ctx['start_from']}")
    ctx["logger"].info(f"检测工具: {', '.join(get_enabled_tools(config))}")
    if ctx["force"]:
        ctx["logger"].info("强制模式: 将重跑所有步骤")
    
    # 从 contigs 开始时，准备输入文件
    if ctx["start_from"] == "contigs":
        import shutil
        assembly_dir = ensure_dir(get_path(ctx, "assembly"))
        target_file = os.path.join(assembly_dir, "final.contigs.fa")
        shutil.copy2(ctx["contigs_file"], target_file)
        ctx["logger"].info(f"已复制 contigs 文件到: {target_file}")
        mark_step_done(ctx["output_dir"], ctx["sample"], "trimmed")
        mark_step_done(ctx["output_dir"], ctx["sample"], "host_removed")
        mark_step_done(ctx["output_dir"], ctx["sample"], "assembly")
    
    # 定义步骤依赖关系
    step_dependencies = {
        "trimmed": [],
        "host_removed": ["trimmed"],
        "assembly": ["host_removed"],
        "vsearch": ["assembly"],
        "checkv_prefilter": ["vsearch"],
        "virsorter": ["checkv_prefilter"],  # 依赖预过滤结果
        "dvf": ["checkv_prefilter"],
        "vibrant": ["checkv_prefilter"],
        "blastn": ["checkv_prefilter"],
        "combination": ["virsorter", "dvf", "vibrant", "blastn", "checkv_prefilter"],
        "checkv": ["combination"],
        "high_quality": ["checkv"],
        "busco_filter": ["high_quality"],
    }
    
    # 定义流程 (步骤名, 函数, 步骤标识符, 工具名[可选])
    steps = [
        ("质控", run_fastp, "trimmed"),
        ("去宿主", run_host_removal, "host_removed"),
        ("组装", run_assembly, "assembly"),
        ("长度过滤", run_vsearch, "vsearch"),
        ("CheckV预过滤", run_checkv_prefilter, "checkv_prefilter", "checkv_prefilter"),
        ("VirSorter", run_virsorter, "virsorter", "virsorter"),
        ("DeepVirFinder", run_dvf, "dvf", "dvf"),
        ("VIBRANT", run_vibrant, "vibrant", "vibrant"),
        ("BLASTN", run_blastn, "blastn", "blastn"),
        ("结果整合", run_combination, "combination"),
        ("CheckV质控", run_checkv, "checkv"),
        ("高质量筛选", run_high_quality, "high_quality"),
        ("BUSCO过滤", run_busco, "busco_filter"),
    ]
    
    # 执行
    for i, step_info in enumerate(steps, 1):
        name, func, step_key = step_info[:3]
        tool_name = step_info[3] if len(step_info) > 3 else None
        
        # 跳过禁用的工具
        if tool_name and not is_tool_enabled(config, tool_name):
            ctx["logger"].info(f"[{i}/{len(steps)}] {name} - 已禁用,跳过")
            continue
        
        # 检查依赖关系：如果依赖步骤比当前步骤新，需要重跑
        need_rerun = False
        if not ctx["force"] and is_step_done(ctx["output_dir"], ctx["sample"], step_key):
            current_timestamp = get_step_timestamp(ctx["output_dir"], ctx["sample"], step_key)
            dependencies = step_dependencies.get(step_key, [])
            
            for dep_step in dependencies:
                dep_timestamp = get_step_timestamp(ctx["output_dir"], ctx["sample"], dep_step)
                if dep_timestamp and current_timestamp and dep_timestamp > current_timestamp:
                    need_rerun = True
                    ctx["logger"].info(f"[{i}/{len(steps)}] {name} - 依赖步骤已更新,需要重跑")
                    break
            
            if not need_rerun:
                ctx["logger"].info(f"[{i}/{len(steps)}] {name} - 已完成,跳过")
                continue
        
        # 执行步骤
        ctx["logger"].info(f"[{i}/{len(steps)}] {name}")
        try:
            func(ctx)
            mark_step_done(ctx["output_dir"], ctx["sample"], step_key)
            ctx["logger"].info(f"[{i}/{len(steps)}] {name} - 完成")
        except Exception as e:
            ctx["logger"].error(f"{name}失败: {e}")
            raise
    
    ctx["logger"].info("流程完成!")


def main():
    try:
        run_pipeline(parse_args())
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
