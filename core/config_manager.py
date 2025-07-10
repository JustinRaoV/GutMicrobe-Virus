"""
配置管理器

提供统一的配置读取、验证和管理功能。
"""

import configparser

def get_config(config_file="config.ini"):
    config = configparser.ConfigParser()
    with open(config_file, encoding="utf-8") as f:
        config.read_file(f)
    return config 