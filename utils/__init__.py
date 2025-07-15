"""
工具函数模块

包含通用工具函数和路径管理功能。
"""

from .tools import get_sample_name, filter_checkv, final_info, remove_inter_result
from .paths import get_paths
from .common import (
    create_simple_logger,
    log_error,
    prepare_directory,
    safe_remove_directory,
    safe_create_directory,
    run_command,
    run_command_with_output,
    safe_remove_file,
    ensure_directory_clean,
)

__all__ = [
    # 工具函数
    "get_sample_name",
    "filter_checkv",
    "final_info",
    "remove_inter_result",
    # 路径管理
    "get_paths",
    # 通用工具
    "create_simple_logger",
    "log_error",
    "prepare_directory",
    "safe_remove_directory",
    "safe_create_directory",
    "run_command",
    "run_command_with_output",
    "safe_remove_file",
    "ensure_directory_clean",
]
