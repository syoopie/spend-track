"""Serves the built React UI from the same process as the API.

In development the UI is served by Vite on :5173, which proxies /api to
this backend - two servers, two ports, and nothing here is used. In a
packaged build there is no Vite and no Node: the frontend is compiled to
static files once at build time and shipped inside the executable, so the
one process a user double-clicks has to serve both halves.

`find_webui_dir()` is the only thing that differs between those worlds, and
it deliberately returns None rather than raising when there's no build -
running the backend alone from a checkout is a normal thing to do.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def find_webui_dir() -> Path | None:
    """The compiled frontend, or None when running against a dev server.

    PyInstaller unpacks bundled data under sys._MEIPASS, so that's checked
    first; the repo-relative path is the fallback for `npm run build` in a
    plain checkout (useful for testing the packaged layout without building
    an executable)."""
    bundled = getattr(sys, "_MEIPASS", None)
    candidates = [Path(bundled) / "webui"] if bundled else []
    candidates.append(Path(__file__).resolve().parents[3] / "frontend" / "dist")
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None


def mount_webui(app: FastAPI, webui_dir: Path) -> None:
    """Mounts the SPA: hashed assets straight off disk, every other path
    falling back to index.html so the client-side router owns /rules,
    /settings and friends on a hard refresh."""
    index_file = webui_dir / "index.html"

    assets_dir = webui_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Registered last, so it only ever sees paths no router claimed. An
        # unmatched /api/... path must still fail like an API call rather
        # than quietly returning the HTML shell, which would turn a typo'd
        # endpoint into an unreadable JSON-parse error in the client.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        # A real file (favicon, manifest, anything else Vite emitted at the
        # root) wins over the fallback; path traversal can't escape the
        # build directory because the resolved path is checked against it.
        candidate = (webui_dir / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(webui_dir.resolve()):
            return FileResponse(candidate)

        return FileResponse(index_file)
