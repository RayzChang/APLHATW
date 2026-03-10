"""
AlphaTW desktop launcher.

Single-process startup for packaged Windows app:
- prepares writable app home under %APPDATA%\\AlphaTW
- copies bundled .env on first launch
- starts FastAPI (which serves frontend dist)
- opens browser automatically
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def _bundled_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def _app_home() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return (Path(appdata) / "AlphaTW").resolve()
    return (Path.home() / "AlphaTW").resolve()


def _prepare_runtime_home() -> Path:
    home = _app_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "data").mkdir(parents=True, exist_ok=True)
    (home / "database").mkdir(parents=True, exist_ok=True)
    (home / "logs").mkdir(parents=True, exist_ok=True)

    source_env = _bundled_root() / ".env"
    target_env = home / ".env"
    if source_env.exists() and not target_env.exists():
        target_env.write_text(source_env.read_text(encoding="utf-8"), encoding="utf-8")

    return home


def _wait_for_port(host: str, port: int, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def main() -> int:
    home = _prepare_runtime_home()
    os.environ["ALPHATW_HOME"] = str(home)

    host = "127.0.0.1"
    port = int(os.getenv("ALPHATW_PORT", "8000"))
    url = f"http://{host}:{port}"

    print("=" * 58)
    print("AlphaTW Desktop - Starting")
    print(f"Runtime home: {home}")
    print(f"URL: {url}")
    print("=" * 58)

    config = uvicorn.Config("api.app:app", host=host, port=port, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if _wait_for_port(host, port):
        webbrowser.open(url)
    else:
        print("Server startup timeout. Please check logs and firewall settings.")

    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping AlphaTW...")
        server.should_exit = True
        thread.join(timeout=8)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
