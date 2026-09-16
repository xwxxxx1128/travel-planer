from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.routers.auth import router as auth_router
from app.api.routers.plan import router as plan_router
from app.api.routers.maps import router as maps_router
from app.api.routers.poi import router as poi_router
from app.api.routers.legacy_user import router as legacy_user_router
from app.api.routers.crawl import router as crawl_router
from app.api.routers.graph import router as graph_router
from app.api.routers.chat import router as chat_router
from app.api.routers.config import router as config_router
from app.api.routers.wishlist import router as wishlist_router

api_router = APIRouter()

# 注册/登录/刷新等公开路由（无需登录）
api_router.include_router(auth_router, prefix='/auth', tags=['auth'])

# 业务路由统一鉴权：需携带 Authorization: Bearer <access_token>
_protected = [Depends(get_current_user)]
api_router.include_router(plan_router, prefix='/travel', tags=['travel'], dependencies=_protected)
api_router.include_router(poi_router, prefix='/knowledge', tags=['knowledge'], dependencies=_protected)
api_router.include_router(crawl_router, prefix='/crawl', tags=['crawl'], dependencies=_protected)
api_router.include_router(graph_router, prefix='/graph', tags=['graph'], dependencies=_protected)
api_router.include_router(chat_router, tags=['chat'], dependencies=_protected)
api_router.include_router(maps_router, tags=['maps'], dependencies=_protected)
api_router.include_router(config_router, prefix='/config', tags=['config'], dependencies=_protected)
api_router.include_router(wishlist_router, prefix='/wishlist', tags=['wishlist'], dependencies=_protected)

# 兼容层用户路由：历史上被测试与旧前端使用，保持公开以免影响既有调用
api_router.include_router(legacy_user_router, tags=['legacy-user'])
