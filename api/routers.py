from fastapi import APIRouter, FastAPI

from api.system_mgt import user_views


def router_v1():
    # 主路由
    root_router = APIRouter()
    # 加载所有的分路由
    root_router.include_router(user_views.router, tags=['用户管理'])

    return root_router

# FastAPI 应用 = 你的后端服务器！把路由装到应用中
def init_routers(app: FastAPI):
    app.include_router(router_v1(), prefix='/api')
