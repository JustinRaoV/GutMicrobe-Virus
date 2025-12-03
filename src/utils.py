"""工具函数"""
import os
import subprocess
import shutil


def get_sample_name(filename):
    """从文件名提取样本名"""
    for ext in [".fastq.gz", ".fq.gz", ".fastq", ".fq"]:
        if filename.endswith(ext):
            return filename[:-len(ext)]
    return filename


def run_cmd(cmd, logger=None, shell=True):
    """运行命令"""
    if logger:
        logger.info(f"运行: {cmd}")
    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    if result.returncode != 0:
        error_msg = f"命令失败: {cmd}\n{result.stderr}"
        if logger:
            logger.error(error_msg)
        raise RuntimeError(error_msg)
    return result


def ensure_dir(path):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)
    return path


def get_path(ctx, step, *parts):
    """获取步骤路径"""
    base = os.path.join(ctx["paths"][step], ctx["sample"])
    return os.path.join(base, *parts) if parts else base


def copy_files(src_dir, dst_dir, files):
    """批量复制文件"""
    ensure_dir(dst_dir)
    for f in files:
        shutil.copy2(os.path.join(src_dir, f), os.path.join(dst_dir, f))


def get_checkpoint_file(output_dir, sample):
    """获取断点文件路径"""
    checkpoint_dir = os.path.join(output_dir, "checkpoints")
    ensure_dir(checkpoint_dir)
    return os.path.join(checkpoint_dir, f"{sample}.checkpoint")


def save_checkpoint(output_dir, sample, step_index):
    """保存断点（当前成功完成的步骤序号）"""
    checkpoint_file = get_checkpoint_file(output_dir, sample)
    with open(checkpoint_file, "w") as f:
        f.write(str(step_index))


def load_checkpoint(output_dir, sample):
    """加载断点，返回上次成功完成的步骤序号，如果没有则返回0"""
    checkpoint_file = get_checkpoint_file(output_dir, sample)
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return 0
    return 0


def clear_checkpoint(output_dir, sample):
    """清除断点文件"""
    checkpoint_file = get_checkpoint_file(output_dir, sample)
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
