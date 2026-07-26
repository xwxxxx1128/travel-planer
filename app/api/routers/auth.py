from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserProfile
from app.tools.auth_tool import create_token, hash_password, verify_password, verify_token

router = APIRouter()


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
    return UserProfile.model_validate(user, from_attributes=True)


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    user = session.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='用户名或密码错误')
    token = create_token(f'{user.id}:{user.username}')
    return TokenResponse(access_token=token, user=UserProfile.model_validate(user, from_attributes=True))


@router.get('/me', response_model=UserProfile)
def me(token: str):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail='无效令牌')
    return UserProfile(id=0, username=str(payload['sub']))
