"""Build the double-clickable app for whichever OS you run this on.

    uv run --group build python scripts/build_desktop.py

Produces `dist/SpendTrack` (Linux), `dist/SpendTrack.exe` (Windows) or
`dist/SpendTrack.app` (macOS). Cross-compiling isn't possible - PyInstaller
freezes the interpreter it is running under - so each platform's artifact is
built on that platform; .github/workflows/desktop-build.yml does all three.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FRONTEND = ROOT / "frontend"
SPEC = BACKEND / "packaging" / "spend-track.spec"


def run(cmd: list[str], cwd: Path) -> None:
    print(f"\n$ {' '.join(cmd)}  (in {cwd.relative_to(ROOT)})", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def build_frontend() -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm not found - Node.js is needed to compile the UI (only to build, never to run).")
    # `npm ci` needs a lockfile and wipes node_modules; fall back to install
    # so a contributor with a warm tree isn't forced through a cold one.
    run([npm, "ci" if (FRONTEND / "package-lock.json").is_file() else "install"], cwd=FRONTEND)
    run([npm, "run", "build"], cwd=FRONTEND)


def build_executable(clean: bool) -> None:
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm", "--distpath", str(BACKEND / "dist")]
    if clean:
        cmd.append("--clean")
    run(cmd, cwd=BACKEND)


def artifact_path() -> Path:
    dist = BACKEND / "dist"
    system = platform.system()
    if system == "Darwin":
        return dist / "SpendTrack.app"
    if system == "Windows":
        return dist / "SpendTrack.exe"
    return dist / "SpendTrack"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-frontend", action="store_true", help="reuse an existing frontend/dist")
    parser.add_argument("--clean", action="store_true", help="discard PyInstaller's caches first")
    args = parser.parse_args()

    if not args.skip_frontend:
        build_frontend()
    elif not (FRONTEND / "dist" / "index.html").is_file():
        raise SystemExit("--skip-frontend was passed but frontend/dist has no build in it.")

    build_executable(clean=args.clean)

    artifact = artifact_path()
    if not artifact.exists():
        raise SystemExit(f"PyInstaller reported success but {artifact} isn't there.")
    size_mb = sum(f.stat().st_size for f in artifact.rglob("*") if f.is_file()) / 1e6 if artifact.is_dir() else artifact.stat().st_size / 1e6
    print(f"\nBuilt {artifact.relative_to(ROOT)} ({size_mb:.0f} MB)")
    if os.name != "nt":
        artifact.chmod(artifact.stat().st_mode | 0o111)
    return 0


if __name__ == "__main__":
    sys.exit(main())
