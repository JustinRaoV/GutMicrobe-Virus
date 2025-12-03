"""配置管理"""
import yaml
import os


def load_config(config_path="config/config.yaml"):
    """加载YAML配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_software(config, name):
    """获取软件路径,支持 Singularity 容器
    
    返回格式:
    - 如果启用 singularity: "singularity exec {sif_path} {software}"
    - 否则: 直接返回软件路径
    """
    use_singularity = config.get('singularity', {}).get('enabled', False)
    
    if use_singularity:
        sif_dir = config.get('singularity', {}).get('sif_dir', '~/sif')
        sif_binds = config.get('singularity', {}).get('binds', [])
        
        # 获取软件对应的 sif 文件名
        sif_mapping = config.get('singularity', {}).get('sif_mapping', {})
        sif_file = sif_mapping.get(name, f"{name}.sif")
        sif_path = os.path.join(sif_dir, sif_file)
        
        # 构建 bind 参数
        bind_args = ""
        if sif_binds:
            bind_args = " ".join([f"-B {b}" for b in sif_binds])
        
        # 软件名称（容器内命令）- 直接使用软件名，不从 software 配置读取
        software_cmd = name
        if name == 'dvf':
            software_cmd = 'dvf.py'
        elif name == 'vibrant':
            software_cmd = 'VIBRANT_run.py'
        
        return f"singularity exec {bind_args} {sif_path} {software_cmd}".strip()
    else:
        # 传统模式: 直接返回软件路径
        return config.get('software', {}).get(name, name)


def get_params(config, name):
    """获取软件参数"""
    return config.get('parameters', {}).get(name, '')


def get_database(config, name):
    """获取数据库路径,支持默认路径
    
    如果未配置特定数据库,则使用: {root}/{name}
    例如: checkv未配置时使用 {root}/checkv
    """
    db_config = config.get('database', {})
    
    if name == 'root':
        return db_config.get('root', '~/db')
    
    # 如果有明确配置,使用配置值
    if name in db_config:
        return db_config[name]
    
    # 否则使用默认路径: root/数据库名
    root = db_config.get('root', '~/db')
    default_paths = {
        'checkv': os.path.join(root, 'checkv'),
        'phabox2': os.path.join(root, 'phabox2'),
        'genomad': os.path.join(root, 'genomad'),
        'blastn': os.path.join(root, 'blastn_database'),
        'busco': os.path.join(root, 'bacteria_odb12'),
        'virsorter': os.path.join(root, 'db'),
    }
    
    return default_paths.get(name, os.path.join(root, name))


def is_tool_enabled(config, tool_name):
    """检查病毒检测工具是否启用,默认启用"""
    return config.get('virus_detection', {}).get(f'enable_{tool_name}', True)
