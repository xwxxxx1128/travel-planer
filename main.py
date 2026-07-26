from __future__ import annotations

import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def build_frontend(base_dir: Path) -> None:
    frontend_dir = base_dir / 'frontend'
    frontend_dist = frontend_dir / 'dist'

    if not frontend_dir.exists():
        print(f'[warn] Frontend directory not found: {frontend_dir}', file=sys.stderr)
        return

    if frontend_dist.exists():
        print('[info] Frontend dist already exists, skip build.')
        return

    print('[info] Frontend dist missing, building once...')
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
    uvicorn.run(app, host='0.0.0.0', port=8000)


class Server:
    def __init__(self):
        base_dir = Path(__file__).resolve().parent
        build_frontend(base_dir)
        from app.main import create_app
        self.app = create_app()


if __name__ == '__main__':
    main()
