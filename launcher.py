"""Local launcher for the web-based measurement console.

The project uses the browser UI as the local program UI. Running this file
starts the local backend and opens the existing web console in the default
browser.
"""

from __future__ import annotations

import argparse
import socket
import threading
import time
import webbrowser

from web_server import serve


def find_free_port(preferred: int) -> int:
    """Return preferred port if available, otherwise ask the OS for one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def open_browser_later(url: str, delay: float = 0.7) -> None:
    def _open() -> None:
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="로컬 웹 UI 실행기")
    parser.add_argument("--host", default="127.0.0.1", help="로컬 실행 주소. 기본값은 127.0.0.1")
    parser.add_argument("--port", type=int, default=8843, help="선호 포트")
    parser.add_argument("--no-open", action="store_true", help="브라우저를 자동으로 열지 않음")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    port = find_free_port(args.port)
    url = f"http://127.0.0.1:{port}/"

    if not args.no_open:
        open_browser_later(url)

    print("=" * 72)
    print("Kinematic Measurement Console - Local Program")
    print("=" * 72)
    print(f"UI    : {url}")
    print("Stop  : Ctrl+C")
    print("=" * 72)
    serve(args.host, port)


if __name__ == "__main__":
    main()
