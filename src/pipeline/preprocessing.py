"""基础分析步骤: 质控、去宿主、组装、过滤"""
import os
import subprocess
from src.config import get_software, get_params
from src.utils import ensure_dir, get_path, copy_files


def run_fastp(ctx):
    """质控"""
    out_dir = ensure_dir(get_path(ctx, "trimmed"))
    cmd = (
        f"{get_software(ctx['config'], 'fastp')} "
        f"-i {ctx['input1']} -I {ctx['input2']} "
        f"-o {out_dir}/{ctx['sample1']}.fq.gz -O {out_dir}/{ctx['sample2']}.fq.gz "
        f"{get_params(ctx['config'], 'fastp')} -w {ctx['threads']} "
        f"-h {out_dir}/report.html"
    )
    subprocess.run(cmd, shell=True, check=True)
    ctx["logger"].info("质控完成")


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
        index = os.path.join(ctx["db"], "bowtie2_index", host, host)
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
