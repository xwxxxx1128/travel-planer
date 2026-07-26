from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserProfile
from app.tools.auth_tool import create_token, hash_password, verify_password

router = APIRouter()


def _to_profile(user: User) -> UserProfile:
    return UserProfile.model_validate(user, from_attributes=True)


@router.get('/users/getUsers/', response_model=list[UserProfile])
def get_users(session: Session = Depends(get_session)):
    return [_to_profile(user) for user in session.query(User).all()]


@router.get('/users/{pk}/', response_model=UserProfile)
def get_by_id(pk: int, session: Session = Depends(get_session)):
    user = session.get(User, pk)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    return _to_profile(user)


@router.post('/register/', response_model=UserProfile)
def register(obj_in: RegisterRequest, session: Session = Depends(get_session)):
    obj_in.username = obj_in.username.strip()
    if session.query(User).filter(User.username == obj_in.username).first():
        raise HTTPException(status_code=409, detail=f'用户名{obj_in.username} 已存在')
    user = User(
        username=obj_in.username,
        password_hash=hash_password(obj_in.password),
        phone=obj_in.phone,
        email=obj_in.email,
        real_name=obj_in.real_name,
        preference=obj_in.preference,
    )
    session.add(user)
    session.flush()
    return _to_profile(user)


@router.post('/login/')
def login(obj_in: LoginRequest, session: Session = Depends(get_session)):
    user = session.query(User).filter(User.username == obj_in.username).first()
    if not user or not verify_password(obj_in.password, user.password_hash):
        raise HTTPException(status_code=401, detail='登录失败')
    return {
        'token': create_token(f'{user.id}:{user.username}'),
        'id': user.id,
        'username': user.username,
        'phone': user.phone,
        'email': user.email,
        'real_name': user.real_name,
        'icon': None,
        'create_time': None,
    }
