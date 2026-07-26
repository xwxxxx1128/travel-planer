import jwt
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from utils.password_hash import get_hashed_password as hash_password, verify_password as _verify_password


SECRET = settings.SECRET_KEY
ALGORITHM = 'HS256'


def create_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {'sub': subject, 'exp': int(expire.timestamp())}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except Exception:
        return None


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _verify_password(plain, hashed)
    except Exception:
        return False
