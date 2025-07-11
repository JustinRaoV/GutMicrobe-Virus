"""
性能监控模块

提供资源使用监控、性能分析和优化建议功能。
"""

import os
import time
import psutil
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ResourceUsage:
    """资源使用情况"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, log_file: Optional[str] = None, interval: float = 5.0):
        """
        初始化性能监控器
        
        Args:
            log_file: 日志文件路径
            interval: 监控间隔（秒）
        """
        self.log_file = log_file
        self.interval = interval
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.resource_history: List[ResourceUsage] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # 获取初始状态
        try:
            self.initial_io = psutil.disk_io_counters()
            self.initial_net = psutil.net_io_counters()
        except Exception:
            self.initial_io = None
            self.initial_net = None
    
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.start_time = time.time()
        self.resource_history.clear()
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        self.end_time = time.time()
        
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                usage = self._get_current_usage()
                self.resource_history.append(usage)
                
                # 写入日志文件
                if self.log_file:
                    self._write_log_entry(usage)
                
                time.sleep(self.interval)
            except Exception as e:
                print(f"监控错误: {e}")
                time.sleep(self.interval)
    
    def _get_current_usage(self) -> ResourceUsage:
        """获取当前资源使用情况"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            
            # 磁盘IO
            current_io = psutil.disk_io_counters()
            if current_io and self.initial_io:
                disk_io_read_mb = (current_io.read_bytes - self.initial_io.read_bytes) / (1024 * 1024)
                disk_io_write_mb = (current_io.write_bytes - self.initial_io.write_bytes) / (1024 * 1024)
            else:
                disk_io_read_mb = 0
                disk_io_write_mb = 0
            
            # 网络IO
            current_net = psutil.net_io_counters()
            if current_net and self.initial_net:
                network_sent_mb = (current_net.bytes_sent - self.initial_net.bytes_sent) / (1024 * 1024)
                network_recv_mb = (current_net.bytes_recv - self.initial_net.bytes_recv) / (1024 * 1024)
            else:
                network_sent_mb = 0
                network_recv_mb = 0
            
            return ResourceUsage(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                disk_io_read_mb=disk_io_read_mb,
                disk_io_write_mb=disk_io_write_mb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb
            )
        except Exception as e:
            print(f"获取资源使用情况失败: {e}")
            # 返回默认值
            return ResourceUsage(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                disk_io_read_mb=0.0,
                disk_io_write_mb=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0
            )
    
    def _write_log_entry(self, usage: ResourceUsage):
        """写入日志条目"""
        if not self.log_file:
            return
            
        try:
            with open(self.log_file, 'a') as f:
                log_entry = {
                    'timestamp': datetime.fromtimestamp(usage.timestamp).isoformat(),
                    'cpu_percent': usage.cpu_percent,
                    'memory_percent': usage.memory_percent,
                    'memory_used_mb': usage.memory_used_mb,
                    'disk_io_read_mb': usage.disk_io_read_mb,
                    'disk_io_write_mb': usage.disk_io_write_mb,
                    'network_sent_mb': usage.network_sent_mb,
                    'network_recv_mb': usage.network_recv_mb
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"写入监控日志失败: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        if not self.resource_history:
            return {}
        
        cpu_values = [u.cpu_percent for u in self.resource_history]
        memory_values = [u.memory_percent for u in self.resource_history]
        
        total_time = 0.0
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
        
        return {
            'monitoring_duration': total_time,
            'cpu': {
                'avg': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory': {
                'avg': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values)
            },
            'total_disk_read_mb': sum(u.disk_io_read_mb for u in self.resource_history),
            'total_disk_write_mb': sum(u.disk_io_write_mb for u in self.resource_history),
            'total_network_sent_mb': sum(u.network_sent_mb for u in self.resource_history),
            'total_network_recv_mb': sum(u.network_recv_mb for u in self.resource_history)
        }
    
    def get_optimization_suggestions(self) -> List[str]:
        """获取优化建议"""
        suggestions = []
        summary = self.get_summary()
        
        if not summary:
            return suggestions
        
        # 从配置文件获取阈值
        from core.config_manager import get_config
        config = get_config()
        cpu_high_threshold = float(config['parameters']['monitor_cpu_high_threshold'])
        cpu_low_threshold = float(config['parameters']['monitor_cpu_low_threshold'])
        memory_high_threshold = float(config['parameters']['monitor_memory_high_threshold'])
        disk_io_threshold = float(config['parameters']['monitor_disk_io_threshold'])
        
        # CPU使用率建议
        if summary['cpu']['avg'] > cpu_high_threshold:
            suggestions.append("CPU使用率较高，建议增加线程数或优化算法")
        elif summary['cpu']['avg'] < cpu_low_threshold:
            suggestions.append("CPU使用率较低，可以考虑增加并行度")
        
        # 内存使用建议
        if summary['memory']['avg'] > memory_high_threshold:
            suggestions.append("内存使用率较高，建议增加内存或优化内存使用")
        
        # 磁盘IO建议
        total_disk_io = summary['total_disk_read_mb'] + summary['total_disk_write_mb']
        if total_disk_io > disk_io_threshold:  # 1GB
            suggestions.append("磁盘IO较大，建议使用SSD或优化文件操作")
        
        return suggestions


class StepProfiler:
    """步骤性能分析器"""
    
    def __init__(self, logger: Optional[Any] = None):
        """
        初始化步骤性能分析器
        
        Args:
            logger: 日志记录器
        """
        self.logger = logger
        self.step_times: Dict[str, float] = {}
        self.step_start_times: Dict[str, float] = {}
        self.monitor: Optional[PerformanceMonitor] = None
    
    def start_step(self, step_name: str):
        """开始步骤计时"""
        self.step_start_times[step_name] = time.time()
        
        if self.logger:
            self.logger.info(f"开始性能监控: {step_name}")
    
    def end_step(self, step_name: str):
        """结束步骤计时"""
        if step_name in self.step_start_times:
            duration = time.time() - self.step_start_times[step_name]
            self.step_times[step_name] = duration
            
            if self.logger:
                self.logger.info(f"步骤完成: {step_name}, 耗时: {duration:.2f}秒")
    
    def get_step_summary(self) -> Dict[str, float]:
        """获取步骤时间摘要"""
        return self.step_times.copy()
    
    def get_total_time(self) -> float:
        """获取总耗时"""
        return sum(self.step_times.values())
    
    def get_slowest_steps(self, top_n: int = 5) -> List[tuple]:
        """获取最慢的步骤"""
        sorted_steps = sorted(self.step_times.items(), key=lambda x: x[1], reverse=True)
        return sorted_steps[:top_n]


def create_monitor(log_file: Optional[str] = None, interval: float = 5.0) -> PerformanceMonitor:
    """创建性能监控器"""
    return PerformanceMonitor(log_file, interval)


def create_profiler(logger: Optional[Any] = None) -> StepProfiler:
    """创建步骤性能分析器"""
    return StepProfiler(logger) 