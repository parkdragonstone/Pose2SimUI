"""
Trial 탐지, 전환, 상태 평가
# Design Ref: §5.2 — TrialManager: discover_trials(), switch_trial(), Signals
# Design Ref: §3.1 — Signals: trial_switched, trial_status_changed
"""
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

from src.core.project import Project, Trial


# Pose2Sim이 사용하는 예약 폴더 — Trial로 취급하지 않음
_EXCLUDE_DIRS: frozenset[str] = frozenset({
    "calibration", "logs", ".git", "__pycache__",
    ".bkit", "docs", "node_modules",
})


class TrialManager(QObject):
    """
    프로젝트 내 Trial 목록 탐지·전환·상태 갱신 담당.

    Signals:
        trial_switched(Trial):              Trial 전환 완료 시 발행.
        trial_status_changed(str, dict):    trial_name, status_dict (has_pose_video 등).
    """

    trial_switched       = pyqtSignal(object)       # Trial
    trial_status_changed = pyqtSignal(str, dict)    # trial_name, status

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current: Trial | None = None

    # ── Trial 탐지 ───────────────────────────────────────────────────

    def discover_trials(self, project: Project) -> list[Trial]:
        """
        프로젝트 루트 아래 하위 폴더를 이름 순으로 탐색.
        예약 폴더(_EXCLUDE_DIRS)는 제외한다.
        # Design Ref: §5.2 — discover_trials
        """
        trials: list[Trial] = []
        try:
            for d in sorted(project.root_path.iterdir()):
                if d.is_dir() and d.name not in _EXCLUDE_DIRS and not d.name.startswith("."):
                    trials.append(Trial(name=d.name, path=d))
        except PermissionError:
            pass
        return trials

    # ── Trial 전환 ───────────────────────────────────────────────────

    def switch_trial(self, trial: Trial) -> None:
        """
        Trial 전환: 현재 Trial 교체 + trial_switched Signal 발행.
        # Design Ref: §5.2 — switch_trial
        """
        self._current = trial
        self.trial_switched.emit(trial)

    # ── 상태 평가 ────────────────────────────────────────────────────

    def get_status(self, trial: Trial) -> dict:
        """
        Trial 디렉토리를 검사해 분석 완료 상태 dict 반환.
        UI 상태 배지(TrialPanel)에서 사용.
        """
        return {
            "has_pose_video": trial.has_pose_video,
            "has_trc":        trial.has_trc,
            "has_kinematics": trial.has_kinematics,
        }

    def emit_status(self, trial: Trial) -> None:
        """trial_status_changed Signal을 직접 발행."""
        self.trial_status_changed.emit(trial.name, self.get_status(trial))

    # ── 프로퍼티 ─────────────────────────────────────────────────────

    @property
    def current(self) -> Trial | None:
        return self._current
