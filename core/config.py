"""
统一配置管理模块

提供一致的配置访问接口和默认值管理
"""

import configparser
import os
from typing import Any, Dict, Optional, Union


class ConfigManager:
    """统一的配置管理器"""
    
    # 默认配置值
    DEFAULT_VALUES = {
        # 软件路径默认值
        'software': {
            'fastp': 'fastp',
            'bowtie2': 'bowtie2',
            'megahit': 'megahit',
            'vsearch': 'vsearch',
            'virsorter': 'virsorter',
            'checkv': 'checkv',
            'seqkit': 'seqkit',
            'pigz': 'pigz',
            'coverm': 'coverm',
        },
        # 参数默认值
        'parameters': {
            'fastp_params': '-l 90 -q 20 -u 30 -y --trim_poly_g --detect_adapter_for_pe',
            'megahit_params': '--k-list 21,29,39,59,79,99,119',
            'vsearch_params': '--minseqlength 500 --maxseqlength -1',
            'virsorter_params': '--min-length 3000 --min-score 0.5 --include-groups dsDNAphage,NCLDV,RNA,ssDNA,lavidaviridae',
            'coverm_params': '--min-read-percent-identity 95 --min-read-aligned-percent 75 -m count --output-format dense',
            'coverm_contig_cmd': 'contig',
            'coverm_gene_cmd': 'contig',
            'dvf_score_threshold': '0.9',
            'dvf_pvalue_threshold': '0.01',
            'filter_ratio_threshold': '0.05',
            'blastn_pident': '50',
            'blastn_evalue': '1e-10',
            'blastn_qcovs': '80',
        },
        # 组合工具默认值
        'combination': {
            'use_blastn': '1',
            'use_virsorter': '1',
            'use_dvf': '1',
            'use_vibrant': '1',
            'use_checkv_prefilter': '1',
            'min_tools_hit': '1',
        },
        # 数据库路径模板
        'database_templates': {
            'checkv_database': '{db_root}/checkvdb/checkv-db-v1.4',
            'dvf_models': '{db_root}/dvf/models',
            'blastn_database': '{db_root}/blastn_database',
            'vibrant_database': '{db_root}/vibrant/databases',
            'vibrant_files': '{db_root}/vibrant/files',
            'busco_database': '{db_root}/bacteria_odb12',
            'bowtie2_db': '{db_root}/bowtie2_index',
        },
        # 硬编码常量
        'constants': {
            'blastn_databases': ['crass', 'gpd', 'gvd', 'mgv', 'ncbi'],
            'checkv_host_gene_threshold': '10',
            'checkv_host_viral_ratio': '5',
            'busco_run_dir': 'run_bacteria_odb12',
            'busco_table_file': 'full_table.tsv',
        }
    }
    
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()
    
    def _load_config(self):
        """加载配置文件，支持智能路径查找"""
        config_paths = []
        
        # 如果是绝对路径，直接使用
        if os.path.isabs(self.config_file):
            config_paths.append(self.config_file)
        else:
            # 相对路径的查找顺序
            config_paths.extend([
                # 1. 当前工作目录
                os.path.join(os.getcwd(), self.config_file),
                # 2. 脚本所在目录（适用于直接调用Python脚本的情况）
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", self.config_file),
                # 3. 项目根目录（通过查找包含run_upstream.py的目录）
                self._find_project_root_config(self.config_file),
                # 4. 原始相对路径
                self.config_file
            ])
        
        # 移除None值和重复路径
        config_paths = list(dict.fromkeys([p for p in config_paths if p]))
        
        for config_path in config_paths:
            if config_path and os.path.exists(config_path):
                self.config.read(config_path, encoding='utf-8')
                self.config_file = config_path  # 更新为实际使用的路径
                return
        
        # 如果都找不到，提供详细的错误信息
        searched_paths = '\n  '.join(config_paths)
        raise FileNotFoundError(
            f"配置文件不存在: {self.config_file}\n"
            f"已搜索以下路径:\n  {searched_paths}\n"
            f"请确保config.ini文件存在于项目根目录或使用--config参数指定正确路径"
        )
    
    def _find_project_root_config(self, config_file: str) -> str:
        """查找项目根目录中的配置文件"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 向上查找包含run_upstream.py的目录
        while current_dir != os.path.dirname(current_dir):  # 直到根目录
            potential_config = os.path.join(current_dir, config_file)
            run_upstream = os.path.join(current_dir, "run_upstream.py")
            
            if os.path.exists(run_upstream) and os.path.exists(potential_config):
                return potential_config
            
            current_dir = os.path.dirname(current_dir)
        
        return None
    
    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """
        获取配置值，支持默认值fallback
        
        Args:
            section: 配置段名
            key: 配置键名
            fallback: 默认值
            
        Returns:
            str: 配置值
        """
        # 首先尝试从配置文件获取
        if self.config.has_section(section) and self.config.has_option(section, key):
            return self.config.get(section, key)
        
        # 然后尝试从默认值获取
        if section in self.DEFAULT_VALUES and key in self.DEFAULT_VALUES[section]:
            return self.DEFAULT_VALUES[section][key]
        
        # 最后返回fallback
        if fallback is not None:
            return str(fallback)
        
        raise KeyError(f"配置项不存在: [{section}] {key}")
    
    def get_int(self, section: str, key: str, fallback: int = None) -> int:
        """获取整数配置值"""
        value = self.get(section, key, fallback)
        return int(value)
    
    def get_float(self, section: str, key: str, fallback: float = None) -> float:
        """获取浮点数配置值"""
        value = self.get(section, key, fallback)
        return float(value)
    
    def get_bool(self, section: str, key: str, fallback: bool = None) -> bool:
        """获取布尔配置值"""
        value = self.get(section, key, fallback)
        if isinstance(value, bool):
            return value
        return str(value).lower() in ('1', 'true', 'yes', 'on')
    
    def get_list(self, section: str, key: str, separator: str = ',', fallback: list = None) -> list:
        """获取列表配置值"""
        try:
            value = self.get(section, key)
            return [item.strip() for item in value.split(separator) if item.strip()]
        except KeyError:
            if fallback is not None:
                return fallback
            raise
    
    def get_database_path(self, db_key: str, db_root: str) -> str:
        """
        获取数据库路径，支持模板替换
        
        Args:
            db_key: 数据库键名
            db_root: 数据库根目录
            
        Returns:
            str: 数据库路径
        """
        # 首先尝试从配置文件获取
        if self.config.has_section('database') and self.config.has_option('database', db_key):
            return self.config.get('database', db_key)
        
        # 然后尝试从模板生成
        template_key = f"{db_key}"
        if template_key in self.DEFAULT_VALUES['database_templates']:
            template = self.DEFAULT_VALUES['database_templates'][template_key]
            return template.format(db_root=db_root)
        
        raise KeyError(f"数据库路径不存在: {db_key}")
    
    def get_env_config(self, tool_name: str) -> Dict[str, Optional[str]]:
        """
        获取工具的环境配置
        
        Args:
            tool_name: 工具名称
            
        Returns:
            Dict: 环境配置字典
        """
        env_config = {
            'conda_activate': None,
            'module_unload': None,
            'module_load': None,
        }
        
        if self.config.has_section('environment'):
            # 主环境配置
            if tool_name == 'main':
                env_config['conda_activate'] = self.config.get('environment', 'main_conda_activate', fallback=None)
                env_config['module_load'] = self.config.get('batch', 'main_module_load', fallback=None)
            else:
                # 特定工具环境配置
                env_config['conda_activate'] = self.config.get('environment', f'{tool_name}_conda_activate', fallback=None)
                env_config['module_unload'] = self.config.get('environment', f'{tool_name}_module_unload', fallback=None)
        
        return env_config
    
    def get_constant(self, key: str) -> Any:
        """获取常量值"""
        if key in self.DEFAULT_VALUES['constants']:
            return self.DEFAULT_VALUES['constants'][key]
        raise KeyError(f"常量不存在: {key}")


# 全局配置管理器实例
_config_manager = None


def get_config_manager(config_file: str = "config.ini") -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    return _config_manager


def get_config(config_file: str = "config.ini") -> configparser.ConfigParser:
    """向后兼容的配置获取函数"""
    manager = get_config_manager(config_file)
    return manager.config


# 类别名，向后兼容
Config = ConfigManager