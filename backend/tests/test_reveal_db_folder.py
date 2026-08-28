"""Settings' "Show in Finder/Explorer/Files" button.

The endpoint shells out, which is the one thing in this app that does, so
these pin the two properties that make that acceptable: the argv is built
from `get_db_path()` and nothing else (no request body reaches it), and an
environment with no file manager answers rather than raises.
"""

import subprocess

import pytest
from fastapi.testclient import TestClient

from app.routers.data_lifecycle import _reveal_command


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_reveal_launches_the_platform_file_manager(client, monkeypatch):
    launched = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))

    resp = client.post("/api/data-lifecycle/reveal")

    assert resp.status_code == 200
    body = resp.json()
    assert body["opened"] is True
    assert body["error"] is None
    assert len(launched) == 1
    # Whatever the platform's verb is, the DB's own directory is what it names.
    assert body["path"] in " ".join(launched[0])


def test_reveal_reports_a_missing_file_manager_instead_of_raising(client, monkeypatch):
    def no_such_binary(cmd, **kw):
        raise FileNotFoundError(2, "No such file or directory", cmd[0])

    monkeypatch.setattr(subprocess, "Popen", no_such_binary)

    resp = client.post("/api/data-lifecycle/reveal")

    # A headless machine is a legitimate answer, not a 500 - the Settings
    # page shows the reason inline next to the path it already prints.
    assert resp.status_code == 200
    body = resp.json()
    assert body["opened"] is False
    assert body["error"]


def test_reveal_ignores_any_path_in_the_request_body(client, monkeypatch):
    launched = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))

    resp = client.post("/api/data-lifecycle/reveal", json={"path": "/etc/passwd", "new_path": "/etc"})

    assert resp.status_code == 200
    assert "/etc/passwd" not in " ".join(launched[0])
    assert "/etc/passwd" != resp.json()["path"]


@pytest.mark.parametrize(
    "platform, expected_head",
    [("darwin", ["open", "-R"]), ("win32", ["explorer"]), ("linux", ["xdg-open"])],
)
def test_reveal_command_per_platform(monkeypatch, tmp_path, platform, expected_head):
    monkeypatch.setattr("sys.platform", platform)
    target = tmp_path / "folder" / "data.db"

    command = _reveal_command(target)

    assert command[: len(expected_head)] == expected_head
    # macOS and Windows select the file itself; xdg-open has no select verb,
    # so it gets the containing folder instead.
    if platform == "linux":
        assert command[-1] == str(target.parent)
    elif platform == "win32":
        # explorer wants the path glued to the comma, with no space.
        assert command[-1] == f"/select,{target}"
    else:
        assert command[-1] == str(target)
