"""
파이프라인 단계별 실행 워커
# Design Ref: §5.1 — PipelineWorker: Pose2Sim API를 QThread에서 실행
# Plan SC: SC-04 — 파이프라인 각 단계 개별 실행 가능
# Plan SC: SC-05 — 실행 중 UI 블로킹 없음
"""
import io
import sys
import os
import logging
import multiprocessing as mp
from pathlib import Path
from typing import Callable

from src.core.workers.base_worker import BaseWorker


# ── subprocess 진입점 (모듈 최상위 — multiprocessing spawn 필수) ─────────────
def _subprocess_entry(step_key: str, working_dir: str, log_queue):
    """
    별도 프로세스에서 Pose2Sim 단계를 실행.
    spawn 컨텍스트이므로:
      - MPLBACKEND=Agg: matplotlib이 Qt 백엔드를 로드하지 않도록 (PyQt 충돌 방지)
      - PYQTGRAPH_QT_LIB=PyQt5: pyqtgraph가 PyQt6를 로드하지 않도록
      - cv2 display 함수를 no-op으로 교체 (헤드리스 환경 SIGSEGV 방지)
    """
    os.environ["MPLBACKEND"] = "Agg"
    os.environ["PYQTGRAPH_QT_LIB"] = "PyQt5"
    try:
        import cv2 as _cv2
        _cv2.imshow            = lambda *a, **k: None
        _cv2.waitKey           = lambda *a, **k: -1
        _cv2.destroyAllWindows = lambda *a, **k: None
        _cv2.destroyWindow     = lambda *a, **k: None
        _cv2.namedWindow       = lambda *a, **k: None
        _cv2.moveWindow        = lambda *a, **k: None
    except Exception:
        pass
    os.chdir(working_dir)

    class _Writer(io.TextIOBase):
        def __init__(self, q):
            super().__init__()
            self._q = q
            self._buf = ""

        def write(self, text):
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line.strip():
                    self._q.put(("log", line))
            return len(text)

        def flush(self):
            if self._buf.strip():
                self._q.put(("log", self._buf))
                self._buf = ""

    writer = _Writer(log_queue)
    sys.stdout = sys.stderr = writer

    log_handler = logging.StreamHandler(writer)
    root = logging.getLogger()
    root.addHandler(log_handler)
    root.setLevel(logging.INFO)

    try:
        import Pose2Sim.Pose2Sim as _P2S_mod
        _P2S_mod.setup_logging = lambda *a, **k: None   # logs.txt 생성 차단
        from Pose2Sim import Pose2Sim as P2S
        fn_map = {
            "pose_estimation":    P2S.poseEstimation,
            "synchronization":    P2S.synchronization,
            "person_association": P2S.personAssociation,
            "triangulation":      P2S.triangulation,
            "filtering":          P2S.filtering,
            "marker_augmentation": P2S.markerAugmentation,
            "kinematics":         P2S.kinematics,
        }
        if step_key not in fn_map:
            log_queue.put(("log", f"[ERROR] 알 수 없는 단계: {step_key}"))
            log_queue.put(("done", False))
            return
        fn_map[step_key]()
        log_queue.put(("done", True))
    except Exception as e:
        import traceback
        log_queue.put(("log", f"[ERROR] {e}"))
        log_queue.put(("log", traceback.format_exc()))
        log_queue.put(("done", False))
    finally:
        # Pose2Sim이 생성하는 logs.txt 삭제
        for name in ("logs.txt", "logs.log"):
            p = Path(working_dir) / name
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


class SubprocessPipelineWorker(BaseWorker):
    """
    Pose2Sim 단계를 별도 프로세스에서 실행하는 워커.

    - subprocess는 자체 메인 스레드를 가지므로 matplotlib/tkinter GUI 창을 표시 가능.
    - onnxruntime 등 native crash가 발생해도 메인 프로세스(UI)는 보호됨.
    - QThread에서 subprocess를 감시하며 log_queue 메시지를 log_line Signal로 전달.
    """

    def __init__(self, step_name: str, step_key: str, working_dir: Path, parent=None):
        super().__init__(parent)
        self._step_name = step_name
        self._step_key = step_key
        self._working_dir = working_dir

    def _execute(self):
        self.log_line.emit(f"[{self._step_name}] 시작: {self._working_dir}")

        ctx = mp.get_context("spawn")
        queue = ctx.Queue()
        proc = ctx.Process(
            target=_subprocess_entry,
            args=(self._step_key, str(self._working_dir), queue),
            daemon=True,
        )
        proc.start()

        success = False
        while True:
            try:
                msg_type, payload = queue.get(timeout=0.5)
                if msg_type == "log":
                    self.log_line.emit(payload)
                elif msg_type == "done":
                    success = payload
                    break
            except Exception:
                if not proc.is_alive():
                    code = proc.exitcode
                    self.log_line.emit(
                        f"[ERROR] 프로세스가 예기치 않게 종료됨 (exit code: {code})"
                    )
                    break

        proc.join(timeout=5)
        if proc.is_alive():
            proc.terminate()

        self.log_line.emit(f"[{self._step_name}] {'완료' if success else '실패'}")
        if not success:
            raise RuntimeError(f"{self._step_name} 실패")


# ── 캘리브레이션 subprocess 진입점 ──────────────────────────────────────────────

def _calib_subprocess_entry(step: str, config_dict: dict, image_coords_2d, working_dir: str, log_queue):
    """
    별도 프로세스에서 Pose2Sim.calibration 실행.
    PyQt5(Pose2Sim 내부 의존)가 PyQt6(메인 프로세스) 와 충돌하지 않도록 격리.
    """
    import os as _os
    import sys as _sys
    import io as _io
    import logging as _logging
    from pathlib import Path as _Path

    _os.chdir(working_dir)

    class _Writer(_io.TextIOBase):
        def __init__(self, q):
            super().__init__()
            self._q = q
            self._buf = ""

        def write(self, text):
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line.strip():
                    self._q.put(("log", line))
            return len(text)

        def flush(self):
            if self._buf.strip():
                self._q.put(("log", self._buf))
                self._buf = ""

    writer = _Writer(log_queue)
    _sys.stdout = _sys.stderr = writer
    _log_handler = _logging.StreamHandler(writer)
    _root = _logging.getLogger()
    _root.addHandler(_log_handler)
    _root.setLevel(_logging.INFO)

    try:
        # ── 환경 변수 선행 설정 ─────────────────────────────────────────
        # spawn 서브프로세스는 부모의 PYQTGRAPH_QT_LIB=PyQt6 를 상속하므로,
        # matplotlib 백엔드 탐색이 PyQt6 를 로드하면 Pose2Sim 의 PyQt5 와 충돌 → SIGBUS.
        # matplotlib import 전에 Agg 백엔드를 강제하고 pyqtgraph 도 PyQt5 로 고정.
        import os as _os2
        _os2.environ["MPLBACKEND"] = "Agg"
        _os2.environ["PYQTGRAPH_QT_LIB"] = "PyQt5"

        # ── OpenCV display 억제 (headless 환경) ──────────────────────────
        try:
            import cv2 as _cv2
            _cv2.imshow            = lambda *a, **k: None
            _cv2.waitKey           = lambda *a, **k: -1
            _cv2.destroyAllWindows = lambda *a, **k: None
            _cv2.destroyWindow     = lambda *a, **k: None
            _cv2.namedWindow       = lambda *a, **k: None
            _cv2.moveWindow        = lambda *a, **k: None
        except Exception:
            pass

        import matplotlib as _mpl
        import matplotlib.pyplot as _plt

        try:
            _mpl.use("Agg")
        except Exception:
            pass

        class _SF:
            class _SC:
                def draw(self, *a, **k): pass
                def mpl_connect(self, *a, **k): return 0
                def mpl_disconnect(self, *a, **k): pass

            class _SM:
                class _SW:
                    def showMaximized(self, *a, **k): pass
                    def show(self, *a, **k): pass
                window = _SW()
                def set_window_title(self, *a, **k): pass
                def show(self, *a, **k): pass

            canvas = _SC()
            number = 999
            def show(self, *a, **k): pass
            def tight_layout(self, *a, **k): pass
            def savefig(self, *a, **k): pass
            def add_subplot(self, *a, **k):
                class _SA:
                    def imshow(self, *a, **k): pass
                    def axis(self, *a, **k): pass
                return _SA()
            def subplots_adjust(self, *a, **k): pass

        _sf = _SF()
        _plt.show  = lambda *a, **k: None
        _plt.gcf   = lambda: _sf
        _plt.figure = lambda *a, **k: _sf
        _plt.close  = lambda *a, **k: None
        _plt.draw   = lambda *a, **k: None
        _plt.subplots = lambda *a, **k: (_sf, _sf.add_subplot())
        _plt.get_current_fig_manager = lambda: _SF._SM()
        _plt.ginput = lambda *a, **k: []

        try:
            import tkinter.messagebox as _tkbox
            _tkbox.askyesno = lambda *a, **k: True
        except Exception:
            pass

        try:
            import numpy as _np
            import cv2 as _cv2_dbg
            import Pose2Sim.calibration as _p2s_calib

            if step == "intrinsic":
                # imgp_objp_visualizer_clicker를 monkeypatch:
                # matplotlib GUI 없이 감지된 코너를 debug_images에 저장 후 자동 확인.
                _debug_dir = _Path(working_dir) / "calibration" / "debug_images"
                _debug_dir.mkdir(parents=True, exist_ok=True)
                _dbg_counter = [0]

                def _intrinsic_visualizer(img, imgp=None, objp=None, img_path=None):
                    _dbg_counter[0] += 1
                    stem = _Path(img_path).stem if img_path else f"frame_{_dbg_counter[0]}"
                    fname = f"{_dbg_counter[0]:04d}_{stem}.png"
                    debug_img = img.copy()
                    if imgp is not None and len(imgp) > 0:
                        for pt in imgp:
                            x, y = int(pt[0][0]), int(pt[0][1])
                            _cv2_dbg.circle(debug_img, (x, y), 5, (0, 255, 0), -1)
                            _cv2_dbg.circle(debug_img, (x, y), 6, (0, 0, 255), 1)
                    _cv2_dbg.imwrite(str(_debug_dir / fname), debug_img)
                    return imgp, objp

                _p2s_calib.imgp_objp_visualizer_clicker = _intrinsic_visualizer
                log_queue.put(("log", f"[INFO] debug_images → {_debug_dir}"))

            elif image_coords_2d and step == "extrinsic":
                _sorted = sorted(image_coords_2d.keys())
                _coords_iter = iter([image_coords_2d[c] for c in _sorted])

                def _mock_clicker(img, imgp=None, objp=None, img_path=None):
                    try:
                        pts = next(_coords_iter)
                        return _np.array([[float(p[0]), float(p[1])] for p in pts], dtype=_np.float32), objp
                    except StopIteration:
                        return (imgp if imgp is not None else _np.zeros((0, 2), dtype=_np.float32)), objp

                _p2s_calib.imgp_objp_visualizer_clicker = _mock_clicker

        except Exception:
            pass

        import Pose2Sim.Pose2Sim as _P2S_mod
        _P2S_mod.setup_logging = lambda *a, **k: None   # logs.txt 생성 차단
        from Pose2Sim import Pose2Sim as P2S
        P2S.calibration(config_dict)
        log_queue.put(("done", True))
    except Exception as e:
        import traceback as _tb
        log_queue.put(("log", f"[ERROR] {e}"))
        log_queue.put(("log", _tb.format_exc()))
        log_queue.put(("done", False))
    finally:
        for _name in ("logs.txt", "logs.log"):
            _p = _Path(working_dir) / _name
            try:
                _p.unlink(missing_ok=True)
            except Exception:
                pass


class SubprocessCalibWorker(BaseWorker):
    """
    Pose2Sim 캘리브레이션을 별도 프로세스에서 실행하는 워커.
    PyQt5(Pose2Sim) 와 PyQt6(UI) 의 objc 클래스 충돌을 프로세스 격리로 방지.
    """

    def __init__(self, step: str, config_dict: dict, image_coords_2d, working_dir: "Path", parent=None):
        super().__init__(parent)
        self._step = step
        self._config_dict = config_dict
        self._image_coords_2d = image_coords_2d
        self._working_dir = working_dir

    def _execute(self):
        label = "Intrinsic 캘리브레이션" if self._step == "intrinsic" else "Extrinsic 캘리브레이션"
        self.log_line.emit(f"[{label}] 시작: {self._working_dir}")

        ctx = mp.get_context("spawn")
        queue = ctx.Queue()
        proc = ctx.Process(
            target=_calib_subprocess_entry,
            args=(self._step, self._config_dict, self._image_coords_2d, str(self._working_dir), queue),
            daemon=True,
        )
        proc.start()

        success = False
        while True:
            try:
                msg_type, payload = queue.get(timeout=0.5)
                if msg_type == "log":
                    self.log_line.emit(payload)
                elif msg_type == "done":
                    success = payload
                    break
            except Exception:
                if not proc.is_alive():
                    code = proc.exitcode
                    self.log_line.emit(f"[ERROR] 프로세스가 예기치 않게 종료됨 (exit code: {code})")
                    break

        proc.join(timeout=5)
        if proc.is_alive():
            proc.terminate()

        self.log_line.emit(f"[{label}] {'완료' if success else '실패'}")
        if not success:
            raise RuntimeError(f"{label} 실패")


# ── 캘리브레이션 전용 인라인 워커 (api_fn 람다 — subprocess 불필요) ───────────

def _suppress_gui():
    """
    macOS ARM64 worker thread에서 matplotlib/tkinter GUI 호출 억제.
    plt.show() 등이 Cocoa 메인스레드 밖에서 호출되면 NSException → Abort 발생.
    반환값: restore 함수 (finally 블록에서 호출).
    """
    restorers = []
    try:
        import matplotlib.pyplot as plt
        _orig_show = plt.show
        plt.show = lambda *a, **k: None

        _fm_logger = logging.getLogger('matplotlib.font_manager')
        _orig_fm_level = _fm_logger.level
        _fm_logger.setLevel(logging.WARNING)

        def _restore_mpl():
            try:
                plt.show = _orig_show
            except Exception:
                pass
            _fm_logger.setLevel(_orig_fm_level)
        restorers.append(_restore_mpl)
    except Exception:
        pass

    try:
        import tkinter.messagebox as _tkbox
        _orig_askyesno = _tkbox.askyesno
        _tkbox.askyesno = lambda *a, **k: True

        def _restore_tk():
            try:
                _tkbox.askyesno = _orig_askyesno
            except Exception:
                pass
        restorers.append(_restore_tk)
    except Exception:
        pass

    def restore():
        for fn in restorers:
            fn()
    return restore


class _FakeManager:
    class _FakeWindow:
        def showMaximized(self, *a, **k): pass
        def show(self, *a, **k): pass
    window = _FakeWindow()
    def set_window_title(self, *a, **k): pass
    def show(self, *a, **k): pass


class PipelineWorker(BaseWorker):
    """
    단일 Pose2Sim API 단계를 QThread에서 실행하는 워커 (캘리브레이션 전용).
    GUI 억제 패치 적용 — 일반 파이프라인은 SubprocessPipelineWorker 사용.
    """

    def __init__(
        self,
        step_name: str,
        api_fn: Callable,
        working_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._step_name = step_name
        self._api_fn = api_fn
        self._working_dir = working_dir

    def _execute(self):
        self.log_line.emit(f"[{self._step_name}] 시작: {self._working_dir}")

        original_dir = Path.cwd()
        restore_gui = _suppress_gui()
        try:
            os.chdir(self._working_dir)

            captured = _StreamCapture(self.log_line.emit)
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = captured
            sys.stderr = captured

            log_handler = _LoggingCapture(self.log_line.emit)
            root_logger = logging.getLogger()
            old_handlers = root_logger.handlers[:]
            old_level = root_logger.level
            root_logger.addHandler(log_handler)
            root_logger.setLevel(logging.INFO)

            try:
                self._api_fn()
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                for h in root_logger.handlers[:]:
                    if isinstance(h, logging.FileHandler):
                        h.close()
                        root_logger.removeHandler(h)
                        try:
                            Path(h.baseFilename).unlink(missing_ok=True)
                        except Exception:
                            pass
                root_logger.removeHandler(log_handler)
                root_logger.handlers = old_handlers
                root_logger.setLevel(old_level)
                captured.flush()

            self.log_line.emit(f"[{self._step_name}] 완료")
        finally:
            # Pose2Sim이 생성하는 logs.txt 삭제
            for name in ("logs.txt", "logs.log"):
                p = self._working_dir / name
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
            os.chdir(original_dir)
            restore_gui()


class _StreamCapture(io.TextIOBase):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback
        self._buf = ""

    def write(self, text: str) -> int:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._callback(line)
        return len(text)

    def flush(self):
        if self._buf.strip():
            self._callback(self._buf)
            self._buf = ""


class _LoggingCapture(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            if msg.strip():
                self._callback(msg)
        except Exception:
            pass
