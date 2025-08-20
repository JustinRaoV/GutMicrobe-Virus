"""
环境管理工具模块

提供统一的conda环境激活和命令执行功能
"""

import os
import subprocess
from typing import Optional, List


def get_safe_conda_command(conda_activate_cmd: Optional[str]) -> str:
    """
    获取安全的conda激活命令，支持多种激活方式的fallback
    
    Args:
        conda_activate_cmd: conda激活命令字符串
        
    Returns:
        str: 安全的conda激活命令
    """
    if not conda_activate_cmd:
        return ""
    
    if 'source activate' in conda_activate_cmd:
        # 提取环境路径
        env_path = conda_activate_cmd.split('source activate')[-1].strip()
        
        # 构建多重fallback策略
        commands = [
            # 1. 尝试初始化conda并激活
            f"eval \"$(conda shell.bash hook)\" && conda activate {env_path}",
            # 2. 尝试直接source activate
            f"source activate {env_path}",
            # 3. 最后fallback到PATH设置
            f"export PATH={env_path}/bin:$PATH"
        ]
        
        return " || ".join(commands)
    else:
        return conda_activate_cmd


def build_command_with_env(base_cmd: str, conda_cmd: Optional[str] = None, 
                          module_cmds: Optional[List[str]] = None) -> str:
    """
    构建带环境激活的完整命令
    
    Args:
        base_cmd: 基础命令
        conda_cmd: conda激活命令
        module_cmds: module命令列表
        
    Returns:
        str: 完整的命令字符串
    """
    commands = []
    
    # 添加module命令
    if module_cmds:
        commands.extend(module_cmds)
    
    # 添加conda激活命令
    if conda_cmd:
        safe_conda_cmd = get_safe_conda_command(conda_cmd)
        if safe_conda_cmd:
            commands.append(safe_conda_cmd)
    
    # 添加基础命令
    commands.append(base_cmd)
    
    return " && ".join(commands)


def run_command_with_env(base_cmd: str, conda_cmd: Optional[str] = None,
                        module_cmds: Optional[List[str]] = None,
                        logger=None, step_name: str = "command", **kwargs) -> int:
    """
    运行带环境激活的命令
    
    Args:
        base_cmd: 基础命令
        conda_cmd: conda激活命令
        module_cmds: module命令列表
        logger: 日志记录器
        step_name: 步骤名称
        **kwargs: 传递给subprocess.run的额外参数
        
    Returns:
        int: 命令返回码
    """
    full_cmd = build_command_with_env(base_cmd, conda_cmd, module_cmds)
    
    if logger:
        logger.info(f"[{step_name}] Running: {full_cmd}")
    
    try:
        # 使用bash执行，确保环境变量和source命令正常工作
        result = subprocess.run(full_cmd, shell=True, check=True, executable='/bin/bash', **kwargs)
        if logger:
            logger.info(f"[{step_name}] Completed successfully")
        return result.returncode
    except subprocess.CalledProcessError as e:
        error_msg = f"[{step_name}] Command failed with return code {e.returncode}"
        if logger:
            logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"[{step_name}] Command failed with exception: {e}"
        if logger:
            logger.error(error_msg)
        raise RuntimeError(error_msg) from e


class EnvironmentManager:
    """环境管理器类（向后兼容）"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
    
    def get_conda_command(self, tool_name: str = "main") -> str:
        """获取conda激活命令"""
        if not self.config_manager:
            return ""
        
        env_config = self.config_manager.get_env_config(tool_name)
        conda_cmd = env_config.get('conda_activate')
        
        return get_safe_conda_command(conda_cmd)
    
    def run_command(self, command: str, tool_name: str = "main", logger=None, **kwargs) -> int:
        """执行命令（主要方法）"""
        if not self.config_manager:
            # 如果没有配置管理器，直接执行命令
            return subprocess.run(command, shell=True, **kwargs).returncode
        
        env_config = self.config_manager.get_env_config(tool_name)
        conda_cmd = env_config.get('conda_activate')
        module_unload = env_config.get('module_unload')
        
        module_cmds = []
        if module_unload:
            module_cmds.append(module_unload)
        
        return run_command_with_env(command, conda_cmd, module_cmds, logger, tool_name, **kwargs)
    
    def execute_with_env(self, tool_name: str, command: str, logger=None) -> int:
        """在指定环境中执行命令（向后兼容）"""
        return self.run_command(command, tool_name, logger)


# 向后兼容的函数别名
def get_conda_command(config_manager, tool_name: str = "main") -> str:
    """获取conda激活命令（向后兼容）"""
    env_manager = EnvironmentManager(config_manager)
    return env_manager.get_conda_command(tool_name)


def execute_with_env(config_manager, tool_name: str, command: str, logger=None) -> int:
    """在指定环境中执行命令（向后兼容）"""
    env_manager = EnvironmentManager(config_manager)
    return env_manager.execute_with_env(tool_name, command, logger)