# -*- coding: utf-8 -*-
"""
日志配置模块
提供统一的日志记录功能，替代 print() 语句
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    设置并返回一个日志记录器

    Args:
        name: 日志器名称（通常是 __name__）
        level: 日志级别
        log_file: 日志文件路径（可选）
        format_string: 日志格式字符串

    Returns:
        配置好的 Logger 对象
    """
    if format_string is None:
        format_string = (
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
        )

    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（可选）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取一个日志记录器（使用默认配置）

    Args:
        name: 日志器名称

    Returns:
        Logger 对象
    """
    # 检查是否已经配置过
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # 使用默认配置设置
    return setup_logger(name)


def set_global_level(level: int):
    """
    设置全局日志级别

    Args:
        level: logging 模块定义的级别
    """
    logging.root.setLevel(level)


# 预定义的日志级别别名
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


# 快捷函数（不推荐，建议使用 get_logger 获取实例）
def debug(msg: str, *args, **kwargs):
    logging.getLogger("app").debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    logging.getLogger("app").info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    logging.getLogger("app").warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    logging.getLogger("app").error(msg, *args, **kwargs)
