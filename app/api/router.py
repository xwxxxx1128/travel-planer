from fastapi import APIRouter

from app.api.routers.auth import router as auth_router
from app.api.routers.plan import router as plan_router
from app.api.routers.maps import router as maps_router
from app.api.routers.poi import router as poi_router
from app.api.routers.legacy_user import router as legacy_user_router
from app.api.routers.crawl import router as crawl_router
from app.api.routers.graph import router as graph_router
from app.api.routers.chat import router as chat_router
from app.api.routers.config import router as config_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix='/auth', tags=['auth'])
api_router.include_router(plan_router, prefix='/travel', tags=['travel'])
api_router.include_router(poi_router, prefix='/knowledge', tags=['knowledge'])
api_router.include_router(crawl_router, prefix='/crawl', tags=['crawl'])
api_router.include_router(graph_router, prefix='/graph', tags=['graph'])
api_router.include_router(chat_router, tags=['chat'])
api_router.include_router(maps_router, tags=['maps'])
api_router.include_router(config_router, prefix='/config', tags=['config'])
api_router.include_router(legacy_user_router, tags=['legacy-user'])
