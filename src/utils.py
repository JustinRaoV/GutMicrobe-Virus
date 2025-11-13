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


def mark_step_done(output_dir, sample, step_name):
    """标记步骤完成"""
    status_dir = os.path.join(output_dir, ".status", sample)
    ensure_dir(status_dir)
    status_file = os.path.join(status_dir, f"{step_name}.done")
    with open(status_file, "w") as f:
        from datetime import datetime
        f.write(f"completed_at: {datetime.now().isoformat()}\n")


def is_step_done(output_dir, sample, step_name):
    """检查步骤是否已完成"""
    status_file = os.path.join(output_dir, ".status", sample, f"{step_name}.done")
    return os.path.exists(status_file)


def get_step_timestamp(output_dir, sample, step_name):
    """获取步骤完成时间戳"""
    status_file = os.path.join(output_dir, ".status", sample, f"{step_name}.done")
    if os.path.exists(status_file):
        return os.path.getmtime(status_file)
    return None


def invalidate_dependent_steps(output_dir, sample, step_name, step_dependencies):
    """使依赖该步骤的后续步骤失效"""
    status_dir = os.path.join(output_dir, ".status", sample)
    if not os.path.exists(status_dir):
        return
    
    # 找出所有依赖当前步骤的后续步骤
    for dependent_step, dependencies in step_dependencies.items():
        if step_name in dependencies:
            status_file = os.path.join(status_dir, f"{dependent_step}.done")
            if os.path.exists(status_file):
                os.remove(status_file)
                # 递归使该步骤的依赖步骤也失效
                invalidate_dependent_steps(output_dir, sample, dependent_step, step_dependencies)
