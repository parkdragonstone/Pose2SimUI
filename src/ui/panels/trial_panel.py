"""
Trial 목록 패널 — 사이드바 하단, Trial 항목 + 상태 배지
# Design Ref: §2.1 — Trial List: 프로젝트 내 Trial 목록 + 상태 배지
# Design Ref: §3.1 — trial_selected Signal
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QSizePolicy,
    QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from src.core.project import Project, Trial
from src.core.trial_manager import TrialManager
from src.ui.widgets.empty_state import EmptyState


class TrialPanel(QWidget):
    """
    왼쪽 사이드바 하단의 Trial 목록 위젯.

    Signals:
        trial_selected(Trial): Trial 항목 클릭 시 발행.
    """

    trial_selected = pyqtSignal(object)   # Trial

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = TrialManager(self)
        self._project: Project | None = None
        self._setup_ui()
        self._manager.trial_status_changed.connect(self._on_status_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # ── 헤더 ─────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("Trials")
        title.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #94A3B8; letter-spacing: 0.5px;"
        )
        header.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addStretch()

        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedSize(22, 22)
        refresh_btn.setToolTip("Trial 목록 새로고침")
        refresh_btn.setStyleSheet(
            "QPushButton { font-size: 13px; padding: 0; margin: 0; text-align: center; }"
        )
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header)

        # ── Trial 목록 ────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setObjectName("trial_list")
        self._list.setSpacing(1)
        self._list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        # ── 빈 상태 ──────────────────────────────────────────────────
        self._empty = EmptyState("Trial 폴더 없음\n프로젝트 루트 아래\n하위 폴더를 추가하세요")
        self._empty.hide()
        layout.addWidget(self._empty)

    # ── 공개 API ─────────────────────────────────────────────────────

    def set_project(self, project: Project) -> None:
        """프로젝트 설정 + Trial 목록 갱신."""
        self._project = project
        self._refresh()

    def refresh(self) -> None:
        """외부에서도 호출 가능한 공개 새로고침."""
        self._refresh()

    # ── 내부 메서드 ───────────────────────────────────────────────────

    def _refresh(self):
        self._list.clear()
        if self._project is None:
            self._show_empty(True)
            return

        trials = self._manager.discover_trials(self._project)
        self._project.trials = trials

        if not trials:
            self._show_empty(True)
            return

        self._show_empty(False)
        for trial in trials:
            item = self._make_item(trial)
            self._list.addItem(item)

    def _make_item(self, trial: Trial) -> QListWidgetItem:
        badge = trial.status_label
        text = f"{trial.name}  {badge}" if badge else trial.name
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, trial)
        item.setToolTip(str(trial.path))
        return item

    def _on_item_clicked(self, item: QListWidgetItem):
        trial: Trial = item.data(Qt.ItemDataRole.UserRole)
        if trial:
            self._manager.switch_trial(trial)
            self.trial_selected.emit(trial)

    def _on_status_changed(self, trial_name: str, status: dict):
        """trial_status_changed Signal → 해당 항목 배지 갱신."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            trial: Trial = item.data(Qt.ItemDataRole.UserRole)
            if trial and trial.name == trial_name:
                # Trial 객체의 상태를 재평가해 텍스트 갱신
                badge = trial.status_label
                text = f"{trial.name}  {badge}" if badge else trial.name
                item.setText(text)
                break

    def _show_empty(self, show: bool):
        self._list.setVisible(not show)
        self._empty.setVisible(show)
