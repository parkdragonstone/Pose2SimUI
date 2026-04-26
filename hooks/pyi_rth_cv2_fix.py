"""
Runtime hook: fix cv2 bootstrap recursion in PyInstaller macOS .app bundles.

In .app bundles, PyInstaller's FrozenImporter intercepts `importlib.import_module("cv2")`
even after `sys.modules.pop("cv2")`, causing cv2's bootstrap to recurse infinitely.

Fix: monkey-patch importlib.import_module so that when called from inside cv2's bootstrap
(detected via sys.OpenCV_LOADER), we load the native cv2.abi3.so directly instead of
going through the regular import machinery.
"""
import sys
import os
import importlib
import importlib.util as _util

_orig_import_module = importlib.import_module


def _patched_import_module(name, package=None):
    # Only intercept the cv2-inside-bootstrap case
    if name == "cv2" and getattr(sys, "OpenCV_LOADER", False):
        # Search sys.path for cv2.abi3.so (the native extension)
        for p in sys.path:
            if not os.path.isdir(p):
                continue
            try:
                entries = os.listdir(p)
            except OSError:
                continue
            for fname in entries:
                if fname.startswith("cv2") and fname.endswith(".so"):
                    so_path = os.path.join(p, fname)
                    if os.path.isfile(so_path):
                        spec = _util.spec_from_file_location("cv2", so_path)
                        if spec is not None:
                            mod = _util.module_from_spec(spec)
                            try:
                                spec.loader.exec_module(mod)
                                return mod
                            except Exception:
                                pass
    return _orig_import_module(name, package)


importlib.import_module = _patched_import_module
