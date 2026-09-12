"""共享的 FastAPI 依赖：从 Authorization: Bearer <token> 解析并校验访问令牌。"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.tools.auth_tool import TOKEN_TYPE_ACCESS, verify_token

# auto_error=False：未带凭证时由我们自己返回统一的 401，而不是 FastAPI 默认的 403
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """校验访问令牌，返回 {id, username}；失败抛 401。

    用法：在路由/包含路由处声明 `dependencies=[Depends(get_current_user)]`，
    或在函数参数里 `current=Depends(get_current_user)`。
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='未提供登录凭证，请先登录',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    payload = verify_token(credentials.credentials, expected_type=TOKEN_TYPE_ACCESS)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='登录已失效，请重新登录',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    # sub 形如 "{user_id}:{username}"
    sub = str(payload.get('sub', ''))
    user_id, _, username = sub.partition(':')
    return {
        'id': int(user_id) if user_id.isdigit() else 0,
        'username': username or sub,
    }
