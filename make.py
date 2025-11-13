#!/usr/bin/env python3
"""批量脚本生成 - 支持从测序文件或contigs文件批量生成分析脚本"""
import argparse
import os
import sys


def get_read_pairs(input_dir):
    """获取配对的测序文件"""
    files = sorted([f for f in os.listdir(input_dir) if f.endswith((".fq.gz", ".fastq.gz"))])
    pairs = []
    for f in files:
        if "_1.fq" in f or "_1.fastq" in f:
            r1 = os.path.join(input_dir, f)
            r2 = r1.replace("_1.fq", "_2.fq").replace("_1.fastq", "_2.fastq")
            if os.path.exists(r2):
                pairs.append((r1, r2))
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


def generate_scripts(args):
    """生成批量分析脚本"""
    # 转换为绝对路径
    script_dir_abs = os.path.abspath(os.path.dirname(__file__))
    run_upstream_script = os.path.join(script_dir_abs, "run_upstream.py")
    config_path_abs = os.path.abspath(args.config)
    output_dir_abs = os.path.abspath(args.output)
    db_path_abs = os.path.abspath(os.path.expanduser(args.db))
    
    # 获取输入文件（已经是绝对路径）
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
    
    # 生成脚本目录
    script_dir = os.path.join(output_dir_abs, "scripts")
    os.makedirs(script_dir, exist_ok=True)
    
    # 生成各样本脚本
    script_files = []
    for i, files in enumerate(samples, 1):
        if args.mode == "reads":
            r1, r2 = files
            sample_name = os.path.basename(r1).split("_1.")[0]
            cmd = f"python {run_upstream_script} {r1} {r2} --start-from reads"
            if args.host:
                cmd += f" --host {args.host}"
        else:  # contigs
            contig_file = files[0]
            sample_name = os.path.splitext(os.path.basename(contig_file))[0]
            cmd = f"python {run_upstream_script} {contig_file} --start-from contigs"
        
        cmd += f" -o {output_dir_abs} -t {args.threads}"
        cmd += f" --db {db_path_abs}"
        cmd += f" --config {config_path_abs}"
        
        script_path = os.path.join(script_dir, f"run_{i:03d}_{sample_name}.sh")
        write_script(script_path, f"""#!/bin/bash
# 样本: {sample_name}
{cmd}
""")
        script_files.append(script_path)
        print(f"  [{i}] {sample_name}")
    
    # 生成批量提交脚本
    submit_script = os.path.join(output_dir_abs, "submit_all.sh")
    write_script(submit_script, "#!/bin/bash\n" + "\n".join([f"bash {s}" for s in script_files]))
    
    print(f"\n已生成 {len(samples)} 个样本脚本到: {script_dir}")
    print(f"批量提交脚本: {submit_script}")
    print(f"\n运行方式:")
    print(f"  单个样本: bash {script_files[0]}")
    print(f"  所有样本: bash {submit_script}")
    print(f"\n所有路径已使用绝对路径，可以在任意目录下执行脚本")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="批量生成病毒组分析脚本")
    parser.add_argument("input", help="输入目录(测序文件或contigs文件)")
    parser.add_argument("--mode", required=True, choices=["reads", "contigs"],
                       help="输入模式: reads(测序文件) 或 contigs(组装文件)")
    parser.add_argument("-o", "--output", default="result", help="输出目录 (默认: result)")
    parser.add_argument("-t", "--threads", type=int, default=8, help="线程数 (默认: 8)")
    parser.add_argument("--host", help="宿主基因组(逗号分隔,仅reads模式需要)")
    parser.add_argument("--db", default="~/db", help="数据库目录 (默认: ~/db)")
    parser.add_argument("--config", help="配置文件 (默认: make.py所在目录的config/config.yaml)")
    
    args = parser.parse_args()
    
    # 设置默认配置文件路径（相对于make.py的位置）
    if not args.config:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.config = os.path.join(script_dir, "config", "config.yaml")
    
    # 转换输入目录为绝对路径
    args.input = os.path.abspath(args.input)
    
    # 验证参数
    if not os.path.isdir(args.input):
        parser.error(f"输入目录不存在: {args.input}")
    if args.mode == "reads" and not args.host:
        parser.error("reads模式需要指定 --host 参数")
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
