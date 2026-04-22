"""Desktop launcher for the TEST server.

Opens the SSH-tunneled /var/www/matat/test instance inside a pywebview
window — same native look as desktop.py, no browser tab. No local Flask:
the app is entirely remote, reached via the SSH tunnel that
start_test.bat opens before calling this script.

The tunnel is expected on 127.0.0.1:18080 (forwarded to matat-server:5051).
"""
from __future__ import annotations

import socket
import sys
import time

TUNNEL_PORT = 18080


def _wait_until_up(port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    if not _wait_until_up(TUNNEL_PORT):
        print(f'[X] SSH tunnel on 127.0.0.1:{TUNNEL_PORT} did not come up '
              'within 15s. Is start_test.bat launching this, and is the '
              'Tailscale link to matat-server up?', file=sys.stderr)
        sys.exit(1)

    import webview

    url = f'http://127.0.0.1:{TUNNEL_PORT}/sandbox-login'
    title = 'מתת מרדכי - Matat / ZTorm / Gemach  (TEST — remote sandbox)'
    webview.create_window(
        title, url,
        width=1400, height=900,
        resizable=True,
        confirm_close=False,
        text_select=True,
        zoomable=True,
    )
    webview.start()


if __name__ == '__main__':
    main()
