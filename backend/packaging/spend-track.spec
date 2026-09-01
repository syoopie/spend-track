# PyInstaller spec for the double-clickable build.
#
# Run it through scripts/build_desktop.py rather than directly - the spec
# assumes the frontend has already been compiled into frontend/dist, which
# that script takes care of.
#
# One binary has to carry three things Python normally finds on disk:
#   * the compiled React UI (webui/), served by app/webui.py
#   * app/schema.sql, read via importlib.resources at first run
#   * uvicorn's protocol/loop/lifespan implementations, which it imports by
#     string at runtime, so PyInstaller's static analysis never sees them

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]  # backend/packaging -> repo root
BACKEND = ROOT / "backend"
WEBUI = ROOT / "frontend" / "dist"
# One PNG master for every platform: PyInstaller converts it to .ico or
# .icns as needed (via Pillow, which pdfplumber already pulls in), so there
# are no per-platform binaries to keep in sync with docs/logo.svg.
ICON = SPECPATH + "/icon.png"

if not (WEBUI / "index.html").is_file():
    raise SystemExit(
        "frontend/dist is missing or empty - run `npm ci && npm run build` in frontend/ first "
        "(scripts/build_desktop.py does this for you)."
    )

datas = [
    (str(WEBUI), "webui"),
    (str(BACKEND / "src" / "app" / "schema.sql"), "app"),
]
# pdfminer ships character-map tables as package data; without them
# pdfplumber raises on the first CJK-ish glyph it meets in a statement.
datas += collect_data_files("pdfminer")

hiddenimports = collect_submodules("uvicorn")

a = Analysis(
    [str(BACKEND / "src" / "app" / "desktop.py")],
    pathex=[str(BACKEND / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy.testing", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SpendTrack",
    icon=ICON,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # console=True on purpose, including on Windows: the window doubles as
    # the app's status display ("open at http://...", "closing this window
    # shuts the app down") and as the way to quit it.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    # macOS gets a .app as well, so the download is something a user can
    # double-click in Finder rather than a bare Unix executable.
    app = BUNDLE(
        exe,
        name="SpendTrack.app",
        icon=ICON,
        bundle_identifier="dev.spendtrack.app",
        info_plist={
            "CFBundleName": "SpendTrack",
            "CFBundleDisplayName": "SpendTrack",
            "CFBundleShortVersionString": "0.2.1",  # keep in step with pyproject.toml and the release tag
            "LSMinimumSystemVersion": "12.0",
            "LSBackgroundOnly": False,
        },
    )
