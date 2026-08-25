"""The packaged build serves the UI and the API from one process.

In development Vite serves the UI and proxies /api, so none of this code
runs - which is exactly why it needs its own tests. A break here isn't
visible until someone downloads the executable.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.webui import find_webui_dir, mount_webui


@pytest.fixture
def webui_dir(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>shell</title>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text("console.log(1)")
    return tmp_path


@pytest.fixture
def client(webui_dir):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    mount_webui(app, webui_dir)
    return TestClient(app)


def test_api_routes_still_win_over_the_spa_fallback(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_unknown_api_path_404s_instead_of_returning_the_html_shell(client):
    """Returning index.html for a mistyped endpoint turns a 404 into an
    unreadable JSON-parse error in the client."""
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert "text/html" not in resp.headers["content-type"]


def test_client_side_routes_get_the_html_shell(client):
    """A hard refresh on /rules must reach the SPA, not a 404 - the route
    only exists in the browser's router."""
    for path in ("/", "/rules", "/settings", "/guide"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "<title>shell</title>" in resp.text


def test_real_files_at_the_root_are_served_as_themselves(client):
    resp = client.get("/favicon.svg")
    assert resp.status_code == 200
    assert resp.text == "<svg/>"


def test_hashed_assets_are_served(client):
    resp = client.get("/assets/index-abc123.js")
    assert resp.status_code == 200
    assert "console.log" in resp.text


def test_path_traversal_cannot_escape_the_build_directory(client, tmp_path):
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("nope")
    resp = client.get("/../secret.txt")
    # Either the client normalizes it away or the fallback returns the shell;
    # what must never happen is the file's contents coming back.
    assert "nope" not in resp.text


def test_find_webui_dir_prefers_the_bundled_copy(tmp_path, monkeypatch):
    """PyInstaller unpacks bundled data under sys._MEIPASS. A frozen build
    must serve *that* copy, never a stale frontend/dist that happens to
    exist on the machine it's running on."""
    bundled = tmp_path / "webui"
    bundled.mkdir()
    (bundled / "index.html").write_text("<!doctype html>")
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)
    assert find_webui_dir() == bundled


def test_find_webui_dir_ignores_a_bundle_without_a_build(tmp_path, monkeypatch):
    """_MEIPASS with no webui/ inside falls through to the repo-relative
    path rather than returning a directory with no index.html in it."""
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)
    found = find_webui_dir()
    assert found is None or found.name == "dist"
