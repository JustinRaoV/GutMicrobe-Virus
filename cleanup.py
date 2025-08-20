#!/usr/bin/env python3
"""
GutMicrobe-Virus 项目清理工具

清理项目中的临时文件、日志文件和无用目录
"""

import os
import shutil
import argparse
import logging
from pathlib import Path
from typing import List


def setup_logging(level: str = "INFO") -> logging.Logger:
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def clean_directories(base_dir: str, logger: logging.Logger) -> int:
    """
    清理指定的目录
    
    Args:
        base_dir: 项目根目录
        logger: 日志记录器
        
    Returns:
        int: 清理的项目数量
    """
    cleaned_count = 0
    
    # 需要清理的目录列表
    dirs_to_clean = [
        "result",
        "libresult", 
        "downstream_out",
        "scripts",
        "logs",
        "busco_downloads"
    ]
    
    for dir_name in dirs_to_clean:
        dir_path = os.path.join(base_dir, dir_name)
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                logger.info(f"删除目录: {dir_path}")
                cleaned_count += 1
            except Exception as e:
                logger.error(f"删除目录失败 {dir_path}: {e}")
    
    return cleaned_count


def clean_files(base_dir: str, logger: logging.Logger) -> int:
    """
    清理指定的文件
    
    Args:
        base_dir: 项目根目录
        logger: 日志记录器
        
    Returns:
        int: 清理的文件数量
    """
    cleaned_count = 0
    
    # 需要清理的文件模式
    file_patterns = [
        "*.log",
        "*.out", 
        "*.err",
        "nohup.out",
        "temp_*",
        "*.tmp",
        "**/temp.txt"
    ]
    
    for pattern in file_patterns:
        for file_path in Path(base_dir).glob(pattern):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    logger.info(f"删除文件: {file_path}")
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"删除文件失败 {file_path}: {e}")
    
    return cleaned_count


def clean_empty_directories(base_dir: str, logger: logging.Logger) -> int:
    """
    清理空目录
    
    Args:
        base_dir: 项目根目录
        logger: 日志记录器
        
    Returns:
        int: 清理的空目录数量
    """
    cleaned_count = 0
    
    # 递归查找并删除空目录
    for root, dirs, files in os.walk(base_dir, topdown=False):
        # 跳过项目根目录和重要目录
        if root == base_dir or any(important in root for important in ['.git', 'core', 'modules', 'utils']):
            continue
            
        # 如果目录为空，删除它
        if not dirs and not files:
            try:
                os.rmdir(root)
                logger.info(f"删除空目录: {root}")
                cleaned_count += 1
            except Exception as e:
                logger.error(f"删除空目录失败 {root}: {e}")
    
    return cleaned_count


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="GutMicrobe-Virus 项目清理工具")
    parser.add_argument("--project-dir", help="项目目录路径", default=".")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       default="INFO", help="日志级别")
    parser.add_argument("--dry-run", action="store_true", 
                       help="仅显示将要清理的内容，不实际删除")
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    project_dir = os.path.abspath(args.project_dir)
    
    if not os.path.exists(project_dir):
        logger.error(f"项目目录不存在: {project_dir}")
        return 1
    
    logger.info(f"开始清理项目: {project_dir}")
    
    if args.dry_run:
        logger.info("*** 试运行模式 - 不会实际删除文件 ***")
    
    total_cleaned = 0
    
    try:
        # 清理目录
        if not args.dry_run:
            dir_count = clean_directories(project_dir, logger)
            total_cleaned += dir_count
            logger.info(f"清理目录: {dir_count} 个")
        
        # 清理文件
        if not args.dry_run:
            file_count = clean_files(project_dir, logger)
            total_cleaned += file_count
            logger.info(f"清理文件: {file_count} 个")
        
        # 清理空目录
        if not args.dry_run:
            empty_dir_count = clean_empty_directories(project_dir, logger)
            total_cleaned += empty_dir_count
            logger.info(f"清理空目录: {empty_dir_count} 个")
        
        if args.dry_run:
            logger.info("试运行完成。使用 --dry-run=false 执行实际清理。")
        else:
            logger.info(f"清理完成！共清理 {total_cleaned} 个项目")
        
        return 0
        
    except Exception as e:
        logger.error(f"清理过程中发生错误: {e}")
        return 1


if __name__ == "__main__":
    exit(main())