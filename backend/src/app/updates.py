"""The one outbound network call in this app that isn't an AI provider.

A GET to GitHub's public releases API for `syoopie/spend-track`: no auth
header, no request body, no identifier of any kind, and nothing about the
user's data. The result is cached for the life of the process and fired
lazily on the first `/api/version` request, so a running app makes exactly
one such call however long it stays open. It is disclosed in Settings'
About card and in the README, because the app otherwise promises that
nothing leaves the device.
"""

import threading
from importlib.metadata import PackageNotFoundError, version as _installed_version

import httpx

REPO = "syoopie/spend-track"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
TIMEOUT_SECONDS = 3.0

_lock = threading.Lock()
_checked = False
_latest: str | None = None


def current_version() -> str:
    try:
        return _installed_version("spendtrack")
    except PackageNotFoundError:
        return "0.0.0"


def _fetch_latest() -> str | None:
    try:
        resp = httpx.get(
            RELEASES_API,
            timeout=TIMEOUT_SECONDS,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        tag = resp.json().get("tag_name")
        if not isinstance(tag, str):
            return None
        return tag.removeprefix("v")
    # Deliberately broad: a network failure, a rate limit, a changed payload
    # shape - none of them may break the endpoint or app startup. "Unknown"
    # is a legitimate answer here, an exception is not.
    except Exception:
        return None


def _parse(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def _is_newer(latest: str, current: str) -> bool:
    try:
        # `isdigit` is true for characters `int` rejects (superscripts), so
        # the parse can still raise on a tag nobody would tag but anybody
        # could.
        a, b = _parse(latest), _parse(current)
    except ValueError:
        return False
    if not a or not b:
        return False
    return a > b


def get_version_status() -> dict:
    global _checked, _latest
    with _lock:
        if not _checked:
            _latest = _fetch_latest()
            _checked = True
        latest = _latest
    current = current_version()
    return {
        "current": current,
        "latest": latest,
        "update_available": bool(latest and _is_newer(latest, current)),
        "release_url": RELEASES_PAGE,
    }


def reset_cache() -> None:
    global _checked, _latest
    with _lock:
        _checked = False
        _latest = None
