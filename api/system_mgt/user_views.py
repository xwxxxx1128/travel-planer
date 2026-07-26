from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserProfile
from app.tools.auth_tool import create_token, verify_token

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
def create(obj_in: RegisterRequest, session: Session = Depends(get_session)):
    obj_in.username = obj_in.username.strip()
    if session.query(User).filter(User.username == obj_in.username).first():
        raise HTTPException(status_code=409, detail=f'用户名{obj_in.username} 已存在')
    user = User(
        username=obj_in.username,
        password_hash=obj_in.password,
        phone=obj_in.phone,
        email=obj_in.email,
        real_name=obj_in.real_name,
        preference=obj_in.preference,
    )
    session.add(user)
    session.flush()
    return _to_profile(user)


@router.post('/login/', response_model=TokenResponse)
def login(obj_in: LoginRequest, session: Session = Depends(get_session)):
    user = session.query(User).filter(User.username == obj_in.username).first()
    if not user or user.password_hash != obj_in.password:
        raise HTTPException(status_code=401, detail='登录失败')
    return TokenResponse(
        access_token=create_token(f'{user.id}:{user.username}'),
        user=_to_profile(user),
    )


@router.post('/auth/')
def auth(form_data = Depends(), session: Session = Depends(get_session)):
    raise HTTPException(status_code=501, detail='OAuth2 form not implemented in lightweight compatibility layer')


@router.patch('/users/{pk}/', response_model=UserProfile)
def patch(pk: int, obj_in: RegisterRequest, session: Session = Depends(get_session)):
    user = session.get(User, pk)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    if obj_in.password:
        user.password_hash = obj_in.password
    user.phone = obj_in.phone
    user.email = obj_in.email
    user.real_name = obj_in.real_name
    user.preference = obj_in.preference
    session.add(user)
    session.flush()
    return _to_profile(user)


@router.post('/users/delete/')
def delete(ids: list[int], session: Session = Depends(get_session)):
    deleted = 0
    for pk in ids:
        user = session.get(User, pk)
        if user:
            session.delete(user)
            deleted += 1
    return {'deleted': deleted}
