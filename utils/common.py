"""
通用工具模块

包含项目中重复使用的代码模式，如目录管理、错误处理等。
"""

import os
import subprocess
import shutil
from typing import Optional, Union
from utils.logging import get_logger, LogManager


def create_simple_logger(name: str, level: str = "INFO"):
    """
    创建简单的日志记录器（向后兼容）
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        
    Returns:
        LogManager: 统一的日志管理器
    """
    return get_logger(f"GutMicrobe-Virus.{name}", level)


def log_error(logger: Union[LogManager, None], message: str, error: Optional[Exception] = None) -> None:
    """
    统一的错误日志记录

    Args:
        logger: 日志记录器
        message: 错误消息
        error: 异常对象（可选）
    """
    if logger is None:
        logger = get_logger()
    
    if hasattr(logger, 'error'):
        if error:
            logger.error(f"{message}: {error}")
        else:
            logger.error(message)
    else:
        # 向后兼容旧的logging.Logger
        if error:
            logger.error(f"{message}: {error}")
        else:
            logger.error(message)


def prepare_directory(directory: str, logger=None) -> bool:
    """
    准备目录（清理并创建）

    Args:
        directory: 目录路径
        logger: 日志记录器（可选）

    Returns:
        bool: 是否成功
    """
    if logger is None:
        logger = get_logger()
        
    if not ensure_directory_clean(directory, logger):
        log_error(logger, f"准备目录失败: {directory}")
        return False
    return True


def safe_remove_directory(directory: str, logger=None) -> bool:
    """
    安全删除目录

    Args:
        directory: 要删除的目录路径
        logger: 日志记录器（可选）

    Returns:
        bool: 是否成功删除
    """
    if logger is None:
        logger = get_logger()
        
    if os.path.exists(directory):
        try:
            shutil.rmtree(directory)
            if hasattr(logger, 'info'):
                logger.info(f"删除目录: {directory}")
            return True
        except Exception as e:
            log_error(logger, f"删除目录失败: {directory}", e)
            return False
    return True


def safe_create_directory(directory: str, logger=None) -> bool:
    """
    安全创建目录

    Args:
        directory: 要创建的目录路径
        logger: 日志记录器（可选）

    Returns:
        bool: 是否成功创建
    """
    if logger is None:
        logger = get_logger()
        
    try:
        os.makedirs(directory, exist_ok=True)
        if hasattr(logger, 'info'):
            logger.info(f"创建目录: {directory}")
        return True
    except Exception as e:
        log_error(logger, f"创建目录失败: {directory}", e)
        return False


# 注意: 命令执行功能已移至 utils.environment 模块
# 请使用 run_command_with_env() 或 EnvironmentManager.run_command()


def safe_remove_file(file_path: str, logger=None) -> bool:
    """
    安全删除文件

    Args:
        file_path: 要删除的文件路径
        logger: 日志记录器（可选）

    Returns:
        bool: 是否成功删除
    """
    if logger is None:
        logger = get_logger()
        
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            if hasattr(logger, 'info'):
                logger.info(f"删除文件: {file_path}")
            return True
        except Exception as e:
            log_error(logger, f"删除文件失败: {file_path}", e)
            return False
    return True


def ensure_directory_clean(directory: str, logger=None) -> bool:
    """
    确保目录干净（删除后重新创建）

    Args:
        directory: 目录路径
        logger: 日志记录器（可选）

    Returns:
        bool: 是否成功
    """
    if not safe_remove_directory(directory, logger):
        return False
    return safe_create_directory(directory, logger)
