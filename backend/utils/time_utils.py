# -*- coding: utf-8 -*-
"""
时间工具函数
"""

from datetime import datetime


def get_current_timestamp() -> str:
    """
    获取当前时间戳（ISO 格式）

    Returns:
        时间戳字符串
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
