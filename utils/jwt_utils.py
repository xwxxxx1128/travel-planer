from datetime import datetime, timedelta
from typing import Union, Any

from jose import jwt

from config import settings
from app.core.config import settings as app_settings

# 统一密钥来源：与 app.core.config 的 SECRET_KEY 保持一致，
# 不再使用 config/development.yml 的 JWT_SECRET_KEY（已废弃，避免两套密钥不一致）。
ACCESS_TOKEN_EXPIRE_MINUTES = app_settings.ACCESS_TOKEN_EXPIRE_MINUTES
ALGORITHM = settings.ALGORITHM
JWT_SECRET_KEY = app_settings.SECRET_KEY


def create_token(subject: Union[str, Any], expires_delta: int = None) -> str:
    """
    根据用户的信息创建一个token。
    subject ---> token  未来， token ---> subject
    :param subject: 用户信息
    :param expires_delta: 有效时间戳
    :return:
    """
    if expires_delta:
        # 自定义token的过期时间
        expires_delta = datetime.now(tz=None) + expires_delta
    else:
        # 默认的token过期时间
        expires_delta = datetime.now(tz=None) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # 根据subject和过期时间生成一个token
    return jwt.encode({'exp': expires_delta, 'sub': str(subject)}, JWT_SECRET_KEY, ALGORITHM)


if __name__ == '__main__':
    print(create_token('lisi'))
