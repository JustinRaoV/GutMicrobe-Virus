"""
统一日志管理模块

提供一致的日志记录接口和格式化
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional


class LogManager:
    """统一的日志管理器"""
    
    def __init__(self, name: str = "GutMicrobe-Virus", level: str = "INFO"):
        self.name = name
        self.level = getattr(logging, level.upper())
        self.logger = None
        self._setup_logger()
    
    def _setup_logger(self):
        """设置日志记录器"""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.level)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 控制台输出
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            
            # 格式化器
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
    
    def add_file_handler(self, log_file: str, level: str = "INFO"):
        """添加文件日志处理器"""
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, level.upper()))
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
    
    def info(self, message: str):
        """记录信息日志"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """记录错误日志"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """记录调试日志"""
        self.logger.debug(message)
    
    def critical(self, message: str):
        """记录严重错误日志"""
        self.logger.critical(message)


# 全局日志管理器实例
_log_manager = None


def get_logger(name: str = "GutMicrobe-Virus", level: str = "INFO") -> LogManager:
    """获取日志管理器单例"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager(name, level)
    return _log_manager


def setup_module_logger(module_name: str, log_file: Optional[str] = None) -> LogManager:
    """为模块设置专用日志记录器"""
    logger = LogManager(f"GutMicrobe-Virus.{module_name}")
    
    if log_file:
        logger.add_file_handler(log_file)
    
    return logger


def setup_logger(name: str, output_dir: str = None, level: str = "INFO") -> LogManager:
    """设置日志记录器（标准接口）"""
    logger = LogManager(f"GutMicrobe-Virus.{name}", level)
    
    if output_dir:
        log_file = os.path.join(output_dir, "logs", f"{name}.log")
        logger.add_file_handler(log_file, level)
    
    return logger


def log_step(step_name: str, logger: LogManager = None):
    """记录步骤开始"""
    if logger is None:
        logger = get_logger()
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"开始执行步骤: {step_name} [{timestamp}]")


def log_completion(step_name: str, success: bool = True, logger: LogManager = None):
    """记录步骤完成"""
    if logger is None:
        logger = get_logger()
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = "成功" if success else "失败"
    logger.info(f"步骤完成: {step_name} - {status} [{timestamp}]")


def log_command(command: str, logger: LogManager = None):
    """记录执行的命令"""
    if logger is None:
        logger = get_logger()
    
    logger.debug(f"执行命令: {command}")


def log_file_operation(operation: str, file_path: str, logger: LogManager = None):
    """记录文件操作"""
    if logger is None:
        logger = get_logger()
    
    logger.debug(f"文件操作: {operation} - {file_path}")


def log_error_with_context(error: Exception, context: str = "", logger: LogManager = None):
    """记录带上下文的错误"""
    if logger is None:
        logger = get_logger()
    
    error_msg = f"错误: {str(error)}"
    if context:
        error_msg = f"{context} - {error_msg}"
    
    logger.error(error_msg)


# 向后兼容的简单日志函数
def create_logger(log_file: str = None, level: str = "INFO") -> LogManager:
    """创建日志记录器（向后兼容）"""
    logger = get_logger(level=level)
    if log_file:
        logger.add_file_handler(log_file, level)
    return logger


def simple_log(message: str, level: str = "INFO"):
    """简单日志记录（向后兼容）"""
    logger = get_logger()
    
    if level.upper() == "INFO":
        logger.info(message)
    elif level.upper() == "WARNING":
        logger.warning(message)
    elif level.upper() == "ERROR":
        logger.error(message)
    elif level.upper() == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)