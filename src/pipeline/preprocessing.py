"""基础分析步骤: 质控、去宿主、组装、过滤"""
import os
import subprocess
import shutil
from src.config import get_software, get_params, get_database
from src.utils import ensure_dir, get_path, copy_files


def run_fastp(ctx):
    """质控"""
    out_dir = ensure_dir(get_path(ctx, "trimmed"))

    cfg_params = ctx.get("config", {}).get("parameters", {})
    stage_reads = bool(cfg_params.get("stage_reads", True))
    stage_keep_on_fail = bool(cfg_params.get("stage_keep_on_fail", True))

    r1_in = ctx["input1"]
    r2_in = ctx["input2"]

    stage_dir = os.path.join(out_dir, "_staging")
    stage_r1 = os.path.join(stage_dir, os.path.basename(r1_in))
    stage_r2 = os.path.join(stage_dir, os.path.basename(r2_in))

    if stage_reads:
        ensure_dir(stage_dir)
        ctx["logger"].info("fastp: staging 输入文件到本地工作目录")
        shutil.copy2(r1_in, stage_r1)
        shutil.copy2(r2_in, stage_r2)
        r1_use, r2_use = stage_r1, stage_r2
    else:
        r1_use, r2_use = r1_in, r2_in

    # 构建命令参数 (尝试使用相对路径以兼容 Singularity)
    cwd = os.getcwd()
    
    def to_rel(path):
        try:
            abs_path = os.path.abspath(path)
            if abs_path.startswith(cwd):
                return os.path.relpath(abs_path, cwd)
        except Exception:
            pass
        return path

    r1_cmd = to_rel(r1_use)
    r2_cmd = to_rel(r2_use)
    out_r1 = to_rel(os.path.join(out_dir, f"{ctx['sample1']}.fq.gz"))
    out_r2 = to_rel(os.path.join(out_dir, f"{ctx['sample2']}.fq.gz"))
    report = to_rel(os.path.join(out_dir, "report.html"))

    cmd = (
        f"{get_software(ctx['config'], 'fastp')} "
        f"-i {r1_cmd} -I {r2_cmd} "
        f"-o {out_r1} -O {out_r2} "
        f"{get_params(ctx['config'], 'fastp')} -w {ctx['threads']} "
        f"-h {report}"
    )
    try:
        subprocess.run(cmd, shell=True, check=True)
        ctx["logger"].info("质控完成")
        if stage_reads:
            shutil.rmtree(stage_dir, ignore_errors=True)
    except Exception:
        if stage_reads and not stage_keep_on_fail:
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise


def run_host_removal(ctx):
    """去宿主"""
    trim_dir = get_path(ctx, "trimmed")
    out_dir = ensure_dir(get_path(ctx, "host_removed"))
    files = [f"{ctx['sample1']}.fq.gz", f"{ctx['sample2']}.fq.gz"]
    
    if not ctx["host_list"]:
        ctx["logger"].info("跳过去宿主")
        copy_files(trim_dir, out_dir, files)
        return
    
    # 复制初始文件
    copy_files(trim_dir, out_dir, files)
    
    # 对每个宿主运行bowtie2
    for host in ctx["host_list"]:
        # 从配置中获取bowtie2索引根目录
        bowtie2_base = get_database(ctx['config'], 'bowtie2_index')
        index = os.path.join(bowtie2_base, host, host)
        r1, r2 = [os.path.join(out_dir, f) for f in files]
        
        cmd = (
            f"{get_software(ctx['config'], 'bowtie2')} -p {ctx['threads']} -x {index} "
            f"-1 {r1} -2 {r2} --un-conc-gz {out_dir}/tmp.fq.gz -S {out_dir}/tmp.sam"
        )
        subprocess.run(cmd, shell=True, check=True)
        
        # 更新文件
        os.rename(f"{out_dir}/tmp.fq.1.gz", r1)
        os.rename(f"{out_dir}/tmp.fq.2.gz", r2)
        os.remove(f"{out_dir}/tmp.sam")
    
    ctx["logger"].info(f"去宿主完成 (移除: {', '.join(ctx['host_list'])})")


def run_assembly(ctx):
    """组装"""
    out_dir = get_path(ctx, "assembly")
    host_dir = get_path(ctx, "host_removed")
    r1 = os.path.join(host_dir, f"{ctx['sample1']}.fq.gz")
    r2 = os.path.join(host_dir, f"{ctx['sample2']}.fq.gz")
    
    # megahit要求父目录存在,但输出目录本身不能存在
    parent_dir = os.path.dirname(out_dir)
    ensure_dir(parent_dir)
    
    # 如果输出目录已存在,删除它(断点重跑场景)
    if os.path.exists(out_dir):
        import shutil
        shutil.rmtree(out_dir)
    
    cmd = (
        f"{get_software(ctx['config'], 'megahit')} -1 {r1} -2 {r2} -o {out_dir} "
        f"{get_params(ctx['config'], 'megahit')} -t {ctx['threads']}"
    )
    subprocess.run(cmd, shell=True, check=True)
    ctx["logger"].info("组装完成")


def run_vsearch(ctx):
    """长度过滤"""
    in_file = get_path(ctx, "assembly", "final.contigs.fa")
    out_dir = ensure_dir(get_path(ctx, "vsearch"))
    
    cmd = (
        f"{get_software(ctx['config'], 'vsearch')} --sortbylength {in_file} "
        f"--output {out_dir}/contigs.fa {get_params(ctx['config'], 'vsearch')}"
    )
    subprocess.run(cmd, shell=True, check=True)
    ctx["logger"].info("长度过滤完成")
