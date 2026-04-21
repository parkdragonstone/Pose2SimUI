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
    자체 메인 스레드를 가지므로 matplotlib GUI 창을 정상적으로 열 수 있음.
    stdout/stderr/logging을 log_queue로 전달.
    """
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
