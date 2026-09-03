"""The version string lives in pyproject.toml, gets copied by hand into the
PyInstaller spec's CFBundleShortVersionString, and names the release tag.
The spec comment says "keep in step" - this is that instruction as a check,
so a bump that misses one place fails here instead of shipping a macOS
build whose Get Info disagrees with the download.
"""

import re
import tomllib
from importlib.metadata import version
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PYPROJECT = BACKEND / "pyproject.toml"
SPEC = BACKEND / "packaging" / "spend-track.spec"


def _pyproject_version() -> str:
    return tomllib.loads(PYPROJECT.read_text())["project"]["version"]


def _spec_bundle_version() -> str:
    match = re.search(r'"CFBundleShortVersionString":\s*"([^"]+)"', SPEC.read_text())
    assert match, "CFBundleShortVersionString not found in the spec"
    return match.group(1)


def test_pyproject_and_spec_versions_match():
    assert _pyproject_version() == _spec_bundle_version()


def test_installed_metadata_matches_pyproject():
    # app/updates.py reads this at runtime; if it drifts from pyproject the
    # About card reports a version the source never had.
    assert version("spendtrack") == _pyproject_version()
