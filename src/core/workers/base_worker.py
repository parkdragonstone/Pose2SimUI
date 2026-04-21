"""
QThread 기반 베이스 워커
# Design Ref: §3.1 — BaseWorker: progress / log_line / finished(bool, str) Signal
# Plan SC: SC-05 — 실행 중 UI 블로킹 없음 (QThread)
"""
import traceback
from PyQt6.QtCore import QThread, pyqtSignal


class BaseWorker(QThread):
    """
    모든 Pose2Sim 단계 워커의 베이스 클래스.

    Signals:
        progress(int):           0~100 진행률
        log_line(str):           로그 한 줄
        finished(bool, str):     성공 여부, 메시지
    """
    progress = pyqtSignal(int)
    log_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def run(self):
        """
        서브클래스는 _execute()를 오버라이드.
        예외 처리와 finished Signal 발행은 이 클래스가 담당.
        """
        try:
            self._execute()
            self.finished.emit(True, "완료")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            self.log_line.emit(f"[ERROR] {error_msg}")
            self.finished.emit(False, str(e))

    def _execute(self):
        """서브클래스에서 구현: 실제 작업 로직."""
        raise NotImplementedError
