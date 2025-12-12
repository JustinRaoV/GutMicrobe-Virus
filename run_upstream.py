#!/usr/bin/env python3
"""上游分析主流程"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import load_config, is_tool_enabled
from src.logger import setup_logger
from src.utils import get_sample_name, save_checkpoint, load_checkpoint, ensure_dir, get_path
from src.pipeline.preprocessing import run_fastp, run_host_removal, run_assembly, run_vsearch
from src.pipeline.virus_detection import (
    run_virsorter, run_genomad, get_enabled_tools
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
    p.add_argument("--config", default="config/config.yaml", help="配置文件")
    p.add_argument("--log-level", default="INFO", help="日志级别")
    p.add_argument("--force", action="store_true", help="强制重跑所有步骤(忽略状态文件)")
    p.add_argument("--stage-reads", action="store_true", help="启用 reads staging (复制到本地目录)")
    
    args = p.parse_args()
    
    # 验证输入参数
    if args.start_from == "reads" and (not args.input1 or not args.input2):
        p.error("从reads开始需要提供 input1 和 input2")
    if args.start_from == "contigs" and not args.input1:
        p.error("从contigs开始需要提供 contigs 文件路径")
    
    return args


def get_step_dirs(output):
    """生成各步骤目录"""
    steps = ["trimmed", "host_removed", "assembly", "vsearch", "virsorter", 
             "genomad", "combination", "checkv", "high_quality", "busco_filter"]
    return {s: os.path.join(output, f"{i+1}.{s}") for i, s in enumerate(steps)}


def build_context(args, config):
    """构建流程上下文"""
    # 根据起始模式确定样本名
    if args.start_from == "reads":
        # 从R1文件名推断样本名，避免简单截断导致尾随"_"等问题
        r1_base = get_sample_name(os.path.basename(args.input1))
        for suffix in ("_R1", "_1", ".R1", ".1"):
            if r1_base.endswith(suffix):
                r1_base = r1_base[: -len(suffix)]
                break
        sample = r1_base.rstrip("_ .")
    else:  # contigs模式
        sample = os.path.splitext(os.path.basename(args.input1))[0]
    
    ctx = {
        "sample": sample,
        "threads": args.threads,
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
    
    # 覆盖配置中的 stage_reads 参数
    if args.stage_reads:
        if "parameters" not in config:
            config["parameters"] = {}
        config["parameters"]["stage_reads"] = True

    # 自动配置 Singularity 挂载路径
    if config.get('singularity', {}).get('enabled', False):
        binds = set(config.get('singularity', {}).get('binds', []))
        
        # 1. 添加输入文件所在目录 (仅当未启用 stage_reads 时)
        # 如果启用了 stage_reads，文件会被复制到工作目录，通常无需挂载原始目录
        # 但为了保险起见，我们还是挂载它，除非它导致问题
        input_files = []
        if args.start_from == "reads":
            input_files = [args.input1, args.input2]
        elif args.start_from == "contigs":
            input_files = [args.input1]
            
        for f in input_files:
            if f:
                binds.add(os.path.dirname(os.path.abspath(f)))
        
        # 2. 添加数据库目录
        # 优先使用 database.root，如果未定义则扫描所有数据库路径
        db_conf = config.get('database', {})
        if 'root' in db_conf:
            binds.add(os.path.abspath(os.path.expanduser(db_conf['root'])))
        else:
            for k, v in db_conf.items():
                if isinstance(v, str) and os.path.isabs(os.path.expanduser(v)):
                    binds.add(os.path.abspath(os.path.expanduser(v)))
        
        # 3. 添加 SIF 目录
        sif_dir = config.get('singularity', {}).get('sif_dir')
        if sif_dir:
            binds.add(os.path.abspath(os.path.expanduser(sif_dir)))

        # 4. 添加当前工作目录和输出目录 (确保 staging 目录和结果目录可见)
        binds.add(os.getcwd())
        binds.add(os.path.abspath(args.output))

        # 5. 智能去重 (保留父目录，移除子目录)
        # 例如: 有 /a 和 /a/b，只保留 /a
        sorted_paths = sorted([os.path.abspath(p) for p in binds if os.path.exists(p)], key=len)
        final_binds = []
        for p in sorted_paths:
            # 检查 p 是否是 final_binds 中某个路径的子目录
            is_subdir = False
            for parent in final_binds:
                if p.startswith(parent + os.sep) or p == parent:
                    is_subdir = True
                    break
            if not is_subdir:
                final_binds.append(p)
        
        config['singularity']['binds'] = final_binds
        ctx['logger'].info(f"Singularity 挂载路径: {final_binds}")

    return ctx


def run_pipeline(args):
    """运行完整流程"""
    config = load_config(args.config)
    ctx = build_context(args, config)
    
    ctx["logger"].info(f"样本: {ctx['sample']}")
    ctx["logger"].info(f"起始模式: {ctx['start_from']}")
    ctx["logger"].info(f"检测工具: {', '.join(get_enabled_tools(config))}")
    
    # 确定起始步骤
    if ctx["force"]:
        start_step = 1
        ctx["logger"].info("强制模式: 将从头开始运行")
    else:
        # 加载断点，获取上次成功完成的步骤
        last_completed = load_checkpoint(ctx["output_dir"], ctx["sample"])
        start_step = last_completed + 1
        if last_completed > 0:
            ctx["logger"].info(f"检测到断点: 上次完成到第{last_completed}步，将从第{start_step}步继续")
    
    # 从 contigs 开始时，准备输入文件
    if ctx["start_from"] == "contigs":
        import shutil
        assembly_dir = ensure_dir(get_path(ctx, "assembly"))
        target_file = os.path.join(assembly_dir, "final.contigs.fa")
        if not os.path.exists(target_file):
            shutil.copy2(ctx["contigs_file"], target_file)
            ctx["logger"].info(f"已复制 contigs 文件到: {target_file}")
        # contigs模式最少从第4步(vsearch)开始
        if start_step < 4:
            start_step = 4
    
    # 定义流程 (步骤名, 函数, 步骤标识符, 工具名[可选])
    steps = [
        ("质控", run_fastp, "trimmed"),
        ("去宿主", run_host_removal, "host_removed"),
        ("组装", run_assembly, "assembly"),
        ("长度过滤(≥1500bp)", run_vsearch, "vsearch"),
        ("VirSorter2", run_virsorter, "virsorter", "virsorter"),
        ("geNomad", run_genomad, "genomad", "genomad"),
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
        
        # 根据断点跳过已完成的步骤
        if i < start_step:
            ctx["logger"].info(f"[{i}/{len(steps)}] {name} - 已完成,跳过")
            continue
        
        # 执行步骤
        ctx["logger"].info(f"[{i}/{len(steps)}] {name}")
        try:
            func(ctx)
            save_checkpoint(ctx["output_dir"], ctx["sample"], i)
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
