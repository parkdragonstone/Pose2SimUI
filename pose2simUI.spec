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
# PyQt5 plugins are found automatically by PyInstaller >= 6.0 on most platforms,
# but we list the ones that ship as Python sub-packages to be safe.
hidden_imports = [
    # PyQt5 bindings used at runtime
    "PyQt5.QtWidgets",
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtMultimedia",
    "PyQt5.QtMultimediaWidgets",
    # matplotlib Qt5 backend (명시적으로 PyQt5 백엔드 지정)
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends._backend_tk",
    # mpl_toolkits needed for Axes3D
    "mpl_toolkits.mplot3d",
    "mpl_toolkits.mplot3d.axes3d",
    "mpl_toolkits.mplot3d.art3d",
    # stdlib — tomllib (3.11+)
    "tomllib",
    # tomli-w (third-party write)
    "tomli_w",
    # cv2
    "cv2",
]

# NumPy 2.x restructured internals into numpy._core (private package).
# PyInstaller's hook misses it; collect_submodules ensures everything is bundled.
hidden_imports += collect_submodules("numpy")

# ── Data files ────────────────────────────────────────────────────────────────
datas = []

# matplotlib data (fonts, style sheets, etc.)
datas += collect_data_files("matplotlib")

# mpl_toolkits
datas += collect_data_files("mpl_toolkits")

# Pose2Sim 데이터 파일 (LSTM 모델, OpenSim 설정 등 321개 파일)
datas += collect_data_files("Pose2Sim")

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[str(ROOT / "hooks")],
    hooksconfig={
        "matplotlib": {"backends": ["Qt5Agg", "Agg"]},
    },
    runtime_hooks=[str(ROOT / "hooks" / "pyi_rth_cv2_fix.py")],
    excludes=[
        # test / dev dependencies
        "pytest", "pytest_qt", "sphinx",
        # heavy ML libs not needed at runtime
        "torch", "tensorflow",
        # tkinter은 Pose2Sim/common.py가 모듈 레벨에서 import하므로 번들 필요
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
    icon=str(ROOT / "images" / "icon.icns"),
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
        icon=str(ROOT / "images" / "icon.icns"),
        bundle_identifier="com.pose2simui.app",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "LSMinimumSystemVersion": "12.0",
        },
    )
