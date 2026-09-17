import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import init_db
from app.graph.engine import build_graph
from app.services.scheduler import start_scheduler, shutdown_scheduler
from tools.init_db import sync_flight_dataset


class _HashedAssets(StaticFiles):
    """Vite 产物文件名带内容哈希，可安全长期缓存（内容变了文件名就变）。"""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response


def _index_response(index_path: Path) -> FileResponse:
    """入口 HTML：必须每次回源校验，否则浏览器会一直用旧构建（看不到新增页面）。

    注意：不要用 @app.middleware('http') 统一加缓存头——BaseHTTPMiddleware 会干扰
    /api/chat/stream 的 SSE 流式输出，这里按路由分别处理是安全的。
    """
    response = FileResponse(index_path)
    response.headers['Cache-Control'] = 'no-cache'  # 缓存但每次校验（配合 ETag → 304，开销极小）
    return response


def create_app() -> FastAPI:
    configure_logging()
    init_db()
    build_graph()
    # 航班班次数据集：平移日期到「今天+30 天」为最新，并补齐国内主流航线。
    # 关掉可设 FLIGHT_DATA_SYNC=0；pytest 下会自动跳过。
    sync_flight_dataset()

    base_dir = Path(__file__).resolve().parents[1]
    frontend_dist = base_dir / 'frontend' / 'dist'

    app = FastAPI(title=settings.APP_NAME, version='1.0.0')
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(api_router, prefix='/api')

    # 健康检查与根路径必须注册在 SPA 通配路由之前，否则会被通配路由拦截
    @app.get('/health')
    async def health() -> dict:
        return {'message': 'Ctrip Travel Planner API', 'status': 'ok'}

    @app.get('/api/ui-version', include_in_schema=False)
    async def ui_version() -> dict:
        """前端构建版本哨兵（入口 HTML 的 mtime）。

        前端启动后定时/切回标签页时轮询本接口；一旦发现版本变化就自动刷新，
        免去“必须先手动刷新一次才能看到新增功能”。
        """
        try:
            stamp = int((frontend_dist / 'index.html').stat().st_mtime)
        except OSError:
            stamp = 0
        return {'version': str(stamp)}

    @app.get('/')
    async def root():
        return RedirectResponse(url='/ui', status_code=302)

    if frontend_dist.exists():
        assets_dir = frontend_dist / 'assets'
        if assets_dir.exists():
            app.mount('/assets', _HashedAssets(directory=assets_dir), name='frontend-assets')

        @app.get('/ui', include_in_schema=False)
        async def frontend_index():
            return _index_response(frontend_dist / 'index.html')

        @app.get('/favicon.ico', include_in_schema=False)
        async def favicon():
            icon = frontend_dist / 'favicon.ico'
            if icon.exists():
                return FileResponse(icon)
            return JSONResponse({'detail': 'Not Found'}, status_code=404)

        @app.get('/{full_path:path}', include_in_schema=False)
        async def spa_router(full_path: str):
            normalized_path = full_path.lstrip('/')
            if normalized_path.startswith('api/'):
                return JSONResponse({'detail': 'Not Found'}, status_code=404)
            target = frontend_dist / normalized_path
            if target.exists() and target.is_file():
                return FileResponse(target)
            # SPA 兜底（如 /ui/flights 这类客户端路由）：同样必须每次校验入口 HTML
            return _index_response(frontend_dist / 'index.html')
    else:
        @app.get('/ui', include_in_schema=False)
        async def frontend_missing():
            return HTMLResponse(
                content=(
                    '<html><head><meta charset="utf-8"><title>旅行规划系统</title></head>'
                    '<body style="font-family:Arial,sans-serif;padding:40px;line-height:1.8">'
                    '<h2>旅行规划后端已启动</h2>'
                    '<p>当前未检测到前端构建产物 <code>frontend/dist</code>。</p>'
                    '<p>请先执行：<code>cd frontend && npm run build</code>，再打开 <code>/ui</code>。</p>'
                    '<p><a href="/docs">打开接口文档</a></p>'
                    '</body></html>'
                )
            )

    @app.on_event('startup')
    async def _startup() -> None:
        start_scheduler()

    @app.on_event('shutdown')
    async def _shutdown() -> None:
        shutdown_scheduler()

    return app


app = create_app()


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)



