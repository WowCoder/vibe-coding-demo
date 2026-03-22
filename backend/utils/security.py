# -*- coding: utf-8 -*-
"""
安全工具函数
包含密码加密、验证等功能
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    密码加密（使用 bcrypt）

    Args:
        password: 原始密码

    Returns:
        加密后的密码哈希
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码

    Args:
        password: 原始密码
        password_hash: 存储的密码哈希

    Returns:
        验证是否通过
    """
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
