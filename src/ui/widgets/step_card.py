"""
파이프라인 단계 카드 위젯
# Design Ref: §2.2 — Step Cards: 상태 배지, 진행률, Run 버튼
# Design Ref: §9   — 에러 처리: Worker 실패 → 빨간 상태 표시
"""
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QProgressBar,
    QSizePolicy,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor


class StepStatus:
    IDLE      = "idle"       # 대기 (아직 실행 안 됨)
    RUNNING   = "running"    # 실행 중
    SUCCESS   = "success"    # 완료
    FAILED    = "failed"     # 실패
    SKIPPED   = "skipped"    # 건너뜀


_STATUS_ICON = {
    StepStatus.IDLE:    "⬜",
    StepStatus.RUNNING: "⏳",
    StepStatus.SUCCESS: "✅",
    StepStatus.FAILED:  "❌",
    StepStatus.SKIPPED: "⏭️",
}

_STATUS_COLOR = {
    StepStatus.IDLE:    "#555555",
    StepStatus.RUNNING: "#1a73e8",
    StepStatus.SUCCESS: "#188038",
    StepStatus.FAILED:  "#c5221f",
    StepStatus.SKIPPED: "#888888",
}


class StepCard(QWidget):
    """
    파이프라인 단일 단계 카드.

    Signals:
        run_requested(str):  사용자가 Run 버튼 클릭 — step_name 전달
    """

    run_requested = pyqtSignal(str)

    def __init__(self, step_name: str, label: str, parent=None):
        super().__init__(parent)
        self._step_name = step_name
        self._label = label
        self._status = StepStatus.IDLE
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumHeight(52)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(8)

        # 상태 아이콘
        self._icon_label = QLabel(_STATUS_ICON[self._status])
        self._icon_label.setFixedWidth(22)
        self._icon_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._icon_label)

        # 단계 이름 + 진행률 바
        info = QVBoxLayout()
        info.setSpacing(2)
        self._name_label = QLabel(self._label)
        self._name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        info.addWidget(self._name_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        info.addWidget(self._progress_bar)
        outer.addLayout(info)

        # Run 버튼
        self._run_btn = QPushButton("Run")
        self._run_btn.setFixedSize(52, 28)
        self._run_btn.clicked.connect(lambda: self.run_requested.emit(self._step_name))
        outer.addWidget(self._run_btn)

        self._update_appearance()

    # ── 상태 업데이트 API ──────────────────────────────────────────────

    def set_status(self, status: str):
        self._status = status
        self._update_appearance()

    def set_progress(self, percent: int):
        self._progress_bar.setValue(percent)

    def _update_appearance(self):
        icon = _STATUS_ICON.get(self._status, "⬜")
        color = _STATUS_COLOR.get(self._status, "#555555")

        self._icon_label.setText(icon)
        self._name_label.setStyleSheet(
            f"font-weight: bold; font-size: 12px; color: {color};"
        )

        is_running = self._status == StepStatus.RUNNING
        self._progress_bar.setVisible(is_running)
        self._run_btn.setEnabled(self._status not in (StepStatus.RUNNING,))

        # 카드 배경 (실행 중일 때 연한 파란색)
        if is_running:
            self.setStyleSheet("QWidget { background-color: #e8f0fe; border-radius: 4px; }")
        elif self._status == StepStatus.FAILED:
            self.setStyleSheet("QWidget { background-color: #fce8e6; border-radius: 4px; }")
        elif self._status == StepStatus.SUCCESS:
            self.setStyleSheet("QWidget { background-color: #e6f4ea; border-radius: 4px; }")
        else:
            self.setStyleSheet("QWidget { background-color: transparent; }")

    def reset(self):
        self._status = StepStatus.IDLE
        self._progress_bar.setValue(0)
        self._update_appearance()
