# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Pose2SimUI
Build:
  macOS : ./build.sh
  Windows: build.bat
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH)

# ── Hidden imports ────────────────────────────────────────────────────────────
# PyQt6 plugins are found automatically by PyInstaller >= 6.0 on most platforms,
# but we list the ones that ship as Python sub-packages to be safe.
hidden_imports = [
    # PyQt6 bindings used at runtime
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    # matplotlib Qt6 backend
    "matplotlib.backends.backend_qtagg",
    # mpl_toolkits needed for Axes3D
    "mpl_toolkits.mplot3d",
    # stdlib — tomllib (3.11+)
    "tomllib",
    # tomli-w (third-party write)
    "tomli_w",
    # numpy / cv2 side-modules sometimes missed
    "numpy.core._methods",
    "numpy.lib.format",
    "cv2",
]

# ── Data files ────────────────────────────────────────────────────────────────
datas = []

# matplotlib data (fonts, style sheets, etc.)
datas += collect_data_files("matplotlib")

# mpl_toolkits
datas += collect_data_files("mpl_toolkits")

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # test / dev dependencies
        "pytest", "pytest_qt", "sphinx",
        # heavy ML libs not needed at runtime
        "torch", "tensorflow",
        # tkinter (PyInstaller sometimes drags it in via matplotlib)
        "_tkinter", "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ── Platform-specific exe ─────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Pose2SimUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,     # None = native arch; set "universal2" for fat binary
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.icns",   # uncomment after adding icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Pose2SimUI",
)

# ── macOS .app bundle ─────────────────────────────────────────────────────────
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Pose2SimUI.app",
        # icon="assets/icon.icns",
        bundle_identifier="com.pose2simui.app",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "LSMinimumSystemVersion": "12.0",
        },
    )
