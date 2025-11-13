"""日志系统"""
import logging
import os
import sys


def setup_logger(name, output_dir=None, level="INFO"):
    """设置日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    # 文件输出
    if output_dir:
        os.makedirs(os.path.join(output_dir, "logs"), exist_ok=True)
        fh = logging.FileHandler(
            os.path.join(output_dir, "logs", f"{name}.log"),
            encoding="utf-8"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    return logger
