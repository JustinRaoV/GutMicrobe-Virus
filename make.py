#!/usr/bin/env python3
"""批量脚本生成 - 支持 SLURM/CFFF 两种模式"""
import argparse
import os
import sys
import yaml
import re


def _cfg_get(config, path, default=None):
    """安全读取嵌套配置: _cfg_get(cfg, ("batch", "threads"), 8)"""
    cur = config
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_read_pairs(input_dir):
    """获取配对的测序文件"""
    files = sorted([f for f in os.listdir(input_dir) if f.endswith((".fq.gz", ".fastq.gz", ".fq", ".fastq"))])
    pairs = []
    # 匹配 _1, _R1, .1, .R1 后跟扩展名
    # Group 1: Base name
    # Group 2: Suffix (_1, _R1, .1, .R1)
    # Group 3: Extension (.fq.gz, .fastq, etc)
    pattern = re.compile(r"^(.*)(_1|_R1|\.1|\.R1)(\.f(ast)?q(\.gz)?)$")
    
    for f in files:
        match = pattern.match(f)
        if match:
            base = match.group(1)
            suffix = match.group(2)
            ext = match.group(3)
            
            # 构建 R2 文件名
            if "1" in suffix:
                suffix_r2 = suffix.replace("1", "2")
                r2_name = f"{base}{suffix_r2}{ext}"
                r1_path = os.path.join(input_dir, f)
                r2_path = os.path.join(input_dir, r2_name)
                
                if os.path.exists(r2_path):
                    pairs.append((r1_path, r2_path))
    return pairs


def get_contig_files(input_dir):
    """获取contigs文件列表"""
    return [os.path.join(input_dir, f) for f in sorted(os.listdir(input_dir))
            if f.endswith((".fa", ".fasta", ".fna"))]


def write_script(path, content):
    """写入脚本文件并添加执行权限"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, 0o755)


def get_short_name(sample_name, max_len=12):
    """智能缩短样本名称"""
    if len(sample_name) <= max_len:
        return sample_name
    # 尝试取首尾部分
    return sample_name[:6] + sample_name[-6:]


def get_slurm_header(sample_name, threads, mem, partition, log_dir, config):
    """生成 SLURM 作业头"""
    return f"""#!/bin/bash
#SBATCH --job-name=v_{sample_name}
#SBATCH --output={log_dir}/{sample_name}.out
#SBATCH --error={log_dir}/{sample_name}.err
#SBATCH --nodes=1
#SBATCH --ntasks-per-node={threads}
#SBATCH --mem={mem}G
# 注意: 按需求不在脚本内指定partition/queue
"""


def get_cfff_header(sample_name, threads, mem, log_dir, config):
    """生成 CFFF 环境作业头"""
    env_config = config.get("env", {})
    module_load = env_config.get(
        "module_load",
        "module load CentOS/7.9/singularity/3.9.2\nmodule load CentOS/7.9/Anaconda3/24.5.0",
    )
    activate_cmd = env_config.get(
        "activate_cmd",
        "source /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/bin/activate",
    )

    return f"""#!/bin/bash
# 样本: {sample_name}

{module_load}
{activate_cmd}
"""


def generate_scripts(args):
    """生成批量分析脚本"""
    # 转换为绝对路径
    script_dir_abs = os.path.abspath(os.path.dirname(__file__))
    run_upstream_script = os.path.join(script_dir_abs, "run_upstream.py")
    config_path_abs = os.path.abspath(args.config)
    output_dir_abs = os.path.abspath(args.output)
    
    # 加载配置
    config = load_yaml(config_path_abs)

    # 从配置读取批量参数默认值 (命令行可覆盖)
    batch_cfg = config.get("batch", {})
    scheduler = args.scheduler or batch_cfg.get("scheduler", "slurm")
    threads = args.threads if args.threads is not None else int(batch_cfg.get("threads", 8))
    mem = args.mem if args.mem is not None else int(batch_cfg.get("mem", 60))
    host_default = batch_cfg.get("host")
    host = args.host if args.host is not None else host_default
    
    # 获取输入文件
    if args.mode == "reads":
        samples = get_read_pairs(args.input)
        if not samples:
            print(f"错误: 在 {args.input} 中未找到配对的测序文件")
            sys.exit(1)
    else:  # contigs
        samples = [(f,) for f in get_contig_files(args.input)]
        if not samples:
            print(f"错误: 在 {args.input} 中未找到 contigs 文件")
            sys.exit(1)
    
    print(f"找到 {len(samples)} 个样本")
    print(f"作业调度系统: {str(scheduler).upper()}")
    
    # 生成脚本目录和日志目录（放在当前目录而非output目录）
    script_dir = os.path.join(script_dir_abs, "scripts")
    log_dir = os.path.join(script_dir_abs, "logs")
    os.makedirs(script_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    
    # 生成各样本脚本
    script_files = []
    for i, files in enumerate(samples, 1):
        if args.mode == "reads":
            r1, r2 = files
            # 尽量鲁棒地从R1文件名推断样本名
            sample_name = os.path.basename(r1)
            sample_name = re.sub(r"(_1|_R1|\.1|\.R1)(\.f(ast)?q(\.gz)?)$", "", sample_name)
            cmd = f"python {run_upstream_script} {r1} {r2} --start-from reads"
            if host:
                cmd += f" --host {host}"
        else:  # contigs
            contig_file = files[0]
            sample_name = os.path.splitext(os.path.basename(contig_file))[0]
            cmd = f"python {run_upstream_script} {contig_file} --start-from contigs"

        cmd += f" -o {output_dir_abs} -t {threads}"
        cmd += f" --config {config_path_abs}"

        # 生成作业头
        if scheduler == "slurm":
            header = get_slurm_header(sample_name, threads, mem, None, log_dir, config)
        elif scheduler == "cfff":
            header = get_cfff_header(sample_name, threads, mem, log_dir, config)
        else:
            raise ValueError(f"未知 scheduler={scheduler}，仅支持 slurm/cfff")

        script_content = f"""{header}
# 样本: {sample_name}
# 生成时间: $(date)

{cmd}
"""

        script_path = os.path.join(script_dir, f"run_{i:03d}_{sample_name}.job.sh")
        write_script(script_path, script_content)
        script_files.append(script_path)
        print(f"  [{i}] {sample_name}")

    # 生成批量提交脚本
    if scheduler == "slurm":
        submit_script = os.path.join(script_dir_abs, "submit_jobs.txt")
        with open(submit_script, "w") as f:
            for s in script_files:
                f.write(f"sbatch {s}\n")

        print(f"\n已生成 {len(samples)} 个样本脚本到: {script_dir}")
        print(f"批量提交列表: {submit_script}")
        print(f"\n运行方式:")
        print(f"  提交所有作业: while read line; do $line; done < {submit_script}")
        return

    submit_script = os.path.join(script_dir_abs, "submit_all.sh")
    submit_content = "#!/bin/bash\n"
    submit_content += f"# 批量运行脚本 - {str(scheduler).upper()}\n\n"

    # cfff 模式默认本地 bash 运行即可
    submit_cmd = "bash"

    for s in script_files:
        submit_content += f"{submit_cmd} {s}\n"

    write_script(submit_script, submit_content)
    print(f"\n已生成 {len(samples)} 个样本脚本到: {script_dir}")
    print(f"日志输出目录: {log_dir}")
    print(f"批量提交脚本: {submit_script}")
    print(f"\n运行方式:")
    print(f"  单个样本: {submit_cmd} {script_files[0]}")
    print(f"  所有样本: bash {submit_script}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="批量生成病毒组分析脚本（支持SLURM/CFFF）")
    parser.add_argument("input", help="输入目录(测序文件或contigs文件)")
    parser.add_argument("--mode", required=True, choices=["reads", "contigs"],
                       help="输入模式: reads(测序文件) 或 contigs(组装文件)")
    parser.add_argument("-o", "--output", default="result", help="输出目录 (默认: result)")
    parser.add_argument("-t", "--threads", type=int, default=None, help="线程数(默认从config.yaml读取)")
    parser.add_argument("--mem", type=int, default=None, help="内存(GB)(默认从config.yaml读取)")
    parser.add_argument("--host", default=None, help="宿主名称(逗号分隔,reads模式需要；默认从config.yaml读取)")
    parser.add_argument("--config", help="配置文件 (默认: make.py所在目录的config/config.yaml)")
    parser.add_argument("--scheduler", default=None, choices=["slurm", "cfff"],
                       help="作业调度系统(默认从config.yaml读取): slurm, cfff")
    
    args = parser.parse_args()
    
    # 设置默认配置文件路径
    if not args.config:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.config = os.path.join(script_dir, "config", "config.yaml")
    
    # 转换输入目录为绝对路径
    args.input = os.path.abspath(args.input)
    
    # 验证参数
    if not os.path.isdir(args.input):
        parser.error(f"输入目录不存在: {args.input}")
    # reads模式 host 优先走配置；这里不强制要求命令行提供
    if not os.path.isfile(args.config):
        parser.error(f"配置文件不存在: {args.config}")
    
    return args


def main():
    try:
        generate_scripts(parse_args())
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
