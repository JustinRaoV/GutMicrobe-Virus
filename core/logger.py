"""
统一的日志系统模块

提供标准化的日志记录、错误处理和进度跟踪功能。
"""

import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple


class PipelineLogger:
    """流水线日志管理器"""
    
    def __init__(self, output_dir: str, sample: str, log_level: str = "INFO"):
        """
        初始化日志管理器
        
        Args:
            output_dir: 输出目录
            sample: 样本名称
            log_level: 日志级别
        """
        self.output_dir = output_dir
        self.sample = sample
        self.log_level = getattr(logging, log_level.upper())
        
        # 创建日志目录
        self.log_dir = os.path.join(output_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 设置日志文件路径
        self.log_file = os.path.join(self.log_dir, f"{sample}_pipeline.log")
        self.error_file = os.path.join(self.log_dir, f"{sample}_errors.log")
        self.progress_file = os.path.join(self.log_dir, f"{sample}_progress.txt")
        
        # 初始化日志记录器
        self._setup_logger()
        
        # 进度跟踪
        self.start_time = time.time()
        self.current_step = 0
        self.total_steps = 0
    
    def _setup_logger(self):
        """设置日志记录器"""
        # 创建主日志记录器
        self.logger = logging.getLogger(f"pipeline_{self.sample}")
        self.logger.setLevel(self.log_level)
        
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 文件处理器
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(self.log_level)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        
        # 错误文件处理器
        error_handler = logging.FileHandler(self.error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(error_handler)
    
    def info(self, message: str):
        """记录信息日志"""
        self.logger.info(f"[{self.sample}] {message}")
    
    def warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(f"[{self.sample}] {message}")
    
    def error(self, message: str, exc_info: bool = True):
        """记录错误日志"""
        self.logger.error(f"[{self.sample}] {message}", exc_info=exc_info)
    
    def debug(self, message: str):
        """记录调试日志"""
        self.logger.debug(f"[{self.sample}] {message}")
    
    def step_start(self, step_name: str, step_number: int, total_steps: int):
        """记录步骤开始"""
        self.total_steps = total_steps
        self.current_step = step_number
        elapsed = time.time() - self.start_time
        
        message = f"开始步骤 {step_number}/{total_steps}: {step_name}"
        self.info(f"{'='*50}")
        self.info(message)
        self.info(f"已运行时间: {self._format_time(elapsed)}")
        self.info(f"{'='*50}")
        
        # 更新进度文件
        self._update_progress(step_number, step_name, "running")
    
    def step_complete(self, step_name: str, step_number: int):
        """记录步骤完成"""
        elapsed = time.time() - self.start_time
        estimated_total = elapsed * self.total_steps / step_number if step_number > 0 else 0
        remaining = estimated_total - elapsed
        
        message = f"完成步骤 {step_number}/{self.total_steps}: {step_name}"
        self.info(f"{'='*50}")
        self.info(message)
        self.info(f"已运行时间: {self._format_time(elapsed)}")
        if step_number < self.total_steps:
            self.info(f"预计剩余时间: {self._format_time(remaining)}")
        self.info(f"{'='*50}")
        
        # 更新进度文件
        self._update_progress(step_number, step_name, "completed")
    
    def step_failed(self, step_name: str, step_number: int, error: str):
        """记录步骤失败"""
        message = f"步骤 {step_number}/{self.total_steps} 失败: {step_name}"
        self.error(f"{'='*50}")
        self.error(message)
        self.error(f"错误信息: {error}")
        self.error(f"{'='*50}")
        
        # 更新进度文件
        self._update_progress(step_number, step_name, "failed", error)
    
    def _update_progress(self, step_number: int, step_name: str, status: str, error: str = ""):
        """更新进度文件"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        progress_info = {
            "step_number": step_number,
            "step_name": step_name,
            "status": status,
            "timestamp": timestamp,
            "error": error
        }
        
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            f.write(f"当前步骤: {step_number}/{self.total_steps}\n")
            f.write(f"步骤名称: {step_name}\n")
            f.write(f"状态: {status}\n")
            f.write(f"时间戳: {timestamp}\n")
            if error:
                f.write(f"错误: {error}\n")
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    
    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度信息"""
        if os.path.exists(self.progress_file):
            progress = {}
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        progress[key.strip()] = value.strip()
            return progress
        return {}


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, logger: PipelineLogger):
        self.logger = logger
    
    def handle_subprocess_error(self, cmd: str, return_code: int, stderr: str = ""):
        """处理子进程错误"""
        error_msg = f"命令执行失败 (返回码: {return_code}): {cmd}"
        if stderr:
            error_msg += f"\n错误输出: {stderr}"
        
        self.logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def handle_file_error(self, operation: str, file_path: str, error: str):
        """处理文件操作错误"""
        error_msg = f"文件操作失败 ({operation}): {file_path}\n错误: {error}"
        self.logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def handle_config_error(self, config_key: str, error: str):
        """处理配置错误"""
        error_msg = f"配置错误 ({config_key}): {error}"
        self.logger.error(error_msg)
        raise RuntimeError(error_msg)


def create_logger(output_dir: str, sample: str, log_level: str = "INFO") -> Tuple[PipelineLogger, ErrorHandler]:
    """创建日志管理器和错误处理器"""
    logger = PipelineLogger(output_dir, sample, log_level)
    error_handler = ErrorHandler(logger)
    return logger, error_handler 