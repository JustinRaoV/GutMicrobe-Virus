"""
工具执行器

提供统一的子进程执行、错误处理和资源管理功能。
"""

import subprocess
import os
import shutil
import tempfile
from typing import List, Dict, Any, Optional, Union
from contextlib import contextmanager


class CommandExecutor:
    """命令执行器"""
    
    def __init__(self, logger=None, error_handler=None):
        """
        初始化命令执行器
        
        Args:
            logger: 日志记录器
            error_handler: 错误处理器
        """
        self.logger = logger
        self.error_handler = error_handler
    
    def run_command(self, cmd: Union[str, List[str]], 
                   shell: bool = False,
                   check: bool = True,
                   capture_output: bool = False,
                   timeout: Optional[int] = None,
                   cwd: Optional[str] = None,
                   env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        """
        执行命令
        
        Args:
            cmd: 命令字符串或列表
            shell: 是否使用shell执行
            check: 是否检查返回码
            capture_output: 是否捕获输出
            timeout: 超时时间（秒）
            cwd: 工作目录
            env: 环境变量
            
        Returns:
            CompletedProcess对象
            
        Raises:
            RuntimeError: 命令执行失败
        """
        if self.logger:
            if isinstance(cmd, list):
                cmd_str = ' '.join(cmd)
            else:
                cmd_str = cmd
            self.logger.info(f"执行命令: {cmd_str}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=shell,
                check=check,
                capture_output=capture_output,
                timeout=timeout,
                cwd=cwd,
                env=env,
                text=True,
                encoding='utf-8'
            )
            
            if self.logger:
                self.logger.info(f"命令执行成功 (返回码: {result.returncode})")
            
            return result
            
        except subprocess.TimeoutExpired as e:
            error_msg = f"命令执行超时: {cmd}"
            if self.error_handler:
                self.error_handler.handle_subprocess_error(str(cmd), -1, f"超时: {timeout}秒")
            else:
                raise RuntimeError(error_msg)
                
        except subprocess.CalledProcessError as e:
            error_msg = f"命令执行失败 (返回码: {e.returncode})"
            if self.error_handler:
                self.error_handler.handle_subprocess_error(str(cmd), e.returncode, e.stderr)
            else:
                raise RuntimeError(f"{error_msg}: {e}")
    
    def run_shell_command(self, cmd: str, **kwargs) -> subprocess.CompletedProcess:
        """执行shell命令"""
        return self.run_command(cmd, shell=True, **kwargs)
    
    def run_list_command(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """执行命令列表"""
        return self.run_command(cmd, shell=False, **kwargs)


class FileManager:
    """文件管理器"""
    
    def __init__(self, logger=None, error_handler=None):
        """
        初始化文件管理器
        
        Args:
            logger: 日志记录器
            error_handler: 错误处理器
        """
        self.logger = logger
        self.error_handler = error_handler
    
    def ensure_dir(self, dir_path: str, clean: bool = False):
        """
        确保目录存在
        
        Args:
            dir_path: 目录路径
            clean: 是否清理已存在的目录
        """
        if clean and os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                if self.logger:
                    self.logger.info(f"清理目录: {dir_path}")
            except Exception as e:
                error_msg = f"清理目录失败: {dir_path}"
                if self.error_handler:
                    self.error_handler.handle_file_error("清理目录", dir_path, str(e))
                else:
                    raise RuntimeError(f"{error_msg}: {e}")
        
        try:
            os.makedirs(dir_path, exist_ok=True)
            if self.logger:
                self.logger.info(f"创建目录: {dir_path}")
        except Exception as e:
            error_msg = f"创建目录失败: {dir_path}"
            if self.error_handler:
                self.error_handler.handle_file_error("创建目录", dir_path, str(e))
            else:
                raise RuntimeError(f"{error_msg}: {e}")
    
    def copy_file(self, src: str, dst: str, overwrite: bool = True):
        """
        复制文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
            overwrite: 是否覆盖已存在的文件
        """
        if not os.path.exists(src):
            error_msg = f"源文件不存在: {src}"
            if self.error_handler:
                self.error_handler.handle_file_error("复制文件", src, "文件不存在")
            else:
                raise FileNotFoundError(error_msg)
        
        if os.path.exists(dst) and not overwrite:
            if self.logger:
                self.logger.warning(f"目标文件已存在，跳过复制: {dst}")
            return
        
        try:
            # 确保目标目录存在
            dst_dir = os.path.dirname(dst)
            if dst_dir:
                os.makedirs(dst_dir, exist_ok=True)
            
            shutil.copy2(src, dst)
            if self.logger:
                self.logger.info(f"复制文件: {src} -> {dst}")
        except Exception as e:
            error_msg = f"复制文件失败: {src} -> {dst}"
            if self.error_handler:
                self.error_handler.handle_file_error("复制文件", f"{src} -> {dst}", str(e))
            else:
                raise RuntimeError(f"{error_msg}: {e}")
    
    def remove_file(self, file_path: str, ignore_missing: bool = True):
        """
        删除文件
        
        Args:
            file_path: 文件路径
            ignore_missing: 是否忽略文件不存在的情况
        """
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                if self.logger:
                    self.logger.info(f"删除文件: {file_path}")
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                if self.logger:
                    self.logger.info(f"删除目录: {file_path}")
        except FileNotFoundError:
            if not ignore_missing:
                raise
        except Exception as e:
            error_msg = f"删除文件失败: {file_path}"
            if self.error_handler:
                self.error_handler.handle_file_error("删除文件", file_path, str(e))
            else:
                raise RuntimeError(f"{error_msg}: {e}")
    
    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(file_path)
    
    def get_file_size(self, file_path: str) -> int:
        """获取文件大小"""
        if not self.file_exists(file_path):
            return 0
        return os.path.getsize(file_path)
    
    def is_file_empty(self, file_path: str) -> bool:
        """检查文件是否为空"""
        return self.get_file_size(file_path) == 0


class EnvironmentManager:
    """环境管理器"""
    
    def __init__(self, logger=None):
        """
        初始化环境管理器
        
        Args:
            logger: 日志记录器
        """
        self.logger = logger
    
    @contextmanager
    def conda_environment(self, module_unload: str = "", conda_activate: str = ""):
        """
        临时激活conda环境
        
        Args:
            module_unload: module unload命令
            conda_activate: conda activate命令
        """
        original_env = os.environ.copy()
        
        try:
            if module_unload:
                if self.logger:
                    self.logger.info(f"执行module unload: {module_unload}")
                # 这里可以添加实际的module unload逻辑
            
            if conda_activate:
                if self.logger:
                    self.logger.info(f"激活conda环境: {conda_activate}")
                # 这里可以添加实际的conda activate逻辑
            
            yield
            
        finally:
            # 恢复原始环境
            os.environ.clear()
            os.environ.update(original_env)
            if self.logger:
                self.logger.info("恢复原始环境")


class PipelineExecutor:
    """流水线执行器"""
    
    def __init__(self, logger=None, error_handler=None):
        """
        初始化流水线执行器
        
        Args:
            logger: 日志记录器
            error_handler: 错误处理器
        """
        self.logger = logger
        self.error_handler = error_handler
        self.command_executor = CommandExecutor(logger, error_handler)
        self.file_manager = FileManager(logger, error_handler)
        self.env_manager = EnvironmentManager(logger)
    
    def execute_step(self, step_name: str, step_func, **kwargs):
        """
        执行流水线步骤
        
        Args:
            step_name: 步骤名称
            step_func: 步骤函数
            **kwargs: 传递给步骤函数的参数
        """
        if self.logger:
            self.logger.info(f"开始执行步骤: {step_name}")
        
        try:
            # 将执行器实例添加到参数中
            kwargs['executor'] = self
            
            # 执行步骤
            result = step_func(**kwargs)
            
            if self.logger:
                self.logger.info(f"步骤执行成功: {step_name}")
            
            return result
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"步骤执行失败: {step_name}", exc_info=True)
            raise


# 全局执行器实例
_executor = None


def get_executor(logger=None, error_handler=None) -> PipelineExecutor:
    """获取全局执行器实例"""
    global _executor
    if _executor is None:
        _executor = PipelineExecutor(logger, error_handler)
    return _executor 