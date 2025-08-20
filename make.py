#!/usr/bin/env python3
"""
GutMicrobe-Virus 批量脚本生成器

根据输入数据目录和结果目录，生成三类脚本：
1. 上游处理脚本（每个样本一个）
2. 病毒库构建脚本（一个）
3. 下游处理脚本（每个样本一个）

支持三种执行模式：
- local: 本地执行
- slurm: SLURM集群
- cfff: 特殊的集群环境（需要module load但不指定资源）
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
import configparser


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def load_config(config_file: str = "config.ini") -> Dict[str, Any]:
    """加载配置文件"""
    config = configparser.ConfigParser()
    config.read(config_file, encoding='utf-8')
    
    # 转换为字典格式
    result = {}
    for section in config.sections():
        result[section] = {}
        for key, value in config.items(section):
            result[section][key] = value
    
    return result


def get_read_pairs(data_dir: str) -> List[Tuple[str, str, str]]:
    """
    获取配对的reads文件
    返回: [(sample_name, r1_path, r2_path), ...]
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_dir}")

    # 获取所有fastq文件
    valid_suffixes = ['.fq.gz', '.fastq.gz', '.fq', '.fastq']
    files = []
    for f in data_path.iterdir():
        if not f.is_file():
            continue
        if any(f.name.endswith(suffix) for suffix in valid_suffixes):
            files.append(f)

    # 按文件名排序
    files.sort(key=lambda x: x.name)

    pairs = []
    processed = set()

    # 定义R1标识符和对应的R2标识符
    patterns = [
        ('_R1', '_R2'),
        ('_1.', '_2.'),
        ('.1.', '.2.'),
        ('R1', 'R2'),
        ('_1', '_2')
    ]

    for f in files:
        if f.name in processed:
            continue

        # 检查是否是R1文件
        found_pattern = None
        for r1_pattern, r2_pattern in patterns:
            if r1_pattern in f.name:
                found_pattern = (r1_pattern, r2_pattern)
                break

        if found_pattern:
            r1_pattern, r2_pattern = found_pattern
            r1 = str(f)

            # 查找对应的R2文件
            r2_filename = f.name.replace(r1_pattern, r2_pattern)
            r2_path = data_path / r2_filename

            if r2_path.exists() and r2_path.name not in processed:
                # 提取样本名 - 移除R1/R2标识符
                sample_name = f.name
                for pattern, _ in patterns:
                    if pattern in sample_name:
                        sample_name = sample_name.replace(pattern, '')
                # 移除文件扩展名
                for suffix in valid_suffixes:
                    if sample_name.endswith(suffix):
                        sample_name = sample_name[:-len(suffix)]
                # 移除可能的分隔符
                sample_name = sample_name.rstrip('._-')

                pairs.append((sample_name, r1, str(r2_path)))
                processed.add(f.name)
                processed.add(r2_path.name)

    return pairs


def get_conda_activation(mode: str, config: Dict[str, Any]) -> str:
    """根据模式获取conda激活命令"""
    if mode == "local":
        # 本地模式，优先使用source activate
        main_env = config.get('batch', {}).get('main_conda_activate', '')
        if main_env:
            # 提取环境路径
            if 'source activate' in main_env:
                env_path = main_env.split('source activate')[-1].strip()
                return f"source activate {env_path} || conda activate {env_path} || export PATH={env_path}/bin:$PATH"
            else:
                return main_env
        return ""
    
    elif mode == "slurm":
        # SLURM模式，优先使用source activate
        main_env = config.get('batch', {}).get('main_conda_activate', '')
        if main_env:
            if 'source activate' in main_env:
                return main_env
            else:
                # 如果配置中没有source activate，则添加
                env_path = main_env.replace('conda activate', '').strip()
                return f"source activate {env_path}"
        return ""
    
    elif mode == "cfff":
        # CFFF模式，需要module load，优先使用source activate
        module_load = config.get('batch', {}).get('main_module_load', '')
        conda_activate = config.get('batch', {}).get('main_conda_activate', '')
        
        commands = []
        if module_load:
            commands.append(module_load)
        if conda_activate:
            # 优先使用source activate
            if 'source activate' in conda_activate:
                commands.append(conda_activate)
            else:
                env_path = conda_activate.replace('conda activate', '').strip()
                commands.append(f"source activate {env_path}")
        
        return ' && '.join(commands) if commands else ''
    
    return ""


def generate_upstream_script(sample_name: str, r1: str, r2: str, result_dir: str,
                           config: Dict[str, Any], mode: str, project_root: str) -> str:
    """生成上游处理脚本"""
    
    threads = config.get('batch', {}).get('threads', '32')
    host = config.get('batch', {}).get('host', 'hg38')
    db = config.get('batch', {}).get('db', '')
    
    conda_cmd = get_conda_activation(mode, config)
    
    script_content = "#!/bin/bash\n\n"
    
    if mode == "slurm":
        script_content += f"""#SBATCH --job-name=upstream_{sample_name}
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks={threads}
#SBATCH --mem=50G
#SBATCH --time=24:00:00
#SBATCH --output=logs/upstream_{sample_name}_%j.out
#SBATCH --error=logs/upstream_{sample_name}_%j.err

"""
    
    script_content += """# 设置错误时退出
set -e

# 创建日志目录
mkdir -p logs

echo "=========================================="
echo "上游分析开始时间: $(date)"
echo "样本名称: """ + sample_name + """"
echo "节点信息: $(hostname)"
echo "工作目录: $(pwd)"
echo "=========================================="

"""
    
    # 添加环境激活
    if conda_cmd:
        script_content += f"# 激活环境\n{conda_cmd}\n\n"
    
    # 添加主要命令 - 使用绝对路径
    run_upstream_path = os.path.join(project_root, "run_upstream.py")
    config_path = os.path.join(project_root, "config.ini")
    result_dir_abs = os.path.abspath(result_dir)
    r1_abs = os.path.abspath(r1)
    r2_abs = os.path.abspath(r2)
    cmd_parts = [
        f"python {run_upstream_path}",
        f'"{r1_abs}"',
        f'"{r2_abs}"',
        f"-o {result_dir_abs}",
        f"-t {threads}",
        f"--config {config_path}"
    ]
    
    if host:
        cmd_parts.append(f"--host {host}")
    if db:
        cmd_parts.append(f"--db {db}")
    
    script_content += "# 执行上游分析\n"
    script_content += " \\\n    ".join(cmd_parts) + "\n\n"
    
    script_content += """echo "=========================================="
echo "上游分析完成时间: $(date)"
echo "=========================================="
"""
    
    return script_content


def generate_viruslib_script(result_dir: str, config: Dict[str, Any], mode: str, project_root: str) -> str:
    """生成病毒库构建脚本"""
    
    threads = config.get('batch', {}).get('threads', '32')
    db = config.get('batch', {}).get('db', '')
    viruslib_result = config.get('batch', {}).get('viruslib_result', f'{result_dir}/viruslib')
    
    conda_cmd = get_conda_activation(mode, config)
    
    script_content = "#!/bin/bash\n\n"
    
    if mode == "slurm":
        script_content += f"""#SBATCH --job-name=viruslib
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks={threads}
#SBATCH --mem=100G
#SBATCH --time=48:00:00
#SBATCH --output=logs/viruslib_%j.out
#SBATCH --error=logs/viruslib_%j.err

"""
    
    script_content += """# 设置错误时退出
set -e

# 创建日志目录
mkdir -p logs

echo "=========================================="
echo "病毒库构建开始时间: $(date)"
echo "节点信息: $(hostname)"
echo "工作目录: $(pwd)"
echo "=========================================="

"""
    
    # 添加环境激活
    if conda_cmd:
        script_content += f"# 激活环境\n{conda_cmd}\n\n"
    
    # 添加主要命令 - 使用绝对路径
    viruslib_path = os.path.join(project_root, "viruslib_pipeline.py")
    config_path = os.path.join(project_root, "config.ini")
    viruslib_result_abs = os.path.abspath(viruslib_result)
    cmd_parts = [
        f"python {viruslib_path}",
        f"-t {threads}",
        f"-o {viruslib_result_abs}",
        f"--config {config_path}"
    ]
    
    if db:
        cmd_parts.append(f"--db {db}")
    
    script_content += "# 执行病毒库构建\n"
    script_content += " \\\n    ".join(cmd_parts) + "\n\n"
    
    script_content += """echo "=========================================="
echo "病毒库构建完成时间: $(date)"
echo "=========================================="
"""
    
    return script_content


def generate_downstream_script(sample_name: str, r1: str, r2: str, result_dir: str,
                             config: Dict[str, Any], mode: str, project_root: str) -> str:
    """生成下游处理脚本"""
    
    threads = config.get('batch', {}).get('threads', '32')
    upstream_result = result_dir
    viruslib_result = config.get('batch', {}).get('viruslib_result', f'{result_dir}/viruslib')
    downstream_result = config.get('batch', {}).get('downstream_result', f'{result_dir}/downstream')
    
    conda_cmd = get_conda_activation(mode, config)
    
    script_content = "#!/bin/bash\n\n"
    
    if mode == "slurm":
        script_content += f"""#SBATCH --job-name=downstream_{sample_name}
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks={threads}
#SBATCH --mem=50G
#SBATCH --time=24:00:00
#SBATCH --output=logs/downstream_{sample_name}_%j.out
#SBATCH --error=logs/downstream_{sample_name}_%j.err

"""
    
    script_content += """# 设置错误时退出
set -e

# 创建日志目录
mkdir -p logs

echo "=========================================="
echo "下游分析开始时间: $(date)"
echo "样本名称: """ + sample_name + """"
echo "节点信息: $(hostname)"
echo "工作目录: $(pwd)"
echo "=========================================="

"""
    
    # 添加环境激活
    if conda_cmd:
        script_content += f"# 激活环境\n{conda_cmd}\n\n"
    
    # 添加主要命令 - 使用绝对路径
    run_downstream_path = os.path.join(project_root, "run_downstream.py")
    config_path = os.path.join(project_root, "config.ini")
    upstream_result_abs = os.path.abspath(upstream_result)
    viruslib_result_abs = os.path.abspath(viruslib_result)
    downstream_result_abs = os.path.abspath(downstream_result)
    r1_abs = os.path.abspath(r1)
    r2_abs = os.path.abspath(r2)
    cmd_parts = [
        f"python {run_downstream_path}",
        f'"{r1_abs}"',
        f'"{r2_abs}"',
        f"--upstream-result {upstream_result_abs}",
        f"--viruslib-result {viruslib_result_abs}",
        f"-o {downstream_result_abs}",
        f"-t {threads}",
        f"--config {config_path}"
    ]
    
    script_content += "# 执行下游分析\n"
    script_content += " \\\n    ".join(cmd_parts) + "\n\n"
    
    script_content += """echo "=========================================="
echo "下游分析完成时间: $(date)"
echo "=========================================="
"""
    
    return script_content


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="GutMicrobe-Virus 批量脚本生成器")
    parser.add_argument("data_dir", help="原始数据目录路径")
    parser.add_argument("result_dir", help="结果输出目录路径")
    parser.add_argument("--mode", choices=["local", "slurm", "cfff"], 
                       default="local", help="执行模式")
    parser.add_argument("--config", help="配置文件路径", default="config.ini")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="日志级别")
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    try:
        # 获取项目根目录（make.py所在目录）
        project_root = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"项目根目录: {project_root}")
        
        # 检查输入目录
        if not os.path.exists(args.data_dir):
            logger.error(f"数据目录不存在: {args.data_dir}")
            sys.exit(1)
        
        # 加载配置
        logger.info(f"加载配置文件: {args.config}")
        config = load_config(args.config)
        
        # 获取reads文件对
        logger.info(f"扫描数据目录: {args.data_dir}")
        read_pairs = get_read_pairs(args.data_dir)
        
        if not read_pairs:
            logger.error(f"在 {args.data_dir} 中未找到配对的reads文件")
            sys.exit(1)
        
        logger.info(f"找到 {len(read_pairs)} 对reads文件:")
        for sample_name, r1, r2 in read_pairs:
            logger.info(f"  {sample_name}: {Path(r1).name} + {Path(r2).name}")
        
        # 创建脚本目录
        script_dir = Path(args.result_dir).parent / "scripts"
        script_dir.mkdir(parents=True, exist_ok=True)
        
        upstream_dir = script_dir / "upstream"
        downstream_dir = script_dir / "downstream"
        upstream_dir.mkdir(exist_ok=True)
        downstream_dir.mkdir(exist_ok=True)
        
        logger.info(f"脚本将保存到: {script_dir}")
        
        # 生成上游脚本
        logger.info("生成上游处理脚本...")
        upstream_scripts = []
        for sample_name, r1, r2 in read_pairs:
            script_content = generate_upstream_script(
                sample_name, r1, r2, args.result_dir, config, args.mode, project_root
            )
            
            script_path = upstream_dir / f"upstream_{sample_name}.sh"
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            os.chmod(script_path, 0o755)
            upstream_scripts.append(str(script_path))
            logger.info(f"  生成: {script_path}")
        
        # 生成病毒库脚本
        logger.info("生成病毒库构建脚本...")
        viruslib_content = generate_viruslib_script(args.result_dir, config, args.mode, project_root)
        viruslib_path = script_dir / "viruslib.sh"
        with open(viruslib_path, 'w') as f:
            f.write(viruslib_content)
        os.chmod(viruslib_path, 0o755)
        logger.info(f"  生成: {viruslib_path}")
        
        # 生成下游脚本
        logger.info("生成下游处理脚本...")
        downstream_scripts = []
        for sample_name, r1, r2 in read_pairs:
            script_content = generate_downstream_script(
                sample_name, r1, r2, args.result_dir, config, args.mode, project_root
            )
            
            script_path = downstream_dir / f"downstream_{sample_name}.sh"
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            os.chmod(script_path, 0o755)
            downstream_scripts.append(str(script_path))
            logger.info(f"  生成: {script_path}")
        
        # 生成提交脚本
        logger.info("生成提交脚本...")
        
        if args.mode == "slurm":
            # SLURM提交脚本
            submit_content = "#!/bin/bash\n\n"
            submit_content += "# 提交上游分析作业\n"
            for script in upstream_scripts:
                submit_content += f"sbatch {script}\n"
            
            submit_content += "\n# 提交病毒库构建作业\n"
            submit_content += f"sbatch {viruslib_path}\n"
            
            submit_content += "\n# 提交下游分析作业\n"
            for script in downstream_scripts:
                submit_content += f"sbatch {script}\n"
            
            submit_path = script_dir / "submit_all.sh"
            
        else:
            # 本地或CFFF执行脚本
            submit_content = "#!/bin/bash\n\n"
            submit_content += "set -e\n\n"
            submit_content += "# GutMicrobe-Virus 批量执行脚本\n"
            submit_content += "# 自动生成，请勿手动修改\n\n"
            
            submit_content += "echo \"========================================\"\n"
            submit_content += "echo \"GutMicrobe-Virus 批量分析开始\"\n"
            submit_content += "echo \"开始时间: $(date)\"\n"
            submit_content += "echo \"========================================\"\n\n"
            
            # 检查必要的文件和目录
            submit_content += "# 检查项目结构\n"
            submit_content += f"if [ ! -f \"{project_root}/config.ini\" ]; then\n"
            submit_content += f"    echo \"错误: 找不到配置文件 {project_root}/config.ini\"\n"
            submit_content += "    exit 1\n"
            submit_content += "fi\n\n"
            
            submit_content += "# 创建必要的目录\n"
            submit_content += f"mkdir -p {args.result_dir}\n"
            submit_content += "mkdir -p logs\n\n"
            
            submit_content += "echo \"开始执行上游分析...\"\n"
            for i, script in enumerate(upstream_scripts, 1):
                sample_name = Path(script).stem.replace('upstream_', '')
                submit_content += f"echo \"[{i}/{len(upstream_scripts)}] 处理样本: {sample_name}\"\n"
                submit_content += f"bash {script} || {{ echo \"上游分析失败: {sample_name}\"; exit 1; }}\n"
            
            submit_content += "\necho \"开始执行病毒库构建...\"\n"
            submit_content += f"bash {viruslib_path} || {{ echo \"病毒库构建失败\"; exit 1; }}\n"
            
            submit_content += "\necho \"开始执行下游分析...\"\n"
            for i, script in enumerate(downstream_scripts, 1):
                sample_name = Path(script).stem.replace('downstream_', '')
                submit_content += f"echo \"[{i}/{len(downstream_scripts)}] 处理样本: {sample_name}\"\n"
                submit_content += f"bash {script} || {{ echo \"下游分析失败: {sample_name}\"; exit 1; }}\n"
            
            submit_content += "\necho \"========================================\"\n"
            submit_content += "echo \"所有任务完成！\"\n"
            submit_content += "echo \"完成时间: $(date)\"\n"
            submit_content += "echo \"========================================\"\n"
            
            submit_path = script_dir / "run_all.sh"
        
        with open(submit_path, 'w') as f:
            f.write(submit_content)
        os.chmod(submit_path, 0o755)
        
        logger.info(f"  生成: {submit_path}")
        
        logger.info("所有脚本生成完成！")
        logger.info(f"执行方式:")
        if args.mode == "slurm":
            logger.info(f"  bash {submit_path}")
        else:
            logger.info(f"  bash {submit_path}")
        
    except Exception as e:
        logger.error(f"脚本生成失败: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
