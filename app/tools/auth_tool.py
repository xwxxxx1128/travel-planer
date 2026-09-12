import jwt
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from utils.password_hash import get_hashed_password as hash_password, verify_password as _verify_password


SECRET = settings.SECRET_KEY
ALGORITHM = 'HS256'

# 令牌类型：access 用于访问接口，refresh 仅用于换取新的 access（不能直接访问业务接口）
TOKEN_TYPE_ACCESS = 'access'
TOKEN_TYPE_REFRESH = 'refresh'


def create_token(
    subject: str,
    token_type: str = TOKEN_TYPE_ACCESS,
    expires_minutes: int | None = None,
) -> str:
    """签发 JWT。

    :param subject: 主题，本项目为 '{user_id}:{username}'
    :param token_type: 'access' | 'refresh'
    :param expires_minutes: 自定义有效期（分钟），缺省按令牌类型取配置值
    """
    if expires_minutes is None:
        expires_minutes = (
            settings.REFRESH_TOKEN_EXPIRE_MINUTES
            if token_type == TOKEN_TYPE_REFRESH
            else settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {'sub': subject, 'exp': int(expire.timestamp()), 'type': token_type}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def create_access_token(subject: str) -> str:
    return create_token(subject, TOKEN_TYPE_ACCESS)


def create_refresh_token(subject: str) -> str:
    return create_token(subject, TOKEN_TYPE_REFRESH)


def verify_token(token: str, expected_type: str | None = None) -> dict | None:
    """校验并解码 JWT；签名/过期不合法返回 None。

    :param expected_type: 若给定，则要求令牌 type 与其一致（如访问接口时要求 'access'）。
                         为兼容历史令牌（无 type 字段），缺省按 access 处理。
    """
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except Exception:
        return None
    if expected_type is not None:
        token_type = payload.get('type', TOKEN_TYPE_ACCESS)
        if token_type != expected_type:
            return None
    return payload


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _verify_password(plain, hashed)
    except Exception:
        return False
