"""病毒检测模块 - 可配置的多工具检测"""
import os
import subprocess
import shutil
from src.config import get_software, get_params, is_tool_enabled, get_database
from src.utils import ensure_dir, get_path


def _skip_if_disabled(ctx, tool_name):
    """检查工具是否被禁用"""
    if not is_tool_enabled(ctx["config"], tool_name):
        ctx["logger"].info(f"跳过{tool_name}")
        return True
    return False


def run_virsorter(ctx):
    """VirSorter2 三步走检测"""
    if _skip_if_disabled(ctx, "virsorter"):
        return
    
    cfg = ctx["config"]
    base_dir = get_path(ctx, "virsorter")
    ensure_dir(os.path.dirname(base_dir))
    in_file = get_path(ctx, "vsearch", "contigs.fa")
    
    # 准备数据库参数 (Conda模式需要, Singularity模式不需要)
    db_arg = ""
    if not cfg.get('singularity', {}).get('enabled', False):
        db_path = get_database(cfg, 'virsorter')
        db_arg = f"-d {db_path}"
    
    # Pass 1: 初次检测
    pass1_dir = os.path.join(base_dir, "vs2-pass1")
    pass1_result = os.path.join(pass1_dir, "final-viral-combined.fa")
    
    if os.path.exists(pass1_result):
        ctx["logger"].info("VirSorter Pass 1 已完成，跳过")
    else:
        ctx["logger"].info("VirSorter Pass 1")
        # 如果目录存在但结果不存在，可能是上次运行失败，清理目录
        if os.path.exists(pass1_dir):
            shutil.rmtree(pass1_dir)
            
        cmd = (
            f"{get_software(cfg, 'virsorter')} run -i {in_file} -w {pass1_dir} "
            f"-j {ctx['threads']} {db_arg} {get_params(cfg, 'virsorter_pass1')} all"
        )
        subprocess.run(cmd, shell=True, check=True)
    
    # CheckV中间步骤
    checkv_dir = os.path.join(base_dir, "checkv")
    combined_file = os.path.join(checkv_dir, "combined.fna")
    
    if os.path.exists(combined_file):
        ctx["logger"].info("VirSorter CheckV验证 已完成，跳过")
    else:
        ctx["logger"].info("VirSorter CheckV验证")
        # CheckV运行
        # 注意：CheckV如果目录存在会报错，所以需要先清理
        if os.path.exists(checkv_dir):
            shutil.rmtree(checkv_dir)
            
        cmd = (
            f"{get_software(cfg, 'checkv')} end_to_end {pass1_result} {checkv_dir} "
            f"-t {ctx['threads']} -d {get_database(cfg, 'checkv')}"
        )
        subprocess.run(cmd, shell=True, check=True)
        
        # 合并 proviruses.fna 和 viruses.fna
        cmd = f"cat {checkv_dir}/proviruses.fna {checkv_dir}/viruses.fna > {combined_file}"
        subprocess.run(cmd, shell=True, check=True)
    
    # Pass 2: 精细化检测
    pass2_dir = os.path.join(base_dir, "vs2-pass2")
    final_result_src = os.path.join(pass2_dir, "final-viral-score.tsv")
    final_result_dst = os.path.join(base_dir, "final-viral-score.tsv")
    
    if os.path.exists(final_result_dst):
        ctx["logger"].info("VirSorter Pass 2 已完成，跳过")
    else:
        ctx["logger"].info("VirSorter Pass 2")
        if os.path.exists(pass2_dir):
            shutil.rmtree(pass2_dir)
            
        cmd = (
            f"{get_software(cfg, 'virsorter')} run -i {combined_file} -w {pass2_dir} "
            f"-j {ctx['threads']} {db_arg} {get_params(cfg, 'virsorter_pass2')} all"
        )
        subprocess.run(cmd, shell=True, check=True)
        
        # 复制最终结果到主目录
        shutil.copy2(final_result_src, final_result_dst)
    
    ctx["logger"].info("VirSorter完成")


def run_genomad(ctx):
    """geNomad检测 - 使用end-to-end模式"""
    if _skip_if_disabled(ctx, "genomad"):
        return
    
    cfg = ctx["config"]
    out_dir = ensure_dir(get_path(ctx, "genomad"))
    in_file = get_path(ctx, "vsearch", "contigs.fa")
    genomad_db = get_database(cfg, 'genomad')
    
    # geNomad end-to-end命令
    cmd = (
        f"{get_software(cfg, 'genomad')} end-to-end {in_file} {out_dir} {genomad_db} "
        f"-t {ctx['threads']} --splits {ctx['threads']} {get_params(cfg, 'genomad')}"
    )
    subprocess.run(cmd, shell=True, check=True)
    
    ctx["logger"].info("geNomad完成")





def get_enabled_tools(config):
    """获取启用的病毒检测工具列表"""
    return [t for t in ["virsorter", "genomad"] 
            if is_tool_enabled(config, t)]
