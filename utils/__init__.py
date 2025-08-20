"""
工具函数模块

包含通用工具函数和路径管理功能。
"""

from .tools import get_sample_name, filter_checkv, final_info, remove_inter_result, make_clean_dir
from .paths import get_paths
from .common import (
    create_simple_logger,
    log_error,
    prepare_directory,
    safe_remove_directory,
    safe_create_directory,
    safe_remove_file,
    ensure_directory_clean,
)
from .environment import (
    EnvironmentManager,
    get_safe_conda_command,
    build_command_with_env,
    run_command_with_env,
    get_conda_command,
    execute_with_env,
)
from .logging import get_logger, LogManager

__all__ = [
    # 工具函数
    "get_sample_name",
    "filter_checkv",
    "final_info",
    "remove_inter_result",
    "make_clean_dir",
    # 路径管理
    "get_paths",
    # 通用工具
    "create_simple_logger",
    "log_error",
    "prepare_directory",
    "safe_remove_directory",
    "safe_create_directory",
    "safe_remove_file",
    "ensure_directory_clean",
    # 环境管理 (推荐使用这些函数进行命令执行)
    "EnvironmentManager",
    "get_safe_conda_command",
    "build_command_with_env",
    "run_command_with_env",
    "get_conda_command",
    "execute_with_env",
    # 日志管理
    "get_logger",
    "LogManager",
]
