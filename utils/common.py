"""
通用工具模块

包含项目中重复使用的代码模式，如目录管理、错误处理等。
"""

import os
import subprocess
import shutil
import logging
from typing import Optional


def create_simple_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    创建简单的日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
    
    Returns:
        logging.Logger: 日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 如果已经有处理器，直接返回
    if logger.handlers:
        return logger
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(console_handler)
    
    return logger


def log_error(logger, message: str, error: Optional[Exception] = None) -> None:
    """
    统一的错误日志记录
    
    Args:
        logger: 日志记录器
        message: 错误消息
        error: 异常对象（可选）
    """
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
    if not ensure_directory_clean(directory, logger):
        if logger:
            log_error(logger, f"Failed to prepare directory: {directory}")
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
    if os.path.exists(directory):
        try:
            shutil.rmtree(directory)
            if logger:
                logger.info(f"删除目录: {directory}")
            return True
        except Exception as e:
            error_msg = f"删除目录失败: {directory}"
            if logger:
                log_error(logger, error_msg, e)
            else:
                print(f"Warning: {error_msg}: {e}")
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
    try:
        os.makedirs(directory, exist_ok=True)
        if logger:
            logger.info(f"创建目录: {directory}")
        return True
    except Exception as e:
        error_msg = f"创建目录失败: {directory}"
        if logger:
            log_error(logger, error_msg, e)
        else:
            print(f"Error: {error_msg}: {e}")
        return False


def run_command(cmd: str, logger=None, step_name: str = "command", 
                check_return_code: bool = True, shell: bool = True) -> int:
    """
    运行命令的统一接口
    
    Args:
        cmd: 要执行的命令
        logger: 日志记录器（可选）
        step_name: 步骤名称，用于日志输出
        check_return_code: 是否检查返回码
        shell: 是否使用shell执行
    
    Returns:
        int: 命令的返回码
    """
    if logger:
        logger.info(f"[{step_name}] Running: {cmd}")
    else:
        print(f"[{step_name}] Running: {cmd}")
    
    try:
        if shell:
            ret = subprocess.call(cmd, shell=True)
        else:
            ret = subprocess.call(cmd.split(), shell=False)
        
        if ret != 0 and check_return_code:
            error_msg = f"ERROR: {step_name} failed with return code {ret}"
            if logger:
                logger.error(error_msg)
            else:
                print(error_msg)
            return ret
        
        if logger:
            logger.info(f"[{step_name}] Completed successfully")
        else:
            print(f"[{step_name}] Completed successfully")
        
        return ret
        
    except Exception as e:
        error_msg = f"ERROR: {step_name} failed with exception: {e}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        return -1


def run_command_with_output(cmd: str, logger=None, step_name: str = "command", 
                           shell: bool = True) -> tuple:
    """
    运行命令并返回输出
    
    Args:
        cmd: 要执行的命令
        logger: 日志记录器（可选）
        step_name: 步骤名称，用于日志输出
        shell: 是否使用shell执行
    
    Returns:
        tuple: (返回码, 标准输出, 标准错误)
    """
    if logger:
        logger.info(f"[{step_name}] Running: {cmd}")
    else:
        print(f"[{step_name}] Running: {cmd}")
    
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd.split(), shell=False, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = f"ERROR: {step_name} failed with return code {result.returncode}"
            if logger:
                logger.error(error_msg)
                if result.stderr:
                    logger.error(f"Stderr: {result.stderr}")
            else:
                print(error_msg)
                if result.stderr:
                    print(f"Stderr: {result.stderr}")
        
        return result.returncode, result.stdout, result.stderr
        
    except Exception as e:
        error_msg = f"ERROR: {step_name} failed with exception: {e}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        return -1, "", str(e)


def safe_remove_file(file_path: str, logger=None) -> bool:
    """
    安全删除文件
    
    Args:
        file_path: 要删除的文件路径
        logger: 日志记录器（可选）
    
    Returns:
        bool: 是否成功删除
    """
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            if logger:
                logger.info(f"删除文件: {file_path}")
            return True
        except Exception as e:
            error_msg = f"删除文件失败: {file_path}"
            if logger:
                log_error(logger, error_msg, e)
            else:
                print(f"Warning: {error_msg}: {e}")
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