# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Pose2SimUI
Build:
  macOS : ./build.sh
  Windows: build.bat
"""
import sys
import os, glob
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs, collect_data_files

ROOT = Path(SPECPATH)

if sys.platform == "darwin":
    icon_path = str(ROOT / "images" / "icon.icns")
else:
    icon_path = str(ROOT / "images" / "icon.ico")

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
hidden_imports += collect_submodules("onnxruntime")
# ── Data files ────────────────────────────────────────────────────────────────
datas = []

datas += collect_data_files("matplotlib")
datas += collect_data_files("mpl_toolkits")
datas += collect_data_files("Pose2Sim")
datas += collect_data_files("onnxruntime")
# openvino 제외: onnxruntime 백엔드 사용, openvino 불필요하며 libhwloc.dylib 처리 오류 발생

binaries = []

binaries += collect_dynamic_libs("onnxruntime")

# ── MKL DLL 강제 번들 (Windows 전용) ──────────────────────────────────────────
mkl_bin = os.path.join(
    os.environ.get("CONDA_PREFIX", ""),
    "Library", "bin"
)

mkl_dlls = glob.glob(os.path.join(mkl_bin, "mkl_*.dll"))
mkl_dlls += glob.glob(os.path.join(mkl_bin, "libiomp5md.dll"))

for dll in mkl_dlls:
    binaries.append((dll, "."))

# openvino dylib 제외 (libhwloc.dylib arm64 처리 오류)

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[str(ROOT / "hooks")],
    hooksconfig={
        "matplotlib": {"backends": ["Qt5Agg", "Agg"]},
    },
    runtime_hooks=[
        str(ROOT / "hooks" / "pyi_rth_cv2_fix.py"),      
    ],
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
    upx=False,
    console=False,        # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,     # None = native arch; set "universal2" for fat binary
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[
        "onnxruntime.dll",
        "onnxruntime_providers_shared.dll",
        "onnxruntime_pybind11_state.pyd",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll"
    ],
    name="Pose2SimUI",
)

# ── macOS .app bundle ─────────────────────────────────────────────────────────
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Pose2SimUI.app",
        icon=icon_path,
        bundle_identifier="com.pose2simui.app",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "LSMinimumSystemVersion": "12.0",
        },
    )
