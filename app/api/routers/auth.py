from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)
from app.tools.auth_tool import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)

router = APIRouter()


def _subject(user: User) -> str:
    return f'{user.id}:{user.username}'


def _to_profile(user: User) -> UserProfile:
    return UserProfile.model_validate(user, from_attributes=True)


@router.post('/register', response_model=UserProfile)
def register(payload: RegisterRequest, session: Session = Depends(get_session)):
    exists = session.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=409, detail='用户名已存在')
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        phone=payload.phone,
        email=payload.email,
        real_name=payload.real_name,
        preference=payload.preference,
    )
    session.add(user)
    session.flush()
    return _to_profile(user)


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    user = session.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='用户名或密码错误')
    return TokenResponse(
        access_token=create_access_token(_subject(user)),
        refresh_token=create_refresh_token(_subject(user)),
        user=_to_profile(user),
    )


@router.post('/refresh', response_model=TokenResponse)
def refresh(payload: RefreshRequest, session: Session = Depends(get_session)):
    """用刷新令牌换取新的访问令牌（访问令牌过期后前端静默续期）。"""
    data = verify_token(payload.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    if not data:
        raise HTTPException(status_code=401, detail='刷新令牌无效或已过期，请重新登录')
    _user_id, _, username = str(data.get('sub', '')).partition(':')
    user = (
        session.query(User).filter(User.username == username).first()
        if username
        else None
    )
    if not user:
        raise HTTPException(status_code=401, detail='用户不存在，请重新登录')
    return TokenResponse(
        access_token=create_access_token(_subject(user)),
        refresh_token=create_refresh_token(_subject(user)),
        user=_to_profile(user),
    )


@router.get('/me', response_model=UserProfile)
def me(
    current: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """校验并返回当前登录用户信息（令牌从 Authorization 头读取，不再走 URL query）。"""
    user = session.get(User, current['id'])
    if not user:
        raise HTTPException(status_code=401, detail='无效令牌')
    return _to_profile(user)
