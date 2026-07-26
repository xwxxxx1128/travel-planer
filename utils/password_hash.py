import bcrypt

# 密码哈希的算法：bcrypt
# 直接使用 bcrypt 原生 API，避免 passlib 1.7.4 与新版 bcrypt 的兼容性问题
# （passlib 1.7.4 读取 bcrypt.__about__.__version__ 会报 AttributeError）


def get_hashed_password(password: str) -> str:
    """
    接受一个真实的密码，返回一个hash之后的密文
    :param password: 明文密码
    :return: hash之后的密文字符串
    """
    # bcrypt 需要字节串，因此先编码；返回时解码成普通字符串方便存库
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed_pass: str) -> bool:
    """
    校验密码是否正确
    :param password: 传入的明文密码
    :param hashed_pass: hash之后密文
    :return: 校验是否通过
    """
    # 兼容数据库里存的是 str 类型的情况，统一转成 bytes
    if isinstance(hashed_pass, str):
        hashed_pass = hashed_pass.encode('utf-8')
    return bcrypt.checkpw(password.encode('utf-8'), hashed_pass)
