"""Desktop launcher — runs Flask in a background thread and opens the app
inside a native WebView2 window (no external browser, no port popup).

Why:
- Eliminates the "browser opens, port conflicts, tabs get closed" issues
  the operator saw while testing.
- Looks and feels like a standalone desktop program.
- On Windows, uses the Edge WebView2 runtime that ships with Windows 10+.

Usage:
    venv\\Scripts\\python.exe desktop.py

start.bat calls this by default. To still run the plain browser version
(for dev), use:  venv\\Scripts\\python.exe run.py
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time

# Ensure app is importable and CWD is the repo root.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

from app import create_app  # noqa: E402


def _pick_free_port() -> int:
    """Bind a random free port on localhost — eliminates 5060/5061 collisions."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_until_up(port: int, timeout: float = 15.0):
    """Poll the Flask server until it accepts connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def run_flask(port: int):
    """Start Flask in-thread. Uses the dev server — fine for a one-user
    sandbox. debug=False so the reloader doesn't double-spawn."""
    app = create_app('development')
    app.run(host='127.0.0.1', port=port, debug=False,
            use_reloader=False, threaded=True)


def main():
    port = _pick_free_port()

    # Start Flask in a daemon thread — it dies when the webview window closes.
    t = threading.Thread(target=run_flask, args=(port,), daemon=True)
    t.start()

    if not _wait_until_up(port):
        print(f'[X] Flask did not start on port {port} within 15s', file=sys.stderr)
        sys.exit(1)

    # Import pywebview lazily so `python run.py` in dev has no extra deps.
    import webview

    url = f'http://127.0.0.1:{port}/login'
    title = 'מתת מרדכי - Matat / ZTorm / Gemach  (SANDBOX)'
    webview.create_window(
        title,
        url,
        width=1400,
        height=900,
        resizable=True,
        confirm_close=False,  # no "are you sure you want to quit" popup
        text_select=True,
        zoomable=True,
    )
    # Default GUI: edgechromium on Windows (WebView2), cef/qt fallback elsewhere.
    webview.start()


if __name__ == '__main__':
    main()
