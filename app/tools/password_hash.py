"""密码哈希与校验（bcrypt）。

直接使用 bcrypt 原生 API，避免 passlib 1.7.4 与新版 bcrypt 的兼容性问题
（passlib 1.7.4 读取 bcrypt.__about__.__version__ 会报 AttributeError）。

由 app/tools/auth_tool.py 使用（注册时哈希、登录时校验）。
"""
from __future__ import annotations

import bcrypt


def get_hashed_password(password: str) -> str:
    """接受明文密码，返回哈希后的密文（可直接入库）。"""
    # bcrypt 需要字节串，先编码；返回时解码成普通字符串方便存库
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_pass: str) -> bool:
    """校验明文密码与密文是否匹配。"""
    # 兼容库里存的是 str 类型的情况，统一转成 bytes
    if isinstance(hashed_pass, str):
        hashed_pass = hashed_pass.encode("utf-8")
    return bcrypt.checkpw(password.encode("utf-8"), hashed_pass)
