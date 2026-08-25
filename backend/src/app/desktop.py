"""The entry point behind the double-clickable build.

A packaged copy has no terminal to type into and no dev servers to start,
so this does the whole job: pick a port, start the server, open the
browser, and stay up until the user closes the window. Everything it prints
is written for someone who has never used a terminal - that console window
is the app's only status display.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from app.config import get_db_path

# Not one of the usual dev ports: a packaged copy may well be running on a
# machine that also has something on 3000/5000/8000, and a first-run port
# clash is exactly the kind of failure this build exists to avoid.
DEFAULT_PORT = 8123
HOST = "127.0.0.1"


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def choose_port() -> int:
    """DEFAULT_PORT when it's free, then a few neighbours, then whatever the
    OS hands out. Trying neighbours first keeps the URL stable and typeable
    across restarts; the ephemeral fallback is what stops a busy machine
    from being unable to start the app at all."""
    if _port_is_free(DEFAULT_PORT):
        return DEFAULT_PORT
    for offset in range(1, 10):
        if _port_is_free(DEFAULT_PORT + offset):
            return DEFAULT_PORT + offset
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def _open_browser_when_ready(url: str, port: int, timeout: float = 30.0) -> None:
    """Waits for the server to actually accept connections before opening a
    tab. Opening immediately races the startup work (schema migration, rule
    reconciliation) and lands the user on a connection-refused page."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((HOST, port)) == 0:
                break
        time.sleep(0.2)
    else:
        print(f"The app is taking longer than usual to start. Try opening {url} yourself.")
        return

    if not webbrowser.open(url):
        print(f"Couldn't open your browser automatically - open {url} yourself.")


def main() -> int:
    port = choose_port()
    url = f"http://{HOST}:{port}/"

    print("SpendTrack")
    print("----------")
    print(f"Your data:  {get_db_path()}")
    print(f"Open at:    {url}")
    print()
    print("Everything runs on this computer - nothing is uploaded anywhere.")
    print("Closing this window shuts the app down. Your data is saved as you go.")
    print()

    # Both spellings, new name first - see config.py's _ENV_ALIASES.
    no_browser = os.environ.get("SPENDTRACK_NO_BROWSER") or os.environ.get("SG_TRACKER_NO_BROWSER")
    if no_browser != "1":
        threading.Thread(target=_open_browser_when_ready, args=(url, port), daemon=True).start()

    # Imported here rather than at module scope so the messages above appear
    # immediately - importing the app pulls in FastAPI, pdfplumber and the
    # rule bank, which is a visible pause in a frozen build.
    from app.main import app

    try:
        uvicorn.run(app, host=HOST, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    print("\nStopped. You can close this window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
