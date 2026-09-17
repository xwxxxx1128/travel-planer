from __future__ import annotations

import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _needs_build(frontend_dir: Path, frontend_dist: Path) -> bool:
    """判断前端源码是否比构建产物更新。

    原实现只要 dist 存在就跳过构建，导致改了前端却用 python main.py 启动时
    前端永远不更新（刷新浏览器也没用）。这里改为按 mtime 判断。
    """
    index = frontend_dist / 'index.html'
    if not index.exists():
        return True
    newest = 0.0
    for name in ('src', 'index.html', 'vite.config.js', 'package.json'):
        target = frontend_dir / name
        if target.is_file():
            newest = max(newest, target.stat().st_mtime)
        elif target.is_dir():
            for path in target.rglob('*'):
                if path.is_file():
                    newest = max(newest, path.stat().st_mtime)
    return newest > index.stat().st_mtime


def build_frontend(base_dir: Path) -> None:
    frontend_dir = base_dir / 'frontend'
    frontend_dist = frontend_dir / 'dist'

    if not frontend_dir.exists():
        print(f'[warn] Frontend directory not found: {frontend_dir}', file=sys.stderr)
        return

    if frontend_dist.exists() and not _needs_build(frontend_dir, frontend_dist):
        print('[info] Frontend dist is up to date, skip build.')
        return

    print('[info] Frontend needs build, building...')
    try:
        subprocess.run(['npm', 'run', 'build'], cwd=frontend_dir, check=True)
    except FileNotFoundError:
        print('[warn] npm not found; backend will start without building frontend.', file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        print(f'[warn] Frontend build failed: {exc}', file=sys.stderr)


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    build_frontend(base_dir)

    from app.main import create_app

    app = create_app()

    import uvicorn

    browser_url = 'http://127.0.0.1:8000/ui'

    def _open_browser() -> None:
        time.sleep(1.5)
        webbrowser.open_new_tab(browser_url)

    threading.Thread(target=_open_browser, daemon=True).start()
    print(f'[info] Open in browser: {browser_url}')
    # 注意：这里必须传 app 对象且不要开启 reload/workers。uvicorn 要求 reload/workers
    # 只能配合“导入字符串”（如 'app.main:app'）使用；若传 app 对象又开 reload，uvicorn 会
    # 打印 warning 后直接 sys.exit(1)，导致服务根本没启动（浏览器表现为 Network Error）。
    uvicorn.run(app, host='0.0.0.0', port=8000)#异步web服务器
    # uvicorn.run(app, host='0.0.0.0', port=8000, reload=True)生产环境应该禁止热重载


class Server:
    def __init__(self):
        base_dir = Path(__file__).resolve().parent
        build_frontend(base_dir)
        from app.main import create_app
        self.app = create_app()


if __name__ == '__main__':
    main()
